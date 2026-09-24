import json, time, urllib.request, urllib.parse, os, hashlib
UA = {"User-Agent": "SetLabelPress/1.0 (personal fan tool; low-volume)"}
R = json.load(open("ja_records.json", encoding="utf-8"))
want = {}
for r in R:
    if r["symbol_file"]: want[r["symbol_file"]] = 240
    if r["logo_file"]: want[r["logo_file"]] = 500
names = list(want); info = {}
for i in range(0, len(names), 40):
    batch = names[i:i+40]
    for w in (240, 500):
        q = [n for n in batch if want[n] == w]
        if not q: continue
        u = "https://bulbapedia.bulbagarden.net/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": w, "titles": "|".join("File:" + n for n in q)})
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        norm = {x["to"]: x["from"] for x in d["query"].get("normalized", [])}
        for p in d["query"]["pages"].values():
            ii = (p.get("imageinfo") or [{}])[0]
            src = ii.get("thumburl") if ii.get("width", 0) > w else ii.get("url")
            info[norm.get(p["title"], p["title"])[5:]] = src
        time.sleep(1)
missing = [n for n in names if not info.get(n)]
print("resolved", len(info) - len(missing), "missing", missing)
got = {}
for n, src in info.items():
    if not src: continue
    fn = "img/" + hashlib.md5(n.encode()).hexdigest()[:12] + os.path.splitext(src.split("?")[0])[1].lower()
    if not os.path.exists(fn):
        with urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=60) as resp: open(fn, "wb").write(resp.read())
        time.sleep(0.4)
    got[n] = fn
json.dump(got, open("img_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("downloaded", len(got))
