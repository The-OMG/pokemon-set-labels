"""Traditional Chinese expansions from the official Pokémon Asia site (asia.pokemon-card.com/tw).

tw_official.json: every product on the card-search index (code, series, title, release date).
tw_counts.json:   printed card count (the "MMM" in "NNN/MMM") read off the first card of each Taiwan-only
                  set, i.e. a set with no Japanese twin to borrow counts from.
"""
import html, json, re, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Set Label Press data pipeline)"}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8")
out, page = [], 1
while page <= 40:
    h = get(f"https://asia.pokemon-card.com/tw/card-search/?pageNo={page}")
    items = re.findall(r'expansionCodes=([^"]+)".*?class="series">([^<]*)<.*?class="expansionTitle">\s*(.*?)\s*</h3>.*?datetime="([^"]+)"', h, re.S)
    if not items: break
    for code, ser, title, dt in items:
        m, d, y = dt.split("-")
        out.append({"id": html.unescape(code), "series": html.unescape(ser.strip()), "title": html.unescape(re.sub(r"\s+", " ", title)), "release": f"{y}-{m}-{d}"})
    page += 1; time.sleep(0.5)
json.dump(out, open("tw_official.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "products")

ja_codes = {r["code"] for r in json.load(open("ja_records.json", encoding="utf-8")) if r["code"]}
try: counts = json.load(open("tw_counts.json"))
except FileNotFoundError: counts = {}
for p in out:
    if p["id"] in ja_codes or p["id"] in counts or "擴充包" not in p["title"]: continue
    h = get(f"https://asia.pokemon-card.com/tw/card-search/list/?expansionCodes={p['id']}")
    for link in re.findall(r'href="(/tw/card-search/detail/\d+/)"', h)[:3]:
        m = re.search(r"\b(\d{3})/(\d{3})\b", re.sub(r"<[^>]+>", " ", get("https://asia.pokemon-card.com" + link)))
        if m: counts[p["id"]] = int(m.group(2)); print(p["id"], counts[p["id"]]); break
        time.sleep(0.3)
    time.sleep(0.4)
json.dump(counts, open("tw_counts.json", "w"), indent=1)
