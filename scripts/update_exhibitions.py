import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, date
from html.parser import HTMLParser
from urllib.parse import urlparse

OUTPUT = Path("data/generators/exhibitions.json")

SOURCES = [
    ("Lisboa", "https://www.ccb.pt/"),
    ("Lisboa", "https://gulbenkian.pt/"),
    ("Lisboa", "https://www.maat.pt/"),
    ("Porto", "https://www.serralves.pt/"),
    ("Lisboa", "https://www.saomamede.com/listagem/exposicoes"),
]

KEYWORDS = (
    "exposi", "exhibition", "pintura", "painting",
    "arte", "art", "design", "arquitet",
    "architect", "fotograf", "photograph"
)


class JSONLDScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.buffer = ""
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self.inside = True
            self.buffer = ""

    def handle_data(self, data):
        if self.inside:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self.inside:
            self.scripts.append(self.buffer)
            self.inside = False


def extract_nodes(data):
    if isinstance(data, list):
        for item in data:
            yield from extract_nodes(item)

    elif isinstance(data, dict):
        yield data

        for item in data.get("@graph", []):
            yield from extract_nodes(item)


def text_value(value):
    if isinstance(value, dict):
        return str(value.get("name", ""))

    return str(value or "")


def valid_date(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError, TypeError):
        return None


def category(text):
    text = text.lower()

    if "architect" in text or "arquitet" in text:
        return "Architecture"

    if "design" in text:
        return "Design"

    if "photo" in text or "fotograf" in text:
        return "Photography"

    if "paint" in text or "pintura" in text:
        return "Painting"

    return "Art"


def fetch_page(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GalerieParisLisboaExhibitionFinder/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read(1200000).decode("utf-8", "replace")


def main():
    today = date.today().isoformat()

    existing = {"events": []}

    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    exhibitions = {}

    for event in existing.get("events", []):
        if (
            isinstance(event, list)
            and len(event) == 7
            and valid_date(event[5])
            and event[5] >= today
        ):
            key = (event[0].lower(), event[3].lower())
            exhibitions[key] = event

    new_count = 0

    for city, source_url in SOURCES:
        try:
            html = fetch_page(source_url)

            parser = JSONLDScripts()
            parser.feed(html)

            for script in parser.scripts:
                try:
                    data = json.loads(script)
                except (ValueError, TypeError):
                    continue

                for item in extract_nodes(data):
                    types = item.get("@type", [])

                    if isinstance(types, str):
                        types = [types]

                    if not any(
                        t in ("Event", "ExhibitionEvent", "VisualArtsEvent")
                        for t in types
                    ):
                        continue

                    title = text_value(item.get("name")).strip()
                    description = text_value(item.get("description"))

                    searchable = (title + " " + description).lower()

                    if not title:
                        continue

                    if not any(word in searchable for word in KEYWORDS):
                        continue

                    start = valid_date(item.get("startDate"))
                    end = valid_date(item.get("endDate"))

                    if not start or not end:
                        continue

                    if end < today or end < start:
                        continue

                    location = item.get("location", {})
                    venue = text_value(location)

                    if not venue:
                        continue

                    link = item.get("url") or source_url

                    if not isinstance(link, str):
                        continue

                    if urlparse(link).scheme not in ("http", "https"):
                        continue

                    event = [
                        title,
                        city,
                        category(searchable),
                        venue,
                        start,
                        end,
                        link
                    ]

                    key = (title.lower(), venue.lower())

                    if key not in exhibitions:
                        new_count += 1

                    exhibitions[key] = event

            print("Checked:", source_url)

        except Exception as error:
            print("Source unavailable:", source_url, str(error))

    results = sorted(
        exhibitions.values(),
        key=lambda event: (event[4], event[0])
    )

    data = {
        "project": "Galerie Paris Lisboa",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "new_exhibitions": new_count,
        "events": results
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Total exhibitions:", len(results))
    print("New exhibitions:", new_count)
    print("Daily update completed.")


if __name__ == "__main__":
    main()
