import json
import re
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

OUTPUT = Path("data/generators/exhibitions.json")

SOURCES = [
    ("Lisboa", "https://www.ccb.pt/"),
    ("Lisboa", "https://gulbenkian.pt/"),
    ("Lisboa", "https://www.maat.pt/"),
    ("Porto", "https://www.serralves.pt/"),
    ("Lisboa", "https://www.saomamede.com/listagem/exposicoes"),
]

EXHIBITION_WORDS = (
    "exposi", "exhibition", "mostra", "pintura", "painting",
    "fotografia", "photography", "arquitetura", "architecture",
    "design", "arte contempor"
)

LINK_WORDS = ("expos", "exhib", "mostra")
MAX_LINKS_PER_SOURCE = 15


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.in_json = False
        self.json_buffer = []
        self.links = []
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if (
            tag == "script"
            and attrs.get("type", "").lower() == "application/ld+json"
        ):
            self.in_json = True
            self.json_buffer = []

        if tag == "a":
            self.link = [attrs.get("href", ""), ""]

    def handle_data(self, data):
        if self.in_json:
            self.json_buffer.append(data)

        if self.link is not None:
            self.link[1] += data

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.scripts.append("".join(self.json_buffer))
            self.in_json = False

        if tag == "a" and self.link is not None:
            self.links.append(tuple(self.link))
            self.link = None


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; GalerieParisLisboa/1.0)"
        }
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        content_type = response.headers.get("Content-Type", "")

        if "html" not in content_type.lower():
            return ""

        return response.read(1500000).decode("utf-8", "replace")


def nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from nodes(item)

    elif isinstance(value, dict):
        yield value

        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                yield from nodes(value[key])

        if "item" in value and isinstance(value["item"], dict):
            yield from nodes(value["item"])


def text(value):
    if isinstance(value, dict):
        return str(value.get("name") or value.get("text") or "")

    return str(value or "")


def date_value(value):
    if isinstance(value, dict):
        value = value.get("@value", "")

    value = str(value or "")
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)

    if not match:
        return None

    try:
        return date.fromisoformat(match.group()).isoformat()
    except ValueError:
        return None


def classify(value):
    value = value.lower()

    if "arquitet" in value or "architect" in value:
        return "Architecture"

    if "design" in value:
        return "Design"

    if "fotograf" in value or "photo" in value:
        return "Photography"

    if "pintura" in value or "paint" in value:
        return "Painting"

    return "Art"


def extract_events(html, page_url, city, today):
    parser = PageParser()
    parser.feed(html)

    found = []

    for script in parser.scripts:
        try:
            data = json.loads(script)
        except (ValueError, TypeError):
            continue

        for item in nodes(data):
            types = item.get("@type", [])

            if isinstance(types, str):
                types = [types]

            if not any(
                str(t).split("/")[-1].lower()
                in ("event", "exhibitionevent", "visualartsevent")
                for t in types
            ):
                continue

            title = text(item.get("name")).strip()
            description = text(item.get("description"))

            if not title:
                continue

            if not any(
                word in (title + " " + description).lower()
                for word in EXHIBITION_WORDS
            ):
                continue

            start = date_value(item.get("startDate"))
            end = date_value(item.get("endDate"))

            if not start or not end:
                continue

            if end < today or end < start:
                continue

            location = item.get("location", {})
            venue = text(location).strip()

            if not venue:
                venue = urlparse(page_url).hostname or "Venue not specified"

            link = item.get("url") or page_url

            if not isinstance(link, str):
                continue

            link = urljoin(page_url, link)

            if urlparse(link).scheme not in ("http", "https"):
                continue

            found.append([
                title,
                city,
                classify(title + " " + description),
                venue,
                start,
                end,
                link
            ])

    return found, parser.links


def main():
    today = date.today().isoformat()
    existing = []

    if OUTPUT.exists():
        try:
            existing = json.loads(
                OUTPUT.read_text(encoding="utf-8")
            ).get("events", [])
        except (OSError, ValueError, AttributeError):
            pass

    exhibitions = {}

    for event in existing:
        if (
            isinstance(event, list)
            and len(event) == 7
            and date_value(event[5])
            and event[5] >= today
        ):
            key = (
                event[0].casefold(),
                event[3].casefold()
            )
            exhibitions[key] = event

    pages_checked = 0

    for city, root in SOURCES:
        try:
            html = fetch(root)

            events, links = extract_events(
                html, root, city, today
            )

            pages_checked += 1

            for event in events:
                key = (
                    event[0].casefold(),
                    event[3].casefold()
                )
                exhibitions[key] = event

            print(
                "Checked:",
                root,
                "| exhibitions:",
                len(events)
            )

            candidates = []

            for href, label in links:
                url = urljoin(root, href)

                if (
                    urlparse(url).netloc
                    != urlparse(root).netloc
                ):
                    continue

                if any(
                    word in (url + " " + label).lower()
                    for word in LINK_WORDS
                ):
                    if url not in candidates and url != root:
                        candidates.append(url)

            for url in candidates[:MAX_LINKS_PER_SOURCE]:
                try:
                    page = fetch(url)

                    found, _ = extract_events(
                        page, url, city, today
                    )

                    pages_checked += 1

                    for event in found:
                        key = (
                            event[0].casefold(),
                            event[3].casefold()
                        )
                        exhibitions[key] = event

                    print(
                        "Checked detail:",
                        url,
                        "| exhibitions:",
                        len(found)
                    )

                except Exception as error:
                    print(
                        "Detail unavailable:",
                        url,
                        str(error)
                    )

        except Exception as error:
            print(
                "Source unavailable:",
                root,
                str(error)
            )

    results = sorted(
        exhibitions.values(),
        key=lambda event: (event[4], event[0])
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    data = {
        "project": "Galerie Paris Lisboa",
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total": len(results),
        "pages_checked": pages_checked,
        "events": results
    }

    OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print("Pages checked:", pages_checked)
    print("Total exhibitions:", len(results))

    if not results:
        print(
            "WARNING: No dated exhibition data found. "
            "Source-specific parsers needed."
        )

    print("Daily update completed.")


if __name__ == "__main__":
    main()
