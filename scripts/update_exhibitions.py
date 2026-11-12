#!/usr/bin/env python3
"""Galerie Paris-Lisboa: daily Portugal exhibitions discovery.
Requires: requests beautifulsoup4. No API keys.
Writes data/generators/exhibitions.json.
Only publishes exhibitions with explicit start/end dates and a source URL.
"""
import json
import re
import time
from datetime import datetime, date, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'generators' / 'exhibitions.json'

# Curated official institutions and exhibition listings. Sites may block bots;
# failures are reported in JSON, not silently treated as exhibitions.
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

KEYWORDS = re.compile(r'exposi[cç][aã]o|exhibition|exposi[cç][oõ]es|mostra|exhibit|exposição temporária', re.I)
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TODAY = date.today()
SESSION = requests.Session()
SESSION.headers.update({'User-Agent':'Mozilla/5.0 (compatible; GalerieParisLisboaExhibitions/2.0; cultural discovery)'})


def iso(value):
    if isinstance(value, dict):
        value = value.get('@value') or value.get('value')
    if not isinstance(value, str):
        return None
    match = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return None


def valid(event):
    if not isinstance(event, dict):
        return False
    start, end = iso(event.get('start')), iso(event.get('end'))
    if not start or not end or end < start or end < TODAY.isoformat():
        return False
    if not isinstance(event.get('title'), str) or len(event['title'].strip()) < 5:
        return False
    url = event.get('url', '')
    return isinstance(url, str) and url.startswith(('http://','https://'))


def event_obj(title, city, category, venue, start, end, url, image=None):
    result = {'title': str(title).strip()[:180], 'city': city, 'category': category,
              'venue': venue, 'start': iso(start), 'end': iso(end), 'url': url}
    if image and isinstance(image, str) and image.startswith('http'):
        result['image'] = image
    return result if valid(result) else None


def walk_json(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from walk_json(x)
    elif isinstance(obj, dict):
        yield obj
        for key in ('@graph', 'itemListElement', 'mainEntity', 'event', 'events'):
            if key in obj:
                yield from walk_json(obj[key])


def extract_events(soup, source_name, city, category, base):
    events = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for item in walk_json(data):
            typ = item.get('@type', '')
            types = typ if isinstance(typ, list) else [typ]
            if not any(str(t).lower().endswith(('event','exhibitionevent','visualartsevent')) for t in types):
                continue
            title = item.get('name')
            if not isinstance(title, str):
                continue
            # Require exhibition wording or exhibition-specific event type.
            if not KEYWORDS.search(title + ' ' + str(item.get('description','')) + ' ' + source_name):
                continue
            start, end = iso(item.get('startDate')), iso(item.get('endDate'))
            location = item.get('location', {})
            venue = location.get('name') if isinstance(location, dict) else source_name
            venue = venue or source_name
            link = item.get('url') or base
            if isinstance(link, list):
                link = link[0] if link else base
            if not isinstance(link, str):
                link = base
            image = item.get('image')
            if isinstance(image, list):
                image = image[0] if image else None
            if isinstance(image, dict):
                image = image.get('url')
            e = event_obj(title, city, category, venue, start, end, urljoin(base, link), urljoin(base, image) if isinstance(image,str) else None)
            if e:
                events.append(e)
    return events


def crawl_source(name, city, category, url):
    response = SESSION.get(url, timeout=13)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    found = extract_events(soup, name, city, category, response.url)
    # Discover relevant official event detail pages; limit per site for runtime.
    links = []
    host = urlparse(response.url).netloc.removeprefix('www.')
    for a in soup.select('a[href]'):
        href = urljoin(response.url, a['href'])
        if urlparse(href).netloc.removeprefix('www.') != host:
            continue
        label = a.get_text(' ', strip=True) + ' ' + href
        if KEYWORDS.search(label) and href not in links and href != response.url:
            links.append(href)
        if len(links) >= 5:
            break
    for link in links:
        try:
            r = SESSION.get(link, timeout=9)
            r.raise_for_status()
            found.extend(extract_events(BeautifulSoup(r.text,'html.parser'), name, city, category, r.url))
        except requests.RequestException:
            pass
    return found


def old_events():
    if not OUTPUT.exists():
        return []
    try:
        data = json.loads(OUTPUT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    kept = []
    for row in data.get('events', []):
        if isinstance(row, list) and len(row) >= 7:
            row = dict(zip(('title','city','category','venue','start','end','url'),row))
        if valid(row):
            kept.append(row)
    return kept


def main():
    events = old_events()
    errors = []
    discovered = 0
    for idx, (name, city, category, url) in enumerate(SOURCES, 1):
        try:
            fresh = crawl_source(name, city, category, url)
            events.extend(fresh)
            discovered += len(fresh)
        except requests.RequestException as exc:
            errors.append(f'{name}: {str(exc)[:180]}')
        print(f'[{idx}/{len(SOURCES)}] {name}: total={len(events)}', flush=True)
        time.sleep(0.08)
    unique = {}
    for row in events:
        if not valid(row):
            continue
        key = (row['title'].casefold().strip(), row['start'], row['url'].rstrip('/'))
        unique[key] = row
    output = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'sources_checked': len(SOURCES),
        'newly_discovered': discovered,
        'errors': errors,
        'events': sorted(unique.values(), key=lambda e:(e['start'],e['city'],e['title']))
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Saved {len(output['events'])} verified-date events; {len(errors)} source errors", flush=True)

if __name__ == '__main__':
    main()
