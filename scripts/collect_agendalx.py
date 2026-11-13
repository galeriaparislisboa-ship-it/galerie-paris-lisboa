#!/usr/bin/env python3
"""Collect public Agenda LX arts event metadata and image URLs.
No bypassing access controls; images remain hosted by their publishers.
"""
import json
import re
import time
import html
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

BASE = "https://www.agendalx.pt/"
START = BASE + "?categories=artes&s=&type=event&archive=artes"
OUT = Path(__file__).resolve().parents[1] / "data/generators/agendalx.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GalerieParisLisboa/1.0; cultural event indexing)"}
MONTHS = {"janeiro":1,"fevereiro":2,"março":3,"marco":3,"abril":4,"maio":5,"junho":6,
          "julho":7,"agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True))).strip()

def absolute(value, base):
    if not value:
        return ""
    url = urljoin(base, str(value).strip())
    return url if urlparse(url).scheme in ("https", "http") else ""

def fetch(session, url):
    response = session.get(url, timeout=25, headers=HEADERS)
    response.raise_for_status()
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("Expected HTML, got " + response.headers.get("Content-Type", "?"))
    return BeautifulSoup(response.text, "html.parser")

def meta(soup, key):
    tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
    return (tag.get("content") or "").strip() if tag else ""

def image_from(node, base):
    if node is None:
        return ""
    for img in node.select("img"):
        for key in ("data-src", "data-lazy-src", "data-original", "src"):
            value = img.get(key, "")
            if value and not value.startswith("data:"):
                return absolute(value, base)
        srcset = img.get("data-srcset") or img.get("srcset") or ""
        if srcset:
            return absolute(srcset.split(",")[0].strip().split(" ")[0], base)
    return ""

def json_events(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            typ = value.get("@type", [])
            types = [typ] if isinstance(typ, str) else typ if isinstance(typ, list) else []
            if any("Event" in str(t) for t in types):
                yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from walk(child)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue

def date_part(value):
    match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", str(value or ""))
    return match.group(0) if match else ""

def dates_from_text(value):
    text = clean(value).lower()
    matches = re.findall(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(MONTHS) + r")\s+(?:de\s+)?(20\d{2})\b", text)
    dates = []
    for day, month, year in matches:
        try:
            dates.append(f"{int(year):04d}-{MONTHS[month]:02d}-{int(day):02d}")
        except ValueError:
            pass
    return (dates[0] if dates else "", dates[-1] if dates else "")

def detail(session, url, listing_image="", listing_title=""):
    soup = fetch(session, url)
    event = next(iter(json_events(soup)), {})
    h1 = soup.find("h1")
    title = clean(event.get("name") or (h1.get_text(" ", strip=True) if h1 else "") or
                  meta(soup, "og:title") or listing_title)
    image = event.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl") or ""
    image = absolute(image or meta(soup, "og:image") or image_from(soup.find("article") or soup, url) or listing_image, url)
    start = date_part(event.get("startDate"))
    end = date_part(event.get("endDate"))
    if not start:
        for element in soup.select("time[datetime]"):
            start = date_part(element.get("datetime"))
            if start:
                break
    if not start:
        for element in soup.select('[class*="date"], [class*="data"], [class*="when"]'):
            start, end = dates_from_text(element.get_text(" ", strip=True))
            if start:
                break
    location = event.get("location") or {}
    venue = clean(location.get("name")) if isinstance(location, dict) else ""
    if not venue:
        venue_el = soup.select_one('[class*="venue"], [class*="local"], [class*="location"]')
        venue = clean(venue_el.get_text(" ", strip=True))[:140] if venue_el else ""
    return {"title": title, "city": "Lisboa", "venue": venue, "category": "Art",
            "start": start, "end": end or start, "url": url, "image": image,
            "source": "Agenda LX", "date_verified": bool(start)}

def discover(soup, listing_url):
    """Do not assume event permalinks contain /evento/; discover card links too."""
    results = {}
    selectors = [
        "article a[href]", ".event a[href]", '[class*="event"] a[href]',
        '[class*="card"] a[href]', '[class*="post"] a[href]',
        '[class*="item"] a[href]', "main a[href]"
    ]
    anchors = []
    for selector in selectors:
        anchors.extend(soup.select(selector))
    if not anchors:
        anchors = soup.select("a[href]")
    excluded = ("/wp-", "/category/", "/categoria/", "/tag/", "/author/",
                "/contact", "/sobre", "/agenda/", "/privacy", "/politica")
    for anchor in anchors:
        url = urldefrag(absolute(anchor.get("href"), listing_url))[0]
        parsed = urlparse(url)
        if parsed.hostname not in ("agendalx.pt", "www.agendalx.pt"):
            continue
        path = parsed.path.rstrip("/")
        if not path or path == "/" or any(path.startswith(x) for x in excluded):
            continue
        if parsed.query and "paged=" in parsed.query:
            continue
        container = anchor.find_parent(["article", "li"]) or anchor.find_parent(
            class_=re.compile(r"card|event|post|item|result", re.I))
        title = clean(anchor.get_text(" ", strip=True))
        if container:
            heading = container.find(re.compile("^h[1-6]$"))
            title = clean(heading.get_text(" ", strip=True)) if heading else title
        if len(title) < 3:
            continue
        img = image_from(container or anchor, listing_url)
        if url not in results or (img and not results[url]["image"]):
            results[url] = {"url": url, "title": title, "image": img}
    return list(results.values())

def main():
    session = requests.Session()
    existing = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    found = {}
    errors = []
    page_stats = []
    for page in range(1, 11):
        url = START + (f"&paged={page}" if page > 1 else "")
        try:
            soup = fetch(session, url)
        except Exception as exc:
            errors.append(f"Listing page {page}: {exc}")
            break
        links = discover(soup, url)
        page_stats.append({"page": page, "candidate_links": len(links)})
        print(f"Page {page}: {len(links)} candidate links")
        if not links:
            errors.append(f"No candidate links on listing page {page}; inspect page HTML/selectors")
            break
        added = 0
        for candidate in links:
            link = candidate["url"]
            if link in found:
                continue
            try:
                item = detail(session, link, candidate["image"], candidate["title"])
                if item["title"] and item["image"]:
                    found[link] = item
                    added += 1
            except Exception as exc:
                if len(errors) < 30:
                    errors.append(f"{link}: {str(exc)[:140]}")
            time.sleep(0.15)
        print(f"Page {page}: {added} events with images; {sum(bool(x['start']) for x in found.values())} dated")
        if page > 1 and not added:
            break
        time.sleep(0.3)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "source": START,
               "events": list(found.values()), "errors": errors[:30], "diagnostics": page_stats}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not found and existing.get("events"):
        print("No new events; preserving existing non-empty file")
        return
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(found)} Agenda LX entries ({sum(bool(x['start']) for x in found.values())} dated) to {OUT}")
    if not found:
        print("WARNING: zero events. Inspect diagnostics and source HTML; no extraction is confirmed.")

if __name__ == "__main__":
    main()
