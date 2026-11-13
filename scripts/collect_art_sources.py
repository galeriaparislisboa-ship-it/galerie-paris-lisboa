#!/usr/bin/env python3
"""Collect official event metadata; retain reviewable provenance.

Automatic verification requires a dedicated official event URL and a date from
JSON-LD. A venue's generic agenda page is not sufficient proof of an event.
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
HEADERS = {'User-Agent': 'GalerieParisLisboaArtAgenda/1.0 (public event metadata)'}

def events(obj):
    if isinstance(obj, list):
        for value in obj:
            yield from events(value)
    elif isinstance(obj, dict):
        types = obj.get('@type', [])
        types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
        if any(str(t).split('/')[-1].endswith('Event') for t in types):
            yield obj
        for field in ('@graph', 'itemListElement'):
            yield from events(obj.get(field, []))

def day(value):
    if not isinstance(value, str):
        return None
    match = re.match(r'^\d{4}-\d{2}-\d{2}', value)
    try:
        return date.fromisoformat(match.group()) if match else None
    except ValueError:
        return None

def event_url(value, source):
    if not isinstance(value, str) or not value.strip():
        return None
    url = urljoin(source, value.strip())
    parsed, origin = urlparse(url), urlparse(source)
    if parsed.scheme != 'https' or parsed.hostname != origin.hostname:
        return None
    if parsed.path.rstrip('/') == origin.path.rstrip('/'):
        return None
    return url

def collect(session, venue, city, source):
    response = session.get(source, headers=HEADERS, timeout=18)
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type', '').lower():
        return []
    soup = BeautifulSoup(response.text[:1_500_000], 'html.parser')
    found = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            obj = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        for event in events(obj):
            start = day(event.get('startDate'))
            end = day(event.get('endDate')) or start
            title = event.get('name')
            url = event_url(event.get('url'), source)
            if not (start and end and end >= date.today() and url and isinstance(title, str)
                    and 4 <= len(title.strip()) <= 180):
                continue
            found.append({'title': BeautifulSoup(title, 'html.parser').get_text(' ', strip=True),
                          'city': city, 'venue': venue,
                          'date': (start if start >= date.today() else end).isoformat(),
                          'official_url': url, 'verified': False, 'discovered_from': source})
    return found

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        old = json.loads(OUTPUT.read_text(encoding='utf-8')).get('candidates', [])
    except (OSError, ValueError, AttributeError):
        old = []
    unique = {}
    for item in old:
        if isinstance(item, dict) and item.get('title') and item.get('date'):
            unique[(item['title'].casefold(), str(item.get('city', '')).casefold(), item['date'])] = item
    with requests.Session() as session:
        for venue, city, source in SOURCES:
            try:
                items = collect(session, venue, city, source)
                print(f'{venue}: {len(items)} eligible event candidates')
                for item in items:
                    key = (item['title'].casefold(), item['city'].casefold(), item['date'])
                    unique.setdefault(key, item)
            except requests.RequestException as exc:
                print(f'{venue}: unavailable ({type(exc).__name__})')
    # Preserve manually reviewed items, but never infer verification from a generic agenda URL.
    output = {'updated_at': datetime.now(timezone.utc).isoformat(),
              'candidates': sorted(unique.values(), key=lambda x: (str(x.get('date', '')), str(x.get('title', ''))))}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(unique)} candidates retained')

if __name__ == '__main__':
    main()
