import re, html, json, sys
t = open('bulba_expansions.html', encoding='utf-8', errors='ignore').read()

def clean(c):
    c = re.sub(r'<sup.*?</sup>', '', c, flags=re.S)
    c = re.sub(r'<br\s*/?>', ' | ', c)
    s = html.unescape(re.sub(r'<[^>]+>', '', c))
    return re.sub(r'\s+', ' ', s).strip()

def fullres(src):
    # https://archives.bulbagarden.net/media/upload/thumb/a/ab/File.png/40px-File.png -> .../upload/a/ab/File.png
    m = re.match(r'(https://archives\.bulbagarden\.net/media/upload)/thumb/(\w/\w\w)/([^/]+)/\d+px-[^"]+', src)
    if m: return f'{m.group(1)}/{m.group(2)}/{m.group(3)}'
    return src

sections = re.split(r'(<span class="mw-headline"[^>]*>.*?</span>)', t)
out = []
cur = None
for part in sections:
    m = re.match(r'<span class="mw-headline"[^>]*>(.*?)</span>', part, re.S)
    if m:
        cur = clean(m.group(1)); continue
    if cur is None: continue
    for tbl in re.findall(r'<table.*?</table>', part, re.S):
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S)
        if not rows: continue
        hdr = [clean(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rows[0], re.S)]
        if 'Name of Expansion' not in hdr and 'Name of Set' not in ' '.join(hdr): continue
        for r in rows[1:]:
            cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', r, re.S)
            if len(cells) < 5: continue
            rec = {'section': cur}
            for h, c in zip(hdr, cells):
                imgs = re.findall(r'src="([^"]+)"', c)
                key = h.lower()
                if 'symbol' in key: rec['symbol_url'] = fullres(imgs[0]) if imgs else None
                elif 'logo' in key: rec['logo_url'] = fullres(imgs[0]) if imgs else None; rec['logo_alt']=clean(c)
                else: rec[key] = clean(c)
            out.append(rec)
print('sections seen:', sorted(set(r['section'] for r in out)))
print('total rows', len(out))
print('header keys', sorted(set(k for r in out for k in r)))
json.dump(out, open('bulba_raw.json', 'w'), indent=1)
for r in out:
    if any(x in r.get('name of expansion','') for x in ['Legends Awakened','Team Up','Dragon Vault','Base Set','Southern']): print(r)
