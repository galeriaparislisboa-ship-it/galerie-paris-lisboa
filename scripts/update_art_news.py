#!/usr/bin/env python3
"""Publish only events supported by an official detail page and machine-readable date."""
import json,re,html
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
BASE=Path(__file__).resolve().parents[1]/'data/generators'
HEADERS={'User-Agent':'GalerieParisLisboaArtAgenda/1.1 (public event metadata)'}
def load(name,key):
    try: return json.loads((BASE/name).read_text(encoding='utf-8')).get(key,[])
    except (OSError,ValueError,AttributeError): return []
def day(v):
    m=re.match(r'^\d{4}-\d{2}-\d{2}',str(v or ''))
    try: return date.fromisoformat(m.group()) if m else None
    except ValueError: return None
def clean(v): return BeautifulSoup(html.unescape(str(v or '')),'html.parser').get_text(' ',strip=True)
def objects(obj):
    if isinstance(obj,list):
        for x in obj: yield from objects(x)
    elif isinstance(obj,dict):
        t=obj.get('@type',[]);t=[t] if isinstance(t,str) else t if isinstance(t,list) else []
        if any(str(x).split('/')[-1].endswith('Event') for x in t): yield obj
        for k in ('@graph','itemListElement','mainEntity'): yield from objects(obj.get(k,[]))
def verified(session,item):
    url=item.get('official_url') or item.get('url')
    p=urlparse(str(url or ''))
    if p.scheme!='https' or not p.hostname or len(p.path.strip('/').split('/'))<2: return False
    expected=day(item.get('date'))
    if not expected or expected<date.today(): return False
    try:
        r=session.get(url,headers=HEADERS,timeout=16);r.raise_for_status()
        if 'text/html' not in r.headers.get('Content-Type','').lower(): return False
        soup=BeautifulSoup(r.text[:1200000],'html.parser')
        title=clean(item.get('title')).casefold()
        for script in soup.find_all('script',type='application/ld+json'):
            try: data=json.loads(script.string or script.get_text())
            except (ValueError,TypeError): continue
            for event in objects(data):
                name=clean(event.get('name')).casefold()
                start=day(event.get('startDate'));end=day(event.get('endDate')) or start
                if name==title and start and end and end>=date.today() and expected in (start,end): return True
        # Fallback: explicit page title AND a machine-readable date, on the same detail page.
        og=soup.find('meta',property='og:title')
        page_title=clean((og.get('content') if og else '') or (soup.h1.get_text(' ',strip=True) if soup.h1 else '')).casefold()
        if not (title==page_title or (len(title)>=12 and title in page_title)): return False
        dates=[]
        for tag in soup.select('time[datetime],meta[itemprop="startDate"],meta[itemprop="endDate"],meta[property="event:start_time"]'):
            d=day(tag.get('datetime') or tag.get('content'))
            if d: dates.append(d)
        return expected in dates
    except requests.RequestException: return False

def main():
    BASE.mkdir(parents=True,exist_ok=True)
    candidates=load('news_candidates.json','candidates'); previous=load('news.json','news')
    published={}; rejected=0
    with requests.Session() as session:
        for item in [*previous,*candidates]:
            if not isinstance(item,dict): continue
            title=clean(item.get('title'));city=clean(item.get('city'))
            when=day(item.get('date'));url=item.get('official_url') or item.get('url')
            if not (title and city and when and when>=date.today() and isinstance(url,str)): continue
            # Revalidate both new and previously published items; no unchecked carryover.
            if not verified(session,item): rejected+=1;continue
            row={'title':title,'city':city,'venue':clean(item.get('venue')),
                 'date':when.isoformat(),'url':url}
            published[(title.casefold(),city.casefold(),row['date'])]=row
    news=sorted(published.values(),key=lambda x:(x['date'],x['city'],x['title']))
    (BASE/'news.json').write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),
        'news':news},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Published {len(news)} verified events; rejected {rejected}; examined {len(candidates)} candidates')
if __name__=='__main__':main()
