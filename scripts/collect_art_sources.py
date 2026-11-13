#!/usr/bin/env python3
"""Discover dated art-event candidates from official Portuguese venue pages.

Only JSON-LD Event/ExhibitionEvent structured data is accepted. This is a
conservative discovery stage, NOT an Instagram scraper or automatic verification.
Candidates remain verified=False until reviewed, as required by update_art_news.py.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'generators' / 'news_candidates.json'
SOURCES = [
    ('Gulbenkian', 'Lisboa', 'https://gulbenkian.pt/agenda/'),
    ('CAM Gulbenkian', 'Lisboa', 'https://gulbenkian.pt/cam/en/agenda/'),
    ('MAAT', 'Lisboa', 'https://www.maat.pt/en/agenda'),
    ('Serralves', 'Porto', 'https://www.serralves.pt/agenda-serralves/'),
    ('CCB', 'Lisboa', 'https://www.ccb.pt/'),
    ('Museu Nacional de Arte Contemporânea', 'Lisboa', 'https://www.museuartecontemporanea.gov.pt/'),
    ('Museu de Arte Contemporânea de Elvas', 'Elvas', 'https://www.cm-elvas.pt/'),
    ('Culturgest', 'Lisboa', 'https://www.culturgest.pt/'),
]
HEADERS = {'User-Agent': 'GalerieParisLisboaArtAgenda/1.0 (public event metadata; respectful crawler)'}


def event_objects(value):
    if isinstance(value, list):
        for child in value:
            yield from event_objects(child)
    elif isinstance(value, dict):
        typ = value.get('@type', [])
        types = [typ] if isinstance(typ, str) else typ if isinstance(typ, list) else []
        if any(str(t).endswith('Event') for t in types):
            yield value
        for key in ('@graph', 'itemListElement'):
            if key in value:
                yield from event_objects(value[key])


def parse_day(value):
    if not isinstance(value, str):
        return None
    match = re.match(r'^\d{4}-\d{2}-\d{2}', value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group())
    except ValueError:
        return None


def official_link(link, base):
    if not isinstance(link, str):
        return base
    full = urljoin(base, link)
    parsed, origin = urlparse(full), urlparse(base)
    return full if parsed.scheme == 'https' and parsed.hostname == origin.hostname else base


def fetch_source(session, venue, city, url):
    response = session.get(url, headers=HEADERS, timeout=18)
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type', '').lower():
        return []
    soup = BeautifulSoup(response.text[:1_500_000], 'html.parser')
    rows = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for event in event_objects(data):
            start = parse_day(event.get('startDate'))
            end = parse_day(event.get('endDate')) or start
            title = event.get('name')
            if not (start and end and end >= date.today() and isinstance(title, str) and 4 <= len(title.strip()) <= 180):
                continue
            # Use start date for future events, end date for ongoing exhibitions.
            day = start if start >= date.today() else end
            rows.append({'title': title.strip(), 'city': city, 'venue': venue,
                         'date': day.isoformat(), 'official_url': official_link(event.get('url'), url),
                         'verified': False, 'discovered_from': url})
    return rows


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(OUTPUT.read_text(encoding='utf-8'))
        candidates = existing.get('candidates', []) if isinstance(existing, dict) else []
    except (OSError, ValueError):
        candidates = []
    unique = {}
    for item in candidates:
        if isinstance(item, dict) and item.get('title') and item.get('date'):
            unique[(item['title'].casefold(), item.get('city', '').casefold(), item['date'])] = item
    with requests.Session() as session:
        for venue, city, url in SOURCES:
            try:
                found = fetch_source(session, venue, city, url)
                print(f'{venue}: {len(found)} structured events found')
                for item in found:
                    key = (item['title'].casefold(), item['city'].casefold(), item['date'])
                    unique.setdefault(key, item)  # Never override human verification
            except requests.RequestException as exc:
                print(f'{venue}: unavailable ({type(exc).__name__})')
    output = {'updated_at': datetime.now(timezone.utc).isoformat(),
              'candidates': sorted(unique.values(), key=lambda x: (x.get('date', ''), x.get('title', '')))}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(output["candidates"])} candidates; review verified=false entries before publication')


if __name__ == '__main__':
    main()
