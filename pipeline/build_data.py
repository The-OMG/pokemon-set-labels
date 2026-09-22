import json, re, datetime
raw = json.load(open('bulba_raw.json', encoding='utf-8'))
tcg = {x['id']: x for x in json.load(open('sets_p1.json', encoding='utf-8'))['data']}
def pdate(s):
    s = s.split('|')[0].strip()
    for fmt in ('%B %d, %Y', '%B %Y', '%Y', '%Y-%m-%d'):
        try: return datetime.datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except: pass
    m = re.search(r'(19|20)\d\d', s); return m.group(0) if m else s
def pcards(s):
    m = re.match(r'\s*(\d+)', s or ''); n = int(m.group(1)) if m else None
    m2 = re.search(r'(\d+)\s*Secret', s or ''); return n, (int(m2.group(1)) if m2 else 0)
series_map = {'Original Series':'Base','Neo Series':'Neo','Legendary Collection Series':'Legendary Collection','e-Card Series':'e-Card',
 'EX Series':'EX','Diamond & Pearl Series':'Diamond & Pearl','Platinum Series':'Platinum','HeartGold & SoulSilver Series':'HeartGold & SoulSilver',
 'Call of Legends Series':'Call of Legends','Black & White Series':'Black & White','XY Series':'XY','Sun & Moon Series':'Sun & Moon',
 'Sword & Shield Series':'Sword & Shield','Scarlet & Violet Series':'Scarlet & Violet','Mega Evolution Series':'Mega Evolution',
 "McDonald's Collection":"McDonald's",'Trick or Trade':'Trick or Trade','POP / Play! Pokemon Prize Packs':'POP / Prize Packs','Other Miscellaneous Sets':'Other'}
out=[]; main_n=0; spec_n=0
for r in raw:
    if r['section'] in ('', 'Basic Energy Cards'): continue
    name = r.get('name of expansion','').replace('�',': ').replace('—',': ')
    typ = r.get('type of expansion','')
    cardstr = r.get('no. of cards','')
    if re.match(r'\s*\d+', typ) and not re.match(r'\s*\d+', cardstr):   # rowspan-shifted row (e.g. White Flare)
        prev = out[-1]; r['set abb.'] = cardstr; cardstr = typ; typ = prev['type']; r['release date'] = prev['release']
    cards, secret = pcards(cardstr)
    rec = dict(name=name, series=series_map.get(r['section'], r['section']), type=typ or 'Other',
               setno=r.get('set no.',''), abbr=r.get('set abb.','').strip(), cards=cards, secret=secret,
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
