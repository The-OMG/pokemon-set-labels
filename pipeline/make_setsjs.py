import json, base64, io, os, shutil, datetime
from PIL import Image
sets = json.load(open('sets_data.json', encoding='utf-8'))
printed = [a for a in json.load(open('docx_abbrs.json')) if not a.isdigit()]
os.makedirs('public/img/logos', exist_ok=True)
out = []
for s in sets:
    rec = {k: s.get(k) for k in ('name','series','type','setno','abbr','cards','secret','release','expno','slug')}
    rec['printed2023'] = s['abbr'] in printed
    sym = s.get('symbol_img'); rec['symbol_img'] = None
    if sym and os.path.exists(sym):
        im = Image.open(sym).convert('RGBA')
        if im.width > 240 or im.height > 240: im.thumbnail((240, 240), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, 'PNG', optimize=True); rec['symbol_img'] = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
    logo = s.get('logo_img'); rec['logo_img'] = None
    if logo and os.path.exists(logo):
        dest = f'public/img/logos/{s["slug"]}.png'; shutil.copyfile(logo, dest); rec['logo_img'] = f'img/logos/{s["slug"]}.png'
    out.append(rec)
js = 'window.POKEMON_SETS_DATE = ' + json.dumps(datetime.date.today().isoformat()) + ';\nwindow.POKEMON_SETS = ' + json.dumps(out, ensure_ascii=False) + ';\n'
open('public/sets.js', 'w', encoding='utf-8').write(js)
print('sets.js', round(len(js.encode())/1e6, 2), 'MB;', sum(1 for r in out if r['symbol_img']), 'symbols,', sum(1 for r in out if r['logo_img']), 'logos;', 'already-printed flags:', sum(1 for r in out if r['printed2023']))
tot = sum(os.path.getsize(os.path.join('public/img/logos', f)) for f in os.listdir('public/img/logos')); print('logos dir', round(tot/1e6, 1), 'MB', len(os.listdir('public/img/logos')), 'files')
