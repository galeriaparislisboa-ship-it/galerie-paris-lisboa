#!/usr/bin/env python3
"""Discover events on official venue pages, including linked detail pages.
No automatic trust of agenda-level dates; verification occurs on detail page.
"""
import json, re, html, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/generators/news_candidates.json'
SOURCES = [
 ('Gulbenkian','Lisboa','https://gulbenkian.pt/agenda/'),
 ('CAM Gulbenkian','Lisboa','https://gulbenkian.pt/cam/en/agenda/'),
 ('MAAT','Lisboa','https://www.maat.pt/en/agenda'),
 ('Serralves','Porto','https://www.serralves.pt/agenda-serralves/'),
 ('CCB','Lisboa','https://www.ccb.pt/'),
 ('Museu Nacional de Arte Contemporânea','Lisboa','https://www.museuartecontemporanea.gov.pt/'),
 ('Museu de Arte Contemporânea de Elvas','Elvas','https://www.cm-elvas.pt/'),
 ('Culturgest','Lisboa','https://www.culturgest.pt/'),
]
HEADERS={'User-Agent':'GalerieParisLisboaArtAgenda/1.1 (public event metadata)'}
KEYWORDS=('expos','exhib','agenda','event','program','programme','mostra','arte','artes','gallery','galeria')
MAX_LINKS=22

def day(v):
    m=re.match(r'^\d{4}-\d{2}-\d{2}',str(v or ''))
    try: return date.fromisoformat(m.group()) if m else None
    except ValueError: return None

def clean(v):
    return BeautifulSoup(html.unescape(str(v or '')),'html.parser').get_text(' ',strip=True)

def events(obj):
    if isinstance(obj,list):
        for v in obj: yield from events(v)
    elif isinstance(obj,dict):
        types=obj.get('@type',[])
        types=[types] if isinstance(types,str) else types if isinstance(types,list) else []
        if any(str(t).split('/')[-1].endswith('Event') for t in types): yield obj
        for k in ('@graph','itemListElement','mainEntity'): yield from events(obj.get(k,[]))

def same_site(link,source):
    p,b=urlparse(link),urlparse(source)
    return p.scheme=='https' and p.hostname and p.hostname.removeprefix('www.')==b.hostname.removeprefix('www.')

def json_events(soup):
    for script in soup.find_all('script',type='application/ld+json'):
        try: data=json.loads(script.string or script.get_text())
        except (TypeError,ValueError): continue
        yield from events(data)

def extract(soup,url,venue,city):
    result=[]
    for event in json_events(soup):
        title=clean(event.get('name'))
        start=day(event.get('startDate')); end=day(event.get('endDate')) or start
        if not (4<=len(title)<=180 and start and end and end>=date.today()): continue
        event_url=urljoin(url,str(event.get('url') or url))
        if not same_site(event_url,url): continue
        result.append({'title':title,'city':city,'venue':venue,
                       'date':(start if start>=date.today() else end).isoformat(),
                       'official_url':event_url,'verified':False,'discovered_from':url})
    # A dedicated detail page may have no JSON-LD; use page title + explicit machine-readable date.
    if not result:
        canonical=soup.find('link',rel='canonical')
        title_meta=soup.find('meta',property='og:title')
        title=clean((title_meta.get('content') if title_meta else None) or (soup.h1.get_text(' ',strip=True) if soup.h1 else ''))
        dates=[]
        for tag in soup.select('time[datetime], meta[property="article:published_time"], meta[itemprop="startDate"], meta[itemprop="endDate"], meta[property="event:start_time"]'):
            d=day(tag.get('datetime') or tag.get('content'))
            if d: dates.append(d)
        future=[d for d in dates if d>=date.today()]
        if 5<=len(title)<=160 and future and len(urlparse(url).path.strip('/').split('/'))>=2:
            link=urljoin(url,canonical.get('href')) if canonical and canonical.get('href') else url
            if same_site(link,url):
                result.append({'title':title,'city':city,'venue':venue,'date':max(future).isoformat(),
                               'official_url':link,'verified':False,'discovered_from':url})
    return result

def get(session,url):
    r=session.get(url,headers=HEADERS,timeout=16);r.raise_for_status()
    if 'text/html' not in r.headers.get('Content-Type','').lower(): return None
    return BeautifulSoup(r.text[:1200000],'html.parser')

def discover_links(soup,source):
    ranked=[]; seen=set()
    for a in soup.select('a[href]'):
        url=urldefrag(urljoin(source,a.get('href','')))[0]
        if not same_site(url,source) or url in seen or url.rstrip('/')==source.rstrip('/'): continue
        p=urlparse(url)
        if p.path.lower().endswith(('.pdf','.jpg','.png','.webp','.zip')): continue
        label=clean(a.get_text(' ',strip=True))
        score=sum(k in (p.path+' '+label).lower() for k in KEYWORDS)
        if score==0 or len(label)>180: continue
        seen.add(url); ranked.append((score,url))
    return [u for _,u in sorted(ranked,key=lambda x:-x[0])[:MAX_LINKS]]

def main():
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    try: old=json.loads(OUTPUT.read_text(encoding='utf-8')).get('candidates',[])
    except (OSError,ValueError,AttributeError): old=[]
    unique={}
    for item in old:
        if isinstance(item,dict) and item.get('title') and item.get('date'):
            unique[(clean(item['title']).casefold(),str(item.get('city','')).casefold(),str(item['date']))]=item
    with requests.Session() as session:
        for venue,city,source in SOURCES:
            found=[]
            try:
                soup=get(session,source)
                if soup:
                    found.extend(extract(soup,source,venue,city))
                    for link in discover_links(soup,source):
                        try:
                            detail=get(session,link)
                            if detail: found.extend(extract(detail,link,venue,city))
                        except requests.RequestException: pass
                        time.sleep(.12)
                for item in found:
                    key=(item['title'].casefold(),item['city'].casefold(),item['date'])
                    if key not in unique: unique[key]=item
                print(f'{venue}: {len(found)} event records found')
            except requests.RequestException as exc: print(f'{venue}: unavailable ({type(exc).__name__})')
    OUTPUT.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),
        'candidates':sorted(unique.values(),key=lambda x:(str(x.get('date','')),str(x.get('title',''))))},
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(unique)} total candidates; publication independently checks official detail pages')
if __name__=='__main__': main()
