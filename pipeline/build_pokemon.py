"""Species data + artwork for the Pokémon (character) labels.

Source: PokeAPI's CSV dump (github.com/PokeAPI/pokeapi, data/v2/csv) and its official-artwork sprites.
Writes ../public/pokemon.js and ../public/img/art/<dex>.webp (475 px official artwork, alpha kept).

    cd pipeline
    python build_pokemon.py            # downloads the CSVs into pokecsv/ and any artwork not already present
"""
import csv, io, json, math, os, re, datetime, urllib.request, time
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


KEEP_CAPS = {'UFO', 'DNA', 'TV', 'HP', 'PP', 'UV'}


def clean(t):
    t = re.sub(r'­\s*', '', t).replace('-\n', '-')        # soft hyphens from the old games' line breaks
    t = re.sub(r'[\f\n\r\t ]+', ' ', t).strip()
    t = re.sub(r'POK[eé]MON', 'Pokémon', t, flags=re.I)
    t = re.sub(r"\b[A-Z][A-Z'’]{2,}\b", lambda m: m.group(0) if m.group(0) in KEEP_CAPS else m.group(0).capitalize(), t)   # BERRIES -> Berries
    t = re.sub(r'(^|[\s(])”', r'\1“', t)                    # a closing quote used as an opener: ”sea fiend.”
    return t.replace('Poke Ball', 'Poké Ball')


def norm_key(t):
    return re.sub(r'[^a-z]', '', t.lower().replace('could', 'can'))


# ---- choosing the entry ----
# Card flavor text is preferred: the TCG's editors already picked the good lines. Game entries fill the gaps.
# Every candidate's first sentence is scored; bad signs are references to regional forms or other forms
# (meaningless on a species label), leaning on other Pokémon's names, fragments and run-ons.
VARIANT_CARD = re.compile(r'\b(Alolan|Galarian|Hisuian|Paldean|Mega|Primal|Origin|Rapid Strike|Single Strike|Ice Rider|Shadow Rider|'
                          r'Crowned|Dusk Mane|Dawn Wings|Ultra Necrozma|Black Kyurem|White Kyurem|Eternamax|Bloodmoon|Terastal|Tera)\b')
TRAINER_CARD = re.compile(r"^Ash[’']s |^_+|Detective|Flying |Surfing |Birthday|with Grey Felt Hat")   # Ash's Pikachu, _____'s Pikachu...
JUNK_TEXT = re.compile(r'_{3,}|\bcard\b|\bbirthdate\b', re.I)
REGION = re.compile(r'\b(Alola|Galar|Hisui|Paldea|Kalos|Unova|Sinnoh|Hoenn|Johto|Kanto|Kitakami|this region|this land)\b')
FORM_REF = re.compile(r"(\bthis form\b|\bform of\b|\bin this form\b|’s form\b|'s form\b|\bthis is the form\b|\bthis style\b|\bthis mode\b|\bthis forme\b)", re.I)
CLASSIC = {'red', 'blue', 'yellow', 'gold', 'silver', 'crystal', 'firered', 'leafgreen', 'ruby', 'sapphire', 'emerald'}
OVERRIDES_FILE = os.path.join(HERE, 'flavor_overrides.json')   # {"25": "hand-picked sentence", ...} from the audit


def name_pattern(name):
    """Species name inside a card name as a whole word; tolerates "Nidoran ♂" for Nidoran♂ and curly/straight apostrophes."""
    body = ''.join(r'\s?' + re.escape(ch) if ch in '♂♀' else ("['’]" if ch in "'’" else re.escape(ch)) for ch in name)
    # not followed by more name: Pawmo ≠ Pawmot, Porygon ≠ Porygon2 / Porygon-Z (but "Mewtwo-EX" still counts as Mewtwo)
    return re.compile(r'(?<![A-Za-z])' + body + r'(?![A-Za-z0-9])(?!-[A-Z](?![A-Za-z]))')


def score_short(s, other_names):
    L, sc, flags = len(s), 0.0, []
    if L < 40: sc -= 2; flags.append('short')
    if L > 110: sc -= 3 + (L - 110) / 20; flags.append('long')
    if FORM_REF.search(s): sc -= 6; flags.append('form')
    if REGION.search(s): sc -= 4; flags.append('region')
    mentions = [nm for nm in other_names if re.search(r'\b' + re.escape(nm) + r'\b', s)]
    if mentions: sc -= 2 * len(mentions); flags.append('names:' + '/'.join(mentions))
    if not re.search(r'[.!?]["”’]?$', s): sc -= 3; flags.append('unterminated')
    if re.match(r'(This|These|They|That)\b', s): sc -= 0.8; flags.append('deictic')
    return sc, flags


def choose_entry(n, name, game_texts, card_texts, all_names):
    """game_texts: [(version, text)], card_texts: [{'text','name','date'}]. Returns (short, full, audit)."""
    other = [nm for nm in all_names if nm != name and len(nm) > 3]
    cands = {}
    for c in card_texts:
        cname = c.get('name', '')
        if VARIANT_CARD.search(cname) or TRAINER_CARD.search(cname) or JUNK_TEXT.search(c['text']):
            continue
        if not name_pattern(name).search(cname):   # a Pawmot card filed under Pawmo
            continue
        t = clean(c['text']); k = norm_key(t)
        d = cands.setdefault(k, {'text': t, 'cards': 0, 'games': 0, 'classic': False})
        d['cards'] += 1
    for ver, raw in game_texts:
        t = clean(raw); k = norm_key(t)
        d = cands.setdefault(k, {'text': t, 'cards': 0, 'games': 0, 'classic': False})
        d['games'] += 1; d['classic'] |= ver in CLASSIC
    scored = []
    for d in cands.values():
        full = d['text']; short = first_sentence(full)
        if len(short) < 45 and len(full) <= 115:   # a stub like "Adores round objects." keeps its second sentence
            short = full
        sc, flags = score_short(short, other)
        sc += 2.5 * math.log2(1 + d['cards']) + 0.6 * min(d['games'], 4) + (0.7 if d['classic'] else 0) + (1.0 if short == full else 0)
        scored.append((sc, short, full, d, flags))
    scored.sort(key=lambda x: -x[0])
    best = scored[0]
    return best[1], best[2], {'score': round(best[0], 2), 'cards': best[3]['cards'], 'games': best[3]['games'], 'flags': best[4],
                              'alts': [(round(s[0], 1), s[1]) for s in scored[1:4]]}


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
    texts = {}
    for r in rows('pokemon_species_flavor_text'):
        if r['language_id'] == EN:
            texts.setdefault(r['species_id'], []).append((versions.get(r['version_id'], ''), r['flavor_text']))
    card_path = os.path.join(HERE, 'card_flavor.json')
    card_texts = json.load(open(card_path, encoding='utf-8')) if os.path.exists(card_path) else {}
    if not card_texts: print('WARNING: card_flavor.json missing, run fetch_card_flavor.py; using game entries only')
    overrides = json.load(open(OVERRIDES_FILE, encoding='utf-8')) if os.path.exists(OVERRIDES_FILE) else {}
    all_names = [names[r['id']]['name'] for r in species]
    audit = []
    mons = {r['id']: r for r in rows('pokemon') if r['is_default'] == '1'}
    type_names = {r['id']: r['identifier'] for r in rows('types')}
    types = {}
    for r in sorted(rows('pokemon_types'), key=lambda r: int(r['slot'])):
        types.setdefault(r['pokemon_id'], []).append(type_names[r['type_id']].capitalize())

    out = []
    for sp in sorted(species, key=lambda r: int(r['id'])):
        sid = sp['id']; n = int(sid); gen = int(sp['generation_id'])
        mon = next((m for m in mons.values() if m['species_id'] == sid), None)
        short, full, info = choose_entry(n, names[sid]['name'], texts.get(sid, []), card_texts.get(sid, []), all_names)
        if sid in overrides:                         # hand-picked in the audit; an override replaces both lengths
            short = full = overrides[sid]; info['flags'] = ['override']
        audit.append({'n': n, 'name': names[sid]['name'], 'short': short, **info})
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
    with open(os.path.join(HERE, 'flavor_audit.tsv'), 'w', encoding='utf-8') as f:   # review this after every rebuild
        f.write('n\tname\tscore\tcards\tgames\tflags\tshort\talt1\n')
        for a in audit:
            f.write('%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (a['n'], a['name'], a.get('score', ''), a.get('cards', ''), a.get('games', ''),
                    ','.join(a['flags']), a['short'], a['alts'][0][1] if a.get('alts') else ''))
    size = sum(os.path.getsize(os.path.join(ART_DIR, f)) for f in os.listdir(ART_DIR))
    print('pokemon.js %.2f MB, %d species, %d with art (%.1f MB), %d failed' % (len(js.encode()) / 1e6, len(out), sum(1 for p in out if p['art']), size / 1e6, len(fails)))
    for f in fails: print('  FAIL', f)


if __name__ == '__main__':
    main()
