#!/usr/bin/env python3
"""Curated, source-verified art news. No Instagram scraping or credentials.

Candidate discoveries may originate from Instagram, but publication requires an
independent official event/venue URL and a verified date. No third-party text/images copied.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1] / 'data' / 'generators'
TODAY = date.today()

def https(url):
    return isinstance(url, str) and urlparse(url).scheme == 'https' and bool(urlparse(url).netloc)

def load(path, key):
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj.get(key, []) if isinstance(obj, dict) else []
    except (OSError, ValueError):
        return []

def iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None

def main():
    BASE.mkdir(parents=True, exist_ok=True)
    candidates = load(BASE / 'news_candidates.json', 'candidates')
    previous = load(BASE / 'news.json', 'news')
    published = {}
    for item in [*previous, *candidates]:
        if not isinstance(item, dict):
            continue
        # official_url must be the gallery / museum / organizer page, not an Instagram post.
        url = item.get('official_url') or item.get('url')
        event_date = iso(item.get('date'))
        title, city = item.get('title'), item.get('city')
        if not (isinstance(title, str) and title.strip() and isinstance(city, str) and city.strip()
                and https(url) and event_date and event_date >= TODAY):
            continue
        # New candidates require a human confirmation of official source and dates.
        if item in candidates and item.get('verified') is not True:
            continue
        clean = {'title': title.strip(), 'city': city.strip(), 'venue': str(item.get('venue') or '').strip(),
                 'date': event_date.isoformat(), 'url': url}
        published[(clean['title'].casefold(), clean['city'].casefold(), clean['date'])] = clean
    news = sorted(published.values(), key=lambda x: (x['date'], x['city'], x['title']))
    output = {'updated_at': datetime.now(timezone.utc).isoformat(), 'news': news}
    (BASE / 'news.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {len(news)} confirmed current/upcoming news items')

if __name__ == '__main__':
    main()
