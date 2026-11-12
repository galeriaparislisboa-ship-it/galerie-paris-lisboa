#!/usr/bin/env python3
"""Portugal Exhibition Finder V8 — discovery of dated exhibitions from public pages.
Uses requests and beautifulsoup4 (already installed in GitHub Actions).
Keeps existing verified exhibitions; never fabricates dates or events.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'generators' / 'exhibitions.json'
SOURCES = [
 ('CCB / MAC','Lisboa','Architecture','https://www.ccb.pt/'),
 ('MAAT','Lisboa','Art','https://www.maat.pt/'),
 ('Gulbenkian','Lisboa','Art','https://gulbenkian.pt/'),
 ('Serralves','Porto','Art','https://www.serralves.pt/'),
 ('São Mamede','Lisboa','Painting','https://www.saomamede.com/listagem/exposicoes'),
 ('MUDE','Lisboa','Design','https://mude.pt/'),
 ('Culturgest','Lisboa','Art','https://www.culturgest.pt/'),
 ('Galeria Municipal do Porto','Porto','Art','https://www.galeriamunicipaldoporto.pt/'),
 ('Museu de Arte Contemporânea de Elvas','Elvas','Art','https://www.cm-elvas.pt/'),
 ('Museu Nacional de Arte Contemporânea','Lisboa','Art','https://www.museuartecontemporanea.gov.pt/'),
 ('Museu Coleção Berardo / MAC CCB','Lisboa','Art','https://www.ccb.pt/'),
 ('Museu do Chiado','Lisboa','Art','https://www.museuartecontemporanea.gov.pt/'),
 ('Museu Nacional do Azulejo','Lisboa','Art','https://www.museunacionaldoazulejo.pt/'),
 ('Museu Nacional de Arte Antiga','Lisboa','Art','https://www.museudearteantiga.pt/'),
 ('Museu do Oriente','Lisboa','Art','https://www.museudooriente.pt/'),
 ('Museu da Marioneta','Lisboa','Art','https://www.museudamarioneta.pt/'),
 ('Museu de Lisboa','Lisboa','Art','https://www.museudelisboa.pt/'),
 ('Museu do Aljube','Lisboa','Art','https://www.museudoaljube.pt/'),
 ('Museu da Farmácia','Lisboa','Art','https://www.museudafarmacia.pt/'),
 ('Museu da Carris','Lisboa','Design','https://museu.carris.pt/'),
 ('Museu da Eletricidade / MAAT','Lisboa','Design','https://www.maat.pt/'),
 ('Museu Bordalo Pinheiro','Lisboa','Art','https://museubordalopinheiro.pt/'),
 ('Museu da Água','Lisboa','Art','https://www.epal.pt/'),
 ('Museu da Cidade / Palácio Pimenta','Lisboa','Art','https://www.museudelisboa.pt/'),
 ('Museu da Música','Lisboa','Art','https://www.museunacionaldamusica.gov.pt/'),
 ('Museu Nacional do Traje','Lisboa','Design','https://www.museudotraje.gov.pt/'),
 ('Museu Nacional do Teatro e da Dança','Lisboa','Art','https://www.museudoteatroedanca.gov.pt/'),
 ('Museu de Arte Popular','Lisboa','Design','https://www.patrimoniocultural.gov.pt/'),
 ('Museu da Presidência','Lisboa','Art','https://www.museu.presidencia.pt/'),
 ('Galeria Graça Brandão','Lisboa','Art','https://www.galeriagracabrandao.com/'),
 ('Galeria Filomena Soares','Lisboa','Art','https://www.gfilomenasoares.com/'),
 ('Galeria Cristina Guerra','Lisboa','Art','https://www.cristinaguerra.com/'),
 ('Galeria Vera Cortês','Lisboa','Art','https://www.veracortes.com/'),
 ('Galeria Pedro Cera','Lisboa','Art','https://www.pedrocera.com/'),
 ('Galeria Francisco Fino','Lisboa','Art','https://www.franciscofino.com/'),
 ('Galeria 111','Lisboa','Art','https://www.111.pt/'),
 ('3+1 Arte Contemporânea','Lisboa','Art','https://www.3m1arte.com/'),
 ('Galeria Madragoa','Lisboa','Art','https://www.galeriamadragoa.pt/'),
 ('Galeria Balcony','Lisboa','Art','https://www.balcony.pt/'),
 ('Galeria Foco','Lisboa','Art','https://www.focogallery.com/'),
 ('Galeria Zé dos Bois','Lisboa','Art','https://www.zedosbois.org/'),
 ('Underdogs Gallery','Lisboa','Art','https://www.under-dogs.net/'),
 ('Hangar Centro de Investigação Artística','Lisboa','Art','https://hangar.com.pt/'),
 ('Carpintarias de São Lázaro','Lisboa','Art','https://www.carpintariasdesaolazaro.pt/'),
 ('Atelier-Museu Júlio Pomar','Lisboa','Painting','https://www.ateliermuseujuliopomar.pt/'),
 ('Museu Arpad Szenes Vieira da Silva','Lisboa','Painting','https://fasvs.pt/'),
 ('Casa da Cerca','Almada','Art','https://www.cm-almada.pt/'),
 ('Centro Cultural de Belém','Lisboa','Architecture','https://www.ccb.pt/'),
 ('Trienal de Arquitectura de Lisboa','Lisboa','Architecture','https://www.trienaldelisboa.com/'),
 ('Lisbon Architecture Triennale','Lisboa','Architecture','https://www.trienaldelisboa.com/'),
 ('Museu da Arquitectura','Matosinhos','Architecture','https://casadaarquitectura.pt/'),
 ('Casa da Arquitectura','Matosinhos','Architecture','https://casadaarquitectura.pt/'),
 ('Museu de Serralves','Porto','Art','https://www.serralves.pt/'),
 ('Casa de Serralves','Porto','Design','https://www.serralves.pt/'),
 ('Museu Nacional Soares dos Reis','Porto','Art','https://museusoaresdosreis.gov.pt/'),
 ('Museu do Carro Eléctrico','Porto','Design','https://www.museudocarroelectrico.pt/'),
 ('Museu do Porto','Porto','Art','https://museudoporto.pt/'),
 ('Museu da Misericórdia do Porto','Porto','Art','https://www.mmipo.pt/'),
 ('Museu de Arte Contemporânea de Serralves','Porto','Art','https://www.serralves.pt/'),
 ('Fundação de Serralves','Porto','Art','https://www.serralves.pt/'),
 ('Galeria Fernando Santos','Porto','Art','https://www.galeriafernandosantos.com/'),
 ('Galeria Nuno Centeno','Porto','Art','https://www.nunocenteno.com/'),
 ('Galeria Presença','Porto','Art','https://www.galeriapresenca.pt/'),
 ('Galeria Quadrado Azul','Porto','Art','https://www.quadradoazul.pt/'),
 ('Galeria Municipal do Porto','Porto','Art','https://www.galeriamunicipaldoporto.pt/'),
 ('Galeria Lehmann + Silva','Porto','Art','https://www.lehmannsilva.com/'),
 ('Galeria São Mamede Porto','Porto','Painting','https://www.saomamede.com/listagem/exposicoes'),
 ('Espaço Mira','Porto','Art','https://www.miraonline.org/'),
 ('MIRA FORUM','Porto','Art','https://www.miraonline.org/'),
 ('Museu de Arte Sacra','Braga','Art','https://www.cm-braga.pt/'),
 ('Museu dos Biscainhos','Braga','Art','https://www.museudosbiscainhos.gov.pt/'),
 ('Museu D. Diogo de Sousa','Braga','Art','https://www.museuddiogodesousa.gov.pt/'),
 ('gnration','Braga','Art','https://www.gnration.pt/'),
 ('Theatro Circo','Braga','Art','https://www.theatrocirco.com/'),
 ('Centro Internacional das Artes José de Guimarães','Guimarães','Art','https://www.ciajg.pt/'),
 ('Centro Cultural Vila Flor','Guimarães','Art','https://www.ccvf.pt/'),
 ('Museu Alberto Sampaio','Guimarães','Art','https://www.museualbertosampaio.gov.pt/'),
 ('Museu de Lamego','Lamego','Art','https://www.museudelamego.gov.pt/'),
 ('Museu de Arte Contemporânea de Chaves','Chaves','Art','https://www.chaves.pt/'),
 ('Museu de Viseu / Grão Vasco','Viseu','Art','https://www.museugraovasco.gov.pt/'),
 ('Museu de Aveiro','Aveiro','Art','https://www.cm-aveiro.pt/'),
 ('Museu de Ílhavo','Ílhavo','Art','https://museumaritimo.cm-ilhavo.pt/'),
 ('Museu de Santa Joana','Aveiro','Art','https://www.cm-aveiro.pt/'),
 ('Museu de Coimbra','Coimbra','Art','https://www.cm-coimbra.pt/'),
 ('Museu Nacional Machado de Castro','Coimbra','Art','https://www.museumachadocastro.gov.pt/'),
 ('Centro de Artes Visuais','Coimbra','Art','https://www.centrodeartesvisuais.pt/'),
 ('Convento São Francisco','Coimbra','Art','https://www.conventosaofrancisco.pt/'),
 ('Museu da Ciência da Universidade de Coimbra','Coimbra','Design','https://www.museudaciencia.org/'),
 ('Museu de Leiria','Leiria','Art','https://www.cm-leiria.pt/'),
 ('m|i|mo Museu da Imagem em Movimento','Leiria','Art','https://www.cm-leiria.pt/'),
 ('Centro de Artes das Caldas da Rainha','Caldas da Rainha','Art','https://www.mcr.pt/'),
 ('Museu José Malhoa','Caldas da Rainha','Painting','https://www.museujosemalhoa.gov.pt/'),
 ('Museu da Cerâmica','Caldas da Rainha','Design','https://www.museudaceramica.gov.pt/'),
 ('Museu de Alcobaça','Alcobaça','Art','https://www.cm-alcobaca.pt/'),
 ('Museu de Santarém','Santarém','Art','https://www.cm-santarem.pt/'),
 ('Museu do Neo-Realismo','Vila Franca de Xira','Art','https://www.museudoneorealismo.pt/'),
 ('Casa das Histórias Paula Rego','Cascais','Painting','https://www.cascais.pt/'),
 ('Centro Cultural de Cascais','Cascais','Art','https://www.fundacaodomluis.pt/'),
 ('Museu Condes de Castro Guimarães','Cascais','Art','https://www.cascais.pt/'),
 ('MU.SA Museu das Artes de Sintra','Sintra','Art','https://cm-sintra.pt/'),
 ('Museu de Oeiras','Oeiras','Art','https://www.oeiras.pt/'),
 ('Centro de Arte Manuel de Brito','Oeiras','Art','https://www.oeiras.pt/'),
 ('Museu de Setúbal','Setúbal','Art','https://www.mun-setubal.pt/'),
 ('Casa da Baía','Setúbal','Art','https://www.mun-setubal.pt/'),
 ('Museu de Évora','Évora','Art','https://www.museudevora.gov.pt/'),
 ('Fundação Eugénio de Almeida','Évora','Art','https://www.fundacaoeugeniodealmeida.pt/'),
 ('Centro de Arte e Cultura FEA','Évora','Art','https://www.fundacaoeugeniodealmeida.pt/'),
 ('Museu de Arte Contemporânea de Elvas','Elvas','Art','https://www.cm-elvas.pt/'),
 ('Museu Municipal de Portalegre','Portalegre','Art','https://www.cm-portalegre.pt/'),
 ('Museu da Tapeçaria de Portalegre','Portalegre','Design','https://www.cm-portalegre.pt/'),
 ('Museu de Beja','Beja','Art','https://www.museuregionaldebeja.pt/'),
 ('Museu de Mértola','Mértola','Art','https://www.cm-mertola.pt/'),
 ('Museu de Faro','Faro','Art','https://www.cm-faro.pt/'),
 ('Museu Municipal de Tavira','Tavira','Art','https://museumunicipaldetavira.cm-tavira.pt/'),
 ('Museu de Portimão','Portimão','Art','https://www.museudeportimao.pt/'),
 ('Centro Cultural de Lagos','Lagos','Art','https://www.cm-lagos.pt/'),
 ('Museu de Loulé','Loulé','Art','https://www.cm-loule.pt/'),
 ('Museu de Arte Sacra do Funchal','Funchal','Art','https://www.museuartesacrafunchal.org/'),
 ('Museu de Arte Contemporânea da Madeira','Calheta','Art','https://www.mudas.pt/'),
 ('MUDAS Museu de Arte Contemporânea','Calheta','Art','https://www.mudas.pt/'),
 ('Museu da Quinta das Cruzes','Funchal','Art','https://mqc.madeira.gov.pt/'),
 ('Museu Carlos Machado','Ponta Delgada','Art','https://museucarlosmachado.azores.gov.pt/'),
 ('Arquipélago Centro de Artes Contemporâneas','Ribeira Grande','Art','https://arquipelagocentrodeartes.azores.gov.pt/'),
 ('Museu de Angra do Heroísmo','Angra do Heroísmo','Art','https://museu-angra.azores.gov.pt/'),
 ('Museu da Horta','Horta','Art','https://museu-horta.azores.gov.pt/'),
]

TODAY = date.today()
KEYWORDS = re.compile(r'exposi[cç][aãõo]?(?:o|es|ões)?|exhibition|exhibitions|exhibit|mostra|on.view|what.s.on|agenda|programa[cç][aã]o|em.cartaz|events?|exposicoes|exposicoes', re.I)
DETAIL = re.compile(r'exposi[cç]|exhibition|exhibit|mostra', re.I)
ISO_DATE = re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')
DATE_PT = re.compile(r'\b(\d{1,2})\s+(?:de\s+)?(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(?:de\s+)?(20\d{2})\b', re.I)
MONTHS = {m:i for i,m in enumerate(('janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'),1)}
HEADERS = {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36', 'Accept':'text/html,application/xhtml+xml', 'Accept-Language':'pt-PT,pt;q=0.9,en;q=0.7'}
TIMEOUT = (4, 7)
MAX_LINKS = 12
MAX_WORKERS = 8

def iso(value):
    if isinstance(value, dict):
        value = value.get('@value') or value.get('value')
    if not isinstance(value, str): return None
    match = ISO_DATE.search(value)
    if match:
        try: return date.fromisoformat(match.group(1)).isoformat()
        except ValueError: return None
    match = DATE_PT.search(value)
    if match:
        try:
            day, month, year = match.groups()
            return date(int(year), MONTHS[month.lower().replace('ç','ç')], int(day)).isoformat()
        except (ValueError, KeyError): return None
    return None

def valid(row):
    if not isinstance(row, dict): return False
    start, end = iso(row.get('start')), iso(row.get('end'))
    return bool(start and end and start <= end and end >= TODAY.isoformat()
                and len(str(row.get('title','')).strip()) >= 5
                and str(row.get('url','')).startswith(('https://','http://')))

def event_obj(title, city, category, venue, start, end, url, image=None):
    row = dict(title=str(title).strip()[:180],city=city,category=category,
               venue=str(venue or '').strip()[:140],start=iso(start),end=iso(end),url=url)
    if isinstance(image,str) and image.startswith('http'): row['image']=image
    return row if valid(row) else None

def walk(obj):
    if isinstance(obj,list):
        for item in obj: yield from walk(item)
    elif isinstance(obj,dict):
        yield obj
        for key in ('@graph','itemListElement','mainEntity','event','events','item'):
            if key in obj: yield from walk(obj[key])

def extract(soup, name, city, category, url):
    found=[]
    for tag in soup.select('script[type="application/ld+json"]'):
        try: data=json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError): continue
        for item in walk(data):
            types=item.get('@type',[])
            if isinstance(types,str): types=[types]
            if not any(str(t).lower().endswith(('event','exhibitionevent','visualartsevent')) for t in types): continue
            title=item.get('name')
            if not isinstance(title,str): continue
            description=str(item.get('description',''))
            if not DETAIL.search(title+' '+description+' '+name): continue
            location=item.get('location') or {}
            venue=location.get('name') if isinstance(location,dict) else name
            link=item.get('url') or url
            if isinstance(link,list): link=link[0] if link else url
            if not isinstance(link,str): link=url
            image=item.get('image')
            if isinstance(image,list): image=image[0] if image else None
            if isinstance(image,dict): image=image.get('url')
            row=event_obj(title,city,category,venue or name,item.get('startDate'),item.get('endDate'),urljoin(url,link),urljoin(url,image) if isinstance(image,str) else None)
            if row: found.append(row)
    # Conservative HTML fallback: only on exhibition-specific detail pages,
    # with two explicit dates in the page and a meaningful heading.
    path=urlparse(url).path
    if DETAIL.search(path):
        heading=soup.select_one('main h1, article h1, h1')
        title=heading.get_text(' ',strip=True) if heading else ''
        if len(title)>=7 and not re.search(r'^(exposi[cç][oõ]es|exhibitions|agenda|programa[cç][aã]o)$',title,re.I):
            main=soup.select_one('main, article') or soup
            # Prefer semantic <time datetime="..."> elements to avoid unrelated page dates.
            dates=[iso(t.get('datetime') or t.get_text(' ',strip=True)) for t in main.select('time')]
            dates=[d for d in dates if d]
            if len(dates)<2:
                # On detail pages, date ranges usually appear near the heading.
                segment=main.get_text(' ',strip=True)[:1300]
                dates=[iso(m.group()) for m in ISO_DATE.finditer(segment)]
                dates += [iso(m.group()) for m in DATE_PT.finditer(segment)]
            dates=[d for d in dates if d]
            if len(dates)>=2:
                start,end=dates[0],dates[1]
                image=soup.select_one('meta[property="og:image"]')
                image_url=urljoin(url,image.get('content')) if image and image.get('content') else None
                row=event_obj(title,city,category,name,start,end,url,image_url)
                if row: found.append(row)
    return found

def fetch(session,url):
    r=session.get(url,headers=HEADERS,timeout=TIMEOUT,allow_redirects=True)
    r.raise_for_status()
    if 'html' not in r.headers.get('Content-Type','text/html').lower(): return None,None
    return BeautifulSoup(r.text[:1500000],'html.parser'),r.url

def crawl(source):
    name,city,category,home=source
    session=requests.Session()
    try:
        soup,base=fetch(session,home)
        if soup is None: return [],None
        found=extract(soup,name,city,category,base)
        host=urlparse(base).netloc.removeprefix('www.')
        links=[]
        for a in soup.select('a[href]'):
            href=urldefrag(urljoin(base,a.get('href','')))[0]
            parsed=urlparse(href)
            if parsed.scheme not in ('http','https') or parsed.netloc.removeprefix('www.')!=host: continue
            if href==base or href in links: continue
            label=a.get_text(' ',strip=True)+' '+parsed.path
            if KEYWORDS.search(label): links.append(href)
        # Priority to exhibition detail links, then listing pages.
        links.sort(key=lambda u: (not bool(DETAIL.search(urlparse(u).path)),len(urlparse(u).path)))
        for link in links[:MAX_LINKS]:
            try:
                page,final=fetch(session,link)
                if page is not None: found.extend(extract(page,name,city,category,final))
            except requests.RequestException: continue
        return found,None
    except requests.RequestException as exc:
        return [],f'{name}: {str(exc)[:160]}'
    finally: session.close()

def old_events():
    if not OUTPUT.exists(): return []
    try: rows=json.loads(OUTPUT.read_text(encoding='utf-8')).get('events',[])
    except (OSError,ValueError,AttributeError): return []
    saved=[]
    for row in rows:
        if isinstance(row,list) and len(row)>=7:
            row=dict(zip(('title','city','category','venue','start','end','url'),row))
        if valid(row): saved.append(row)
    return saved

def main():
    previous=old_events()
    collected=[]; errors=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures={pool.submit(crawl,source):source[0] for source in SOURCES}
        for index,future in enumerate(as_completed(futures),1):
            try: fresh,error=future.result()
            except Exception as exc: fresh,error=[],f'{futures[future]}: {type(exc).__name__}: {exc}'
            collected.extend(fresh)
            if error: errors.append(error)
            print(f'[{index}/{len(SOURCES)}] {futures[future]}: {len(fresh)} events',flush=True)
    unique={}
    for row in previous+collected:
        if not valid(row): continue
        key=(row['title'].casefold().strip(),row['start'],row['url'].rstrip('/'))
        unique[key]=row
    old_keys={(r['title'].casefold().strip(),r['start'],r['url'].rstrip('/')) for r in previous}
    output=dict(updated_at=datetime.now(timezone.utc).isoformat(),sources_checked=len(SOURCES),
                newly_discovered=len(set(unique)-old_keys),errors=errors,
                events=sorted(unique.values(),key=lambda e:(e['start'],e['city'],e['title'])))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Saved {len(output['events'])} events; {output['newly_discovered']} newly discovered; {len(errors)} source errors",flush=True)

if __name__=='__main__': main()
