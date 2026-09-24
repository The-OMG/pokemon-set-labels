import json, time, urllib.request, urllib.parse, sys
UA = {"User-Agent": "SetLabelPress/1.0 (personal fan tool)"}
def get(u):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 * (a + 1)); err = e
    raise err
out = {}
for lang in ["ja", "ko", "zh-tw", "zh-cn"]:
    lst = get(f"https://api.tcgdex.net/v2/{lang}/sets")
    det = []
    for s in lst:
        d = get(f"https://api.tcgdex.net/v2/{lang}/sets/{urllib.parse.quote(s['id'])}")
        d.pop("cards", None); det.append(d); time.sleep(0.15)
    out[lang] = det
    print(lang, len(det), sum(1 for d in det if d.get("logo")), sum(1 for d in det if d.get("symbol")), flush=True)
json.dump(out, open("tcgdex_raw.json", "w"), ensure_ascii=False, indent=1)
