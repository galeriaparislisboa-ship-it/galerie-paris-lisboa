#!/usr/bin/env python3
"""Best-effort Agenda LX ARTES importer; keeps existing exhibition data intact.
Public metadata only. Image links are stored only if available; check reuse rights.
"""
import json, re, html, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE='https://www.agendalx.pt/'
START='https://www.agendalx.pt/?categories=artes&s=&type=event&archive=artes'
OUT=Path(__file__).resolve().parents[1]/'data/generators/agendalx.json'
HEAD={'User-Agent':'GalerieParisLisboa/1.0 (public cultural metadata; contact via website)'}

def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',str(s or '')))).strip()
def get(session,url):
 r=session.get(url,timeout=18,headers=HEAD);r.raise_for_status()
 if 'html' not in r.headers.get('content-type','').lower(): raise ValueError('Not HTML')
 return BeautifulSoup(r.text,'html.parser')
def absolute(url,base):
 if not url:return ''
 u=urljoin(base,url)
 return u if urlparse(u).scheme in ('https','http') else ''
def meta(soup,prop):
 el=soup.find('meta',property=prop) or soup.find('meta',attrs={'name':prop})
 return el.get('content','') if el else ''
def event_nodes(data):
 if isinstance(data,list):
  for v in data:yield from event_nodes(v)
 elif isinstance(data,dict):
  t=data.get('@type',[]);ts=[t] if isinstance(t,str) else t if isinstance(t,list) else []
  if any('Event' in str(x) for x in ts):yield data
  for k in ('@graph','itemListElement'):
   if k in data:yield from event_nodes(data[k])
def ld_events(soup):
 for node in soup.find_all('script',type='application/ld+json'):
  try:
   for event in event_nodes(json.loads(node.string or node.get_text())):yield event
  except (ValueError,TypeError):pass
def datepart(v):
 if not isinstance(v,str):return ''
 m=re.match(r'^\d{4}-\d\d-\d\d',v)
 return m.group() if m else ''
def extract(session,url):
 soup=get(session,url)
 title=clean(meta(soup,'og:title') or (soup.find('h1').get_text(' ',strip=True) if soup.find('h1') else ''))
 img=absolute(meta(soup,'og:image'),url)
 candidates=list(ld_events(soup));e=candidates[0] if candidates else {}
 title=clean(e.get('name') or title)
 image=e.get('image') or img
 if isinstance(image,list):image=image[0] if image else ''
 if isinstance(image,dict):image=image.get('url','')
 image=absolute(image,url)
 start=datepart(e.get('startDate'));end=datepart(e.get('endDate')) or start
 loc=e.get('location') or {};venue=clean(loc.get('name','')) if isinstance(loc,dict) else ''
 return {'title':title,'city':'Lisboa','venue':venue,'category':'Art','start':start,'end':end,'url':url,'image':image,'source':'Agenda LX','date_verified':bool(start and end)}
def discover(soup):
 links=[]
 for a in soup.select('a[href]'):
  url=absolute(a.get('href'),BASE);p=urlparse(url)
  if p.hostname not in ('www.agendalx.pt','agendalx.pt'):continue
  if not p.path or p.path=='/' or '/wp-' in p.path:continue
  if any(x in p.path for x in ('/evento/','/event/','/exposicao/','/exposicoes/')):links.append(url.split('#')[0])
 return list(dict.fromkeys(links))
def main():
 session=requests.Session();seen={};errors=[]
 # Traverse public category pagination conservatively; do not bypass access controls.
 for page in range(1,16):
  url=START+('&paged='+str(page) if page>1 else '')
  try:soup=get(session,url)
  except Exception as e:errors.append('Page '+str(page)+': '+str(e)[:100]);break
  links=discover(soup)
  if not links:break
  added=0
  for link in links:
   if link in seen:continue
   try:
    item=extract(session,link)
    if item['title'] and item['image'] and item['start']:
     seen[link]=item;added+=1
   except Exception as e:errors.append(link+': '+str(e)[:80])
   time.sleep(.15)
  print('Page',page,'links',len(links),'new dated events with images',added)
  if page>1 and not added:break
  time.sleep(.3)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 payload={'updated_at':datetime.now(timezone.utc).isoformat(),'source':START,'events':list(seen.values()),'errors':errors[:20]}
 # Avoid overwriting previously collected data if site temporarily fails.
 if not seen and OUT.exists():
  print('No new events: keeping prior file; diagnostic:',errors[:2]);return
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Saved',len(seen),'Agenda LX events to',OUT)
if __name__=='__main__':main()
