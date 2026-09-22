import json, re, datetime
raw = json.load(open('bulba_raw.json', encoding='utf-8'))
tcg = {x['id']: x for x in json.load(open('sets_p1.json', encoding='utf-8'))['data']}
def pdate(s):
    s = re.split(r'[|–—�-]', s)[0].strip()
    for fmt in ('%B %d, %Y', '%B %Y', '%Y', '%Y-%m-%d'):
        try: return datetime.datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except: pass
    m = re.search(r'(19|20)\d\d', s); return m.group(0) if m else s
KIND_NAMES = {'Secret': 'Secret', 'Shiny Vault': 'Shiny Vault', 'Trainer Gallery': 'Trainer Gallery', 'Galarian Gallery': 'Galarian Gallery',
              'Radiant Collection': 'Radiant Collection', 'Classic Collection': 'Classic Collection', 'Shiny Pokémon': 'Shiny Pokémon',
              'Alph Lithograph': 'Alph Lithograph', 'Holofoil': 'Holofoil', 'Unown': 'Unown', 'Rotom': 'Rotom', 'Arceus': 'Arceus', 'Shiny Legendary': 'Shiny Legendary'}
def pcards(s):
    parts = [p.strip() for p in (s or '').split('|')]
    m = re.match(r'\s*(\d+)', parts[0] if parts else ''); n = int(m.group(1)) if m else None
    extras = []
    for p in parts[1:]:
        m2 = re.match(r'(\d+)\s*(.*)', p)
        if not m2: continue
        kind = re.sub(r'\bcards?\b', '', m2.group(2)).replace('�', 'é').strip()
        extras.append({'kind': KIND_NAMES.get(kind, kind), 'n': int(m2.group(1))})
    secret = sum(e['n'] for e in extras if e['kind'] == 'Secret')
    return n, secret, extras
series_map = {'Original Series':'Base','Neo Series':'Neo','Legendary Collection Series':'Legendary Collection','e-Card Series':'e-Card',
 'EX Series':'EX','Diamond & Pearl Series':'Diamond & Pearl','Platinum Series':'Platinum','HeartGold & SoulSilver Series':'HeartGold & SoulSilver',
 'Call of Legends Series':'Call of Legends','Black & White Series':'Black & White','XY Series':'XY','Sun & Moon Series':'Sun & Moon',
 'Sword & Shield Series':'Sword & Shield','Scarlet & Violet Series':'Scarlet & Violet','Mega Evolution Series':'Mega Evolution',
 "McDonald's Collection":"McDonald's",'Trick or Trade':'Trick or Trade','POP / Play! Pokemon Prize Packs':'POP / Prize Packs','Other Miscellaneous Sets':'Other'}
out=[]; main_n=0; spec_n=0
for r in raw:
    if r['section'] == 'Basic Energy Cards': continue
    if r['section'] == '':   # the Black Star Promos table (its heading is an image, so the section name parsed blank)
        r = dict(r); r['section'] = 'Black Star Promos'; r['type of expansion'] = 'Promo'
        r['symbol_url'] = r.get('symbol_url') or 'https://archives.bulbagarden.net/media/upload/5/58/SetSymbolPromo.png'
    name = r.get('name of expansion','').replace('�',': ').replace('—',': ')
    typ = r.get('type of expansion','')
    cardstr = r.get('no. of cards','')
    if re.match(r'\s*\d+', typ) and not re.match(r'\s*\d+', cardstr):   # rowspan-shifted row (e.g. White Flare)
        prev = out[-1]; r['set abb.'] = cardstr; cardstr = typ; typ = prev['type']; r['release date'] = prev['release']
    cards, secret, extras = pcards(cardstr.replace('*',''))
    promo_series = {'WP':'Base','NP':'EX','DPP':'Diamond & Pearl','HSP':'HeartGold & SoulSilver','BWP':'Black & White','XYP':'XY','SMP':'Sun & Moon','SWSD':'Sword & Shield','SVP':'Scarlet & Violet','MEP':'Mega Evolution'}
    series = promo_series.get(r.get('set abb.','').strip(), series_map.get(r['section'], r['section'])) if typ == 'Promo' else series_map.get(r['section'], r['section'])
    if typ == 'Promo' and r.get('set abb.','').strip() == 'SVP': r['release period'] = 'March 31, 2023'   # English SVP promos began with the S&V launch
    rec = dict(name=name, series=series, type=typ or 'Other',
               setno=r.get('set no.',''), abbr=r.get('set abb.','').strip(), cards=cards, secret=secret, extras=extras,
               release=pdate(r.get('release date') or r.get('release period') or ''),
               symbol_url=r.get('symbol_url'), logo_url=r.get('logo_url'))
    if typ == 'Main Series Expansion': main_n += 1; rec['expno'] = main_n
    elif typ == 'Special Expansion': spec_n += 1; rec['expno'] = spec_n
    else: rec['expno'] = None
    out.append(rec)
# fill Base Set images from pokemontcg.io
for rec in out:
    if not rec['symbol_url'] or not rec['logo_url']:
        nm = rec['name'].lower().replace(' set','').replace('play! pokémon ','').replace('pokémon trading card game classic','classic')
        cand = [t for t in tcg.values() if t['name'].lower()==nm or (rec['name']=='Base Set' and t['id']=='base1')]
        if cand:
            rec['logo_url'] = rec['logo_url'] or cand[0]['images']['logo']
            if rec['name'] != 'Base Set': rec['symbol_url'] = rec['symbol_url'] or cand[0]['images']['symbol']   # Base Set has no set symbol
        else: print('NO IMAGES:', rec['name'])
json.dump(out, open('sets_data.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
print(len(out), 'sets; main', main_n, 'special', spec_n)
for r in out:
    if r['name'] in ('Diamond & Pearl: Legends Awakened','Sun & Moon: Team Up','Dragon Vault') or r['abbr'] in ('LA','TEU','DRV'): print(r['expno'], r['name'], r['abbr'], r['release'], r['cards'], r['secret'])
print('no abbr:', [r['name'] for r in out if not r['abbr']])
print('bad dates:', [(r['name'], r['release']) for r in out if not re.match(r'\d{4}-\d\d-\d\d', r['release'])])
print('types:', {t: sum(1 for r in out if r['type']==t) for t in set(r['type'] for r in out)})
print([ (r['expno'],r['name'],r['abbr'],r['release']) for r in out if r['release']>='2025-06'])
