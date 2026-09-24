"""Korean release dates from pokemoncard.co.kr product pages (/card/<id>): name + 발매일.

The site has no expansion index, so product ids are scanned. By default this resumes after the highest id
already in kr_official.json and probes the next 80 ids (new releases); pass --full to rescan 1..(max+80).
Only booster / deck products are kept; build.py then keeps the boosters and matches them to Japanese sets.
"""
import json, re, sys, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Set Label Press data pipeline)"}
try: known = {o["pid"]: o for o in json.load(open("kr_official.json", encoding="utf-8"))}
except FileNotFoundError: known = {}
top = max(known, default=0)
start = 1 if ("--full" in sys.argv or not known) else top + 1
for i in range(start, top + 81):
    try: h = urllib.request.urlopen(urllib.request.Request(f"https://pokemoncard.co.kr/card/{i}", headers=UA), timeout=30).read().decode("utf-8")
    except Exception: continue
    t = re.search(r'medium-title[^>]*>([^<]*)<', h); d = re.search(r'발매일</b>\s*([0-9-]+)', h)
    if t and d and re.search(r'확장팩|스타트 덱|스타터 세트|스페셜|하이클래스', t.group(1)):
        known[i] = {"pid": i, "title": t.group(1).strip(), "release": d.group(1)}
        print(i, d.group(1), t.group(1).strip())
    time.sleep(0.25)
json.dump(sorted(known.values(), key=lambda o: o["pid"]), open("kr_official.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
