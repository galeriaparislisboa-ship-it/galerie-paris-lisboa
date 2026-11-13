#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Galerie Paris–Lisboa
Agenda LX Event Collector

Collecte les événements artistiques d'Agenda LX :
- Titre
- Dates
- Lieu
- Image
- URL officielle

Résultat :
data/generators/agendalx.json
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE = "https://www.agendalx.pt"

START = (
    "https://www.agendalx.pt/"
    "?categories=artes&s=&type=event&archive=artes"
)

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "generators"
    / "agendalx.json"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GalerieParisLisboa/1.0)"
}


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def absolute(url, base=BASE):
    if not url:
        return ""

    return urljoin(base, str(url).strip())


def get_page(session, url):
    response = session.get(
        url,
        headers=HEADERS,
        timeout=25
    )

    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


def get_meta(soup, name):
    tag = soup.find("meta", property=name)

    if not tag:
        tag = soup.find("meta", attrs={"name": name})

    if tag:
        return clean(tag.get("content"))

    return ""


def get_image(soup, url):
    image = get_meta(soup, "og:image")

    if image:
        return absolute(image, url)

    selectors = [
        "article img",
        ".event img",
        ".event-image img",
        ".featured-image img",
        "main img"
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            image = (
                element.get("data-src")
                or element.get("data-lazy-src")
                or element.get("src")
            )

            if image and not image.startswith("data:"):
                return absolute(image, url)

    return ""


def extract_dates(soup):
    dates = []

    for element in soup.select("time[datetime]"):
        value = element.get("datetime", "")

        match = re.search(
            r"\d{4}-\d{2}-\d{2}",
            value
        )

        if match:
            dates.append(match.group(0))

    for script in soup.select(
        'script[type="application/ld+json"]'
    ):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue

        objects = data if isinstance(data, list) else [data]

        for obj in objects:
            if not isinstance(obj, dict):
                continue

            objects_to_check = [obj]

            if isinstance(obj.get("@graph"), list):
                objects_to_check += obj["@graph"]

            for item in objects_to_check:
                if not isinstance(item, dict):
                    continue

                for key in ("startDate", "endDate"):
                    value = item.get(key, "")

                    match = re.search(
                        r"\d{4}-\d{2}-\d{2}",
                        str(value)
                    )

                    if match:
                        dates.append(match.group(0))

    if dates:
        return dates[0], dates[-1]

    return "", ""


def extract_venue(soup):
    selectors = [
        ".event-location",
        ".event-venue",
        ".location",
        ".venue",
        '[class*="venue"]',
        '[class*="location"]'
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            value = clean(
                element.get_text(" ", strip=True)
            )

            if value:
                return value[:160]

    return ""


def extract_event(session, url):
    soup = get_page(session, url)

    h1 = soup.find("h1")

    title = (
        clean(h1.get_text(" ", strip=True))
        if h1
        else get_meta(soup, "og:title")
    )

    image = get_image(soup, url)

    start, end = extract_dates(soup)

    venue = extract_venue(soup)

    if not title:
        return None

    return {
        "title": title,
        "city": "Lisboa",
        "venue": venue,
        "category": "Art",
        "start": start,
        "end": end or start,
        "url": url,
        "image": image,
        "source": "Agenda LX",
        "date_verified": bool(start)
    }


def discover_events(soup):
    events = []

    for link in soup.select("a[href]"):
        href = link.get("href", "")

        url = absolute(href)

        parsed = urlparse(url)

        if parsed.hostname not in (
            "agendalx.pt",
            "www.agendalx.pt"
        ):
            continue

        if "/events/event/" not in parsed.path:
            continue

        url = url.split("#")[0]

        if url not in events:
            events.append(url)

    return events


def main():
    session = requests.Session()

    events = {}
    errors = []

    print("Starting Agenda LX collection")

    try:
        soup = get_page(session, START)

        links = discover_events(soup)

        print("Event links found:", len(links))

        for index, url in enumerate(links, start=1):
            try:
                event = extract_event(session, url)

                if event and event["title"]:
                    events[url] = event

                    print(
                        index,
                        event["title"],
                        "image:",
                        bool(event["image"]),
                        "date:",
                        bool(event["start"])
                    )

            except Exception as error:
                errors.append(
                    f"{url}: {str(error)[:150]}"
                )

            time.sleep(0.2)

    except Exception as error:
        errors.append(str(error))

    payload = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": START,
        "total": len(events),
        "events": list(events.values()),
        "errors": errors[:30]
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Conserver les anciennes données si
    # une collecte temporaire échoue.
    if OUTPUT.exists() and not events:
        try:
            previous = json.loads(
                OUTPUT.read_text(encoding="utf-8")
            )

            if previous.get("events"):
                print(
                    "No new events. "
                    "Keeping previous data."
                )
                return

        except (OSError, ValueError):
            pass

    OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        "Saved",
        len(events),
        "Agenda LX events"
    )


if __name__ == "__main__":
    main()
