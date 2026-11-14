#!/usr/bin/env python3
"""Collecte Agenda LX via son API publique et publie data/generators/agendalx.json."""

import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://www.agendalx.pt/wp-json/agendalx/v1/events'

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / 'data'
    / 'generators'
    / 'agendalx.json'
)

PER_PAGE = 10
MAX_PAGES = 40


def plain(value):
    if isinstance(value, list):
        value = ' '.join(str(x) for x in value)

    value = re.sub(r'<[^>]+>', ' ', str(value or ''))

    return re.sub(r'\s+', ' ', unescape(value)).strip()


def fetch(page):
    query = urlencode({
        'search': '',
        'page': page,
        'per_page': PER_PAGE,
        'categories': 'artes',
        'tags': '',
        'venues': '',
        'time': '',
        'type': 'event',
    })

    request = Request(
        f'{API}?{query}',
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; GalerieParisLisboa/1.0)',
            'Accept': 'application/json',
        }
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if not isinstance(payload, list):
        raise ValueError(
            f'Page {page}: réponse inattendue '
            f'({type(payload).__name__})'
        )

    return payload


def normalize(item):
    venue_data = item.get('venue') or {}

    venues = (
        [
            v.get('name', '')
            for v in venue_data.values()
            if isinstance(v, dict)
        ]
        if isinstance(venue_data, dict)
        else []
    )

    tags_data = item.get('tags_name_list') or {}

    tags = (
        [
            v.get('name', '')
            for v in tags_data.values()
            if isinstance(v, dict)
        ]
        if isinstance(tags_data, dict)
        else []
    )

    title = plain(
        (item.get('title') or {}).get('rendered', '')
    )

    return {
        'id': str(item.get('id', '')),
        'title': title,
        'subtitle': plain(item.get('subtitle')),
        'description': plain(item.get('description')),
        'venue': ', '.join(venues),
        'location': ', '.join(venues),
        'city': 'Lisbon',
        'region': 'Lisbon',
        'country': 'Portugal',
        'start_date': item.get('StartDate') or '',
        'end_date': item.get('LastDate') or '',
        'dates': plain(item.get('string_dates')),
        'hours': plain(item.get('string_times')),
        'image': item.get('featured_media_large') or '',
        'url': item.get('link') or '',
        'source': 'Agenda LX',
        'category': 'Art',
        'discipline': 'Art',
        'tags': tags,
        'price': item.get('price_cat') or '',
    }


def main():
    collected = {}

    print(
        'Starting Agenda LX API collection',
        flush=True
    )

    for page in range(1, MAX_PAGES + 1):
        try:
            batch = fetch(page)

        except (
            HTTPError,
            URLError,
            TimeoutError,
            ValueError
        ) as exc:

            print(
                f'Page {page}: {exc}',
                flush=True
            )

            if not collected:
                raise RuntimeError(
                    'Aucune donnée récupérée : '
                    'ancien JSON conservé'
                ) from exc

            print(
                'Arrêt pagination, conservation des '
                'événements déjà récupérés',
                flush=True
            )

            break

        print(
            f'Page {page}: {len(batch)} events',
            flush=True
        )

        if not batch:
            break

        for item in batch:
            if not isinstance(item, dict):
                continue

            event = normalize(item)

            if (
                event['id']
                and event['title']
                and event['url']
            ):
                collected[event['id']] = event

        if len(batch) < PER_PAGE:
            break

        time.sleep(0.2)

    if not collected:
        raise RuntimeError(
            '0 événement : refus de remplacer '
            'le JSON existant'
        )

    events = sorted(
        collected.values(),
        key=lambda x: (
            x['end_date'],
            x['title']
        )
    )

    payload = {
        'updated_at': datetime.now(
            timezone.utc
        ).isoformat(),
        'source': API,
        'total': len(events),
        'events': events,
        'errors': [],
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tmp = OUTPUT.with_suffix('.json.tmp')

    tmp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ) + '\n',
        encoding='utf-8'
    )

    tmp.replace(OUTPUT)

    print(
        f'Saved {len(events)} Agenda LX '
        f'events to {OUTPUT}',
        flush=True
    )


if __name__ == '__main__':
    main()
