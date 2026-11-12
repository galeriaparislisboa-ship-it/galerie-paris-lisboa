#!/usr/bin/env python3
"""Galerie Paris–Lisboa: daily exhibitions collector.
Requires: pip install requests beautifulsoup4
Writes data/generators/exhibitions.json. No API keys required.
"""
import json, re, sys, time
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data/generators/exhibitions.json"
SOURCES=[
 ("CCB","Lisboa","Architecture","https://www.ccb.pt/"),
 ("MAAT","Lisboa","Art","https://www.maat.pt/"),
 ("Gulbenkian","Lisboa","Art","https://gulbenkian.pt/"),
 ("Serralves","Porto","Art","https://www.serralves.pt/"),
 ("São Mamede","Lisboa","Painting","https://www.saomamede.com/listagem/exposicoes"),
 ("Museu do Design","Lisboa","Design","https://mude.pt/"),
 ("Museu Coleção Berardo / MAC CCB","Lisboa","Art","https://www.ccb.pt/"),
 ("Culturgest","Lisboa","Art","https://www.culturgest.pt/"),
 ("Galeria Municipal do Porto","Porto","Art","https://www.galeriamunicipaldoporto.pt/"),
 ("Museu de Arte Contemporânea de Elvas","Évora","Art","https://www.cm-elvas.pt/"),
 ("Museu Nacional de Arte Contemporânea","Lisboa","Art","https://www.museuartecontemporanea.gov.pt/"),
]
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; GPLExhibitions/1.0; editorial discovery)"}
def iso(value):
 if isinstance(value,dict):value=value.get("@value","")
 m=re.search(r"\d{4}-\d{2}-\d{2}",str(value or ""))
 return m.group(0) if m else ""
def objects(x):
 if isinstance(x,list):
  for v in x:yield from objects(v)
 elif isinstance(x,dict):
  yield x
  if "@graph" in x:yield from objects(x["@graph"])
def text(x):
 if isinstance(x,dict):return x.get("name","")
 return str(x or "")
def collect(session,name,city,category,url):
 r=session.get(url,headers=HEADERS,timeout=14);r.raise_for_status()
 soup=BeautifulSoup(r.text,"html.parser")
 site_logo=""
 for sel in ['meta[property="og:logo"]','link[rel="apple-touch-icon"]','link[rel="icon"]']:
  tag=soup.select_one(sel)
  if tag:site_logo=urljoin(r.url,tag.get("content") or tag.get("href") or "");break
 result=[]
 for tag in soup.select('script[type="application/ld+json"]'):
  try:parsed=json.loads(tag.string or tag.get_text())
  except (ValueError,TypeError):continue
  for obj in objects(parsed):
   types=obj.get("@type",[])
   if isinstance(types,str):types=[types]
   if not any("Event" in t or "Exhibition" in t for t in types):continue
   title=text(obj.get("name"));start=iso(obj.get("startDate"));end=iso(obj.get("endDate"))
   if not title or not start or not end or end<date.today().isoformat():continue
   image=obj.get("image","")
   if isinstance(image,list):image=image[0] if image else ""
   if isinstance(image,dict):image=image.get("url") or image.get("contentUrl") or ""
   link=obj.get("url") or r.url
   if not str(link).startswith("http"):link=urljoin(r.url,str(link))
   if not str(link).startswith("https://"):continue
   result.append({"title":title,"city":city,"category":category,"venue":name,
    "start":start,"end":end,"url":link,
    "image":urljoin(r.url,image) if image else "",
    "logo":site_logo if site_logo.startswith("https://") else ""})
 return result
def main():
 session=requests.Session(); old=[]
 if OUTPUT.exists():
  try:
   data=json.loads(OUTPUT.read_text())
   for e in data.get("events",[]):
    if isinstance(e,list) and len(e)>=7:
     e={"title":e[0],"city":e[1],"category":e[2],"venue":e[3],"start":e[4],"end":e[5],"url":e[6],"image":e[7] if len(e)>7 else "","logo":e[8] if len(e)>8 else ""}
    if isinstance(e,dict) and e.get("end","")>=date.today().isoformat():old.append(e)
  except (OSError,ValueError):pass
 found=[];errors=[]
 for name,city,category,url in SOURCES:
  try:found+=collect(session,name,city,category,url)
  except (requests.RequestException,ValueError) as e:errors.append(name+": "+str(e)[:120])
  time.sleep(.25)
 merged={}
 for e in old+found:
  if e.get("title") and e.get("venue") and e.get("end","")>=date.today().isoformat():
   key=(e["title"].casefold(),e["venue"].casefold())
   prior=merged.get(key,{})
   merged[key]={**prior,**{k:v for k,v in e.items() if v}}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 payload={"updated_at":datetime.now(timezone.utc).isoformat(),"sources_checked":len(SOURCES),
          "newly_discovered":len(found),"errors":errors,"events":list(merged.values())}
 OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
 print(f"{len(found)} found; {len(merged)} active records; {len(errors)} source errors")
 if errors:print("\n".join(errors),file=sys.stderr)
if __name__=="__main__":main()
