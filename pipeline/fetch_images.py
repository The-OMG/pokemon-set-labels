import json, os, io, time, re, urllib.request, sys
from PIL import Image
sets = json.load(open('sets_data.json', encoding='utf-8'))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PokemonSetLabels/1.0 (personal label printing)'}
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def fetch(url):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e:
            err = e; time.sleep(2 + 2*i)
    raise err
log = []
for s in sets:
    s['slug'] = slug(s['name'])
    for kind, maxw in (('symbol', 480), ('logo', 1100)):
        url = s.get(f'{kind}_url'); dest = f'img/{kind}s/{s["slug"]}.png'
        if not url: s[f'{kind}_img'] = None; continue
        if os.path.exists(dest): s[f'{kind}_img'] = dest; continue
        try:
            b = fetch(url); im = Image.open(io.BytesIO(b)).convert('RGBA')
            if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
            im.save(dest, optimize=True); s[f'{kind}_img'] = dest
            log.append(f'OK {kind} {s["name"]} {im.size}')
        except Exception as e:
            s[f'{kind}_img'] = None; log.append(f'FAIL {kind} {s["name"]} {url} {e}')
        time.sleep(0.6)
json.dump(sets, open('sets_data.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
open('fetch_log.txt', 'w', encoding='utf-8').write('\n'.join(log))
print('done', sum(1 for l in log if l.startswith('OK')), 'ok', sum(1 for l in log if l.startswith('FAIL')), 'fail')
