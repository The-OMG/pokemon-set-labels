"""Species data + artwork for the Pokémon (character) labels.

Source: PokeAPI's CSV dump (github.com/PokeAPI/pokeapi, data/v2/csv) and its official-artwork sprites.
Writes ../public/pokemon.js and ../public/img/art/<dex>.webp (475 px official artwork, alpha kept).

    cd pipeline
    python build_pokemon.py            # downloads the CSVs into pokecsv/ and any artwork not already present
"""
import csv, io, json, os, re, datetime, urllib.request, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

CSV_BASE = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
ART_URL = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png'
CSVS = ['pokemon_species', 'pokemon_species_names', 'pokemon_species_flavor_text', 'pokemon', 'pokemon_types', 'types', 'versions']
UA = {'User-Agent': 'PokemonSetLabels/1.0 (personal label printing)'}
EN = '9'
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, '..', 'public')
ART_DIR = os.path.join(PUBLIC, 'img', 'art')

# Dex entry preference: modern, well-edited text first (the TCG reuses these), older games as a fallback.
VERSION_PREF = ['sword', 'shield', 'scarlet', 'violet', 'legends-arceus', 'ultra-sun', 'ultra-moon', 'sun', 'moon',
                'x', 'y', 'omega-ruby', 'alpha-sapphire', 'black-2', 'white-2', 'black', 'white', 'platinum',
                'heartgold', 'soulsilver', 'diamond', 'pearl', 'emerald', 'firered', 'leafgreen', 'ruby', 'sapphire',
                'crystal', 'gold', 'silver', 'yellow', 'red', 'blue', 'lets-go-pikachu', 'lets-go-eevee']
ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
GEN_YEAR = {1: 1996, 2: 1999, 3: 2002, 4: 2006, 5: 2010, 6: 2013, 7: 2016, 8: 2019, 9: 2022}
# Species that arrived later than their generation's first games (Japanese release years)
YEAR_RANGES = [((803, 807), 2017),   # Ultra Sun & Ultra Moon
               ((808, 809), 2018),   # Meltan / Melmetal, Let's Go
               ((891, 898), 2020),   # Isle of Armor / Crown Tundra
               ((899, 905), 2022),   # Legends: Arceus
               ((1011, 1024), 2023), # Teal Mask / Indigo Disk
               ((1025, 1025), 2024)] # Pecharunt, Mochi Mayhem


def fetch(url):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e:
            err = e; time.sleep(2 + 2 * i)
    raise err


def rows(name):
    path = os.path.join(HERE, 'pokecsv', name + '.csv')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(fetch(CSV_BASE + name + '.csv'))
    return list(csv.DictReader(open(path, encoding='utf-8')))


def clean(t):
    t = t.replace('­\n', '').replace('­', '').replace('-\n', '-')
    t = re.sub(r'[\f\n\r\t ]+', ' ', t).strip()
    t = re.sub(r'POK[eé]MON', 'Pokémon', t, flags=re.I)
    return t


def first_sentence(t):
    protected = re.sub(r'\b(Mr|Mt|St|Dr|Jr|Mrs|Ms)\. ', r'\1<DOT> ', t)
    s = re.split(r'(?<=[.!?])\s+(?=["“A-Z0-9])', protected, maxsplit=1)[0]
    return s.replace('<DOT>', '.')


def year_for(n, gen):
    for (lo, hi), y in YEAR_RANGES:
        if lo <= n <= hi:
            return y
    return GEN_YEAR[gen]


def main():
    species = [r for r in rows('pokemon_species') if int(r['id']) <= 10000]
    names = {r['pokemon_species_id']: r for r in rows('pokemon_species_names') if r['local_language_id'] == EN}
    versions = {r['id']: r['identifier'] for r in rows('versions')}
    rank = {v: i for i, v in enumerate(VERSION_PREF)}
    texts = {}
    for r in rows('pokemon_species_flavor_text'):
        if r['language_id'] == EN:
            texts.setdefault(r['species_id'], []).append((rank.get(versions.get(r['version_id']), 99), clean(r['flavor_text'])))
    mons = {r['id']: r for r in rows('pokemon') if r['is_default'] == '1'}
    type_names = {r['id']: r['identifier'] for r in rows('types')}
    types = {}
    for r in sorted(rows('pokemon_types'), key=lambda r: int(r['slot'])):
        types.setdefault(r['pokemon_id'], []).append(type_names[r['type_id']].capitalize())

    out = []
    for sp in sorted(species, key=lambda r: int(r['id'])):
        sid = sp['id']; n = int(sid); gen = int(sp['generation_id'])
        mon = next((m for m in mons.values() if m['species_id'] == sid), None)
        cand = sorted(texts.get(sid, []), key=lambda x: x[0])
        full = cand[0][1] if cand else ''
        # one sentence, like the card: the preferred game's first sentence, unless it is a run-on
        shorts = [first_sentence(t) for _, t in cand]
        short = next((s for s in shorts if len(s) <= 110), min(shorts, key=len) if shorts else '')
        out.append({
            'n': n, 'name': names[sid]['name'], 'genus': names[sid]['genus'], 'gen': gen, 'genr': ROMAN[gen],
            'year': year_for(n, gen), 'types': types.get(mon['id'], []) if mon else [],
            'ht': int(mon['height']) if mon else None, 'wt': int(mon['weight']) if mon else None,
            'legendary': sp['is_legendary'] == '1', 'mythical': sp['is_mythical'] == '1',
            'short': short, 'flavor': full, 'slug': sp['identifier'],
        })

    os.makedirs(ART_DIR, exist_ok=True)

    def art(p):
        dest = os.path.join(ART_DIR, '%d.webp' % p['n'])
        if os.path.exists(dest):
            return None
        try:
            im = Image.open(io.BytesIO(fetch(ART_URL.format(p['n'])))).convert('RGBA')
            bb = im.getchannel('A').getbbox()            # trim the transparent margin so the art fills its box
            if bb: im = im.crop(bb)
            im.save(dest, 'WEBP', quality=86, method=6)
            return None
        except Exception as e:
            return '%d %s: %s' % (p['n'], p['name'], e)

    with ThreadPoolExecutor(12) as ex:
        fails = [f for f in ex.map(art, out) if f]
    for p in out:
        p['art'] = 'img/art/%d.webp' % p['n'] if os.path.exists(os.path.join(ART_DIR, '%d.webp' % p['n'])) else None

    js = ('window.POKEMON_SPECIES_DATE = ' + json.dumps(datetime.date.today().isoformat()) + ';\n'
          'window.POKEMON_SPECIES = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n')
    open(os.path.join(PUBLIC, 'pokemon.js'), 'w', encoding='utf-8').write(js)
    size = sum(os.path.getsize(os.path.join(ART_DIR, f)) for f in os.listdir(ART_DIR))
    print('pokemon.js %.2f MB, %d species, %d with art (%.1f MB), %d failed' % (len(js.encode()) / 1e6, len(out), sum(1 for p in out if p['art']), size / 1e6, len(fails)))
    for f in fails: print('  FAIL', f)


if __name__ == '__main__':
    main()
