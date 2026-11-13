#!/usr/bin/env python3
"""Publish current art events with a valid, dedicated official event page.

Automatically validate candidate metadata against JSON-LD on its event detail
page. Manual verified=True remains supported for reviewed legacy entries.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1] / 'data' / 'generators'
HEADERS = {'User-Agent': 'GalerieParisLisboaArtAgenda/1.0 (public event metadata)'}

def load(name, key):
    try:
        data = json.loads((BASE / name).read_text(encoding='utf-8'))
        return data.get(key, []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []

def day(value):
    if not isinstance(value, str):
        return None
    match = re.match(r'^\d{4}-\d{2}-\d{2}', value)
    try:
        return date.fromisoformat(match.group()) if match else None
    except ValueError:
        return None

def objects(value):
    if isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
        if any(str(t).split('/')[-1].endswith('Event') for t in types):
            yield value
        for field in ('@graph', 'itemListElement'):
            yield from objects(value.get(field, []))

def validate(session, item):
    url = item.get('official_url') or item.get('url')
    if not isinstance(url, str) or urlparse(url).scheme != 'https' or not urlparse(url).hostname:
        return False
    if item.get('verified') is True:
        return bool(day(item.get('date')) and day(item['date']) >= date.today())
    try:
        response = session.get(url, headers=HEADERS, timeout=18)
        response.raise_for_status()
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            return False
        soup = BeautifulSoup(response.text[:1_500_000], 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or script.get_text())
            except (TypeError, ValueError):
                continue
            for event in objects(data):
                name = event.get('name')
                if not isinstance(name, str):
                    continue
                title = BeautifulSoup(name, 'html.parser').get_text(' ', strip=True)
                start = day(event.get('startDate'))
                end = day(event.get('endDate')) or start
                expected = day(item.get('date'))
                if (title.casefold() == str(item.get('title', '')).casefold() and start and end
                        and end >= date.today() and expected in (start, end)):
                    return True
    except requests.RequestException:
        return False
    return False

def main():
    BASE.mkdir(parents=True, exist_ok=True)
    candidates = load('news_candidates.json', 'candidates')
    previous = load('news.json', 'news')
    published = {}
    with requests.Session() as session:
        for item in [*previous, *candidates]:
            if not isinstance(item, dict):
                continue
            title, city = item.get('title'), item.get('city')
            when = day(item.get('date'))
            url = item.get('official_url') or item.get('url')
            if not (isinstance(title, str) and title.strip() and isinstance(city, str) and city.strip()
                    and when and when >= date.today() and isinstance(url, str)):
                continue
            # Previously published events are not reverified unless source candidate is available.
            if item in candidates and not validate(session, item):
                continue
            if item not in candidates and urlparse(url).scheme != 'https':
                continue
            clean = {'title': BeautifulSoup(title, 'html.parser').get_text(' ', strip=True),
                     'city': city.strip(), 'venue': str(item.get('venue') or '').strip(),
                     'date': when.isoformat(), 'url': url}
            published[(clean['title'].casefold(), clean['city'].casefold(), clean['date'])] = clean
    news = sorted(published.values(), key=lambda x: (x['date'], x['city'], x['title']))
    (BASE / 'news.json').write_text(json.dumps({'updated_at': datetime.now(timezone.utc).isoformat(),
                                                'news': news}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {len(news)} verified events; {len(candidates)} candidates examined')

if __name__ == '__main__':
    main()
