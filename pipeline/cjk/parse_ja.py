"""Parse Bulbapedia's Japanese expansion list into set records, attach TCGdex set codes."""
import json, re, unicodedata
from datetime import date, datetime

wiki = open("jp_list.wiki", encoding="utf-8").read()
wiki = wiki.split("==Promotional sets==")[0]
wiki = re.sub(r"<!--.*?-->", "", wiki, flags=re.S)
wiki = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", wiki, flags=re.S)

MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                        "September", "October", "November", "December"], 1)}


def parse_date(s):
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})", s)
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}" if m else ""


def files(s):
    return [f.strip() for f in re.findall(r"\[\[File:([^|\]]+)", s)]


def tcg_text(s):
    """Render {{TCG|link|display}} / [[a|b]] to plain text."""
    s = re.sub(r"\{\{TCG\|([^|}]+)\|([^}]+)\}\}", r"\2", s)
    s = re.sub(r"\{\{TCG\|([^}]+)\}\}", r"\1", s)
    s = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''?|\{\{[^}]*\}\}", "", s)
    return s.strip()


def split_br(s):
    return [p.strip() for p in re.split(r"<br\s*/?>", s, flags=re.I) if p.strip()]


records = []
section, era, sub = None, None, None
for block in re.split(r"\n(?==)", wiki):
    head = re.match(r"(=+)\s*(.*?)\s*=+", block)
    if head:
        lvl, title = len(head.group(1)), head.group(2)
        if lvl == 2: section = title
        elif lvl == 3: era, sub = title, None
        elif lvl == 4: sub = title
    for table in re.findall(r"\{\|.*?\n\|\}", block, flags=re.S):
        rows = re.split(r"\n\|-[^\n]*", table)
        hdr = [re.sub(r"^.*\|\s*", "", h).replace("<br>", " / ").strip()
               for h in re.findall(r"^!(.*)$", rows[0] + "\n" + (rows[1] if len(rows) > 1 else ""), flags=re.M)]
        spans = {}  # column index -> [remaining rows, text]
        for row in rows[1:]:
            raw_cells = [c[1:].strip() for c in re.findall(r"^\|(?![-}]).*$", row, flags=re.M)]
            if not raw_cells: continue
            cells, it = [], iter(raw_cells)
            for col in range(len(hdr)):
                if col in spans and spans[col][0] > 0:
                    cells.append(spans[col][1]); spans[col][0] -= 1; continue
                v = next(it, "")
                m = re.match(r"rowspan\s*=\s*\"?(\d+)\"?\s*\|\s*(.*)$", v)
                if m:
                    v = m.group(2); spans[col] = [int(m.group(1)) - 1, v]
                cells.append(v)
            c = dict(zip(hdr, cells))
            name_cell = next(v for k, v in c.items() if k.startswith("Japanese name"))
            cards_cell = next(v for k, v in c.items() if k.startswith("No. of cards"))
            eng_cell = c.get("English equivalent", "")
            date_s = parse_date(c.get("Release date", ""))
            parts = split_br(name_cell)
            jp_names = [p.strip() for p in re.split(r"\s*[•·]\s*", tcg_text(parts[0]))]
            tr_names = [p.strip() for p in re.split(r"\s*[•·]\s*", tcg_text(parts[1]))] if len(parts) > 1 else []
            counts = split_br(cards_cell)
            syms = files(c.get("Symbol", ""))
            logos = files(c.get("Logo", ""))
            n = max(len(jp_names), 1)
            if len(counts) > n and len(jp_names) == 1 and ":" in parts[0]:
                # "時空の創造: ダイヤモンドコレクション • パールコレクション" style pair written as one title
                base, rest = parts[0].split(":", 1)
                jp_names = [base.strip() + " " + x.strip() for x in re.split(r"\s*[•·]\s*", rest)]
                n = len(jp_names)
            for i in range(n):
                cnt = counts[i] if i < len(counts) else (counts[0] if counts else "")
                m = re.match(r"\s*(\d+)\s*(?:\((\d+|TBA)\))?", tcg_text(cnt))
                records.append({
                    "name": jp_names[i],
                    "name_en": tr_names[i] if i < len(tr_names) else (tr_names[0] if tr_names else ""),
                    "english_equivalent": tcg_text(eng_cell),
                    "era": re.sub(r"\s+(Era|Series)$", "", era or ""),
                    "type": "Main Series Expansion" if section == "Main Sets" else "Special Expansion",
                    "subtype": sub or "",
                    "cards": int(m.group(1)) if m else None,
                    "secret": int(m.group(2)) if m and m.group(2) and m.group(2).isdigit() else 0,
                    "release": date_s,
                    "symbol_file": syms[i] if i < len(syms) else (syms[0] if syms else None),
                    "logo_file": logos[i] if i < len(logos) else (logos[0] if len(logos) == 1 and n == 1 else None),
                })

# ---- attach set codes from TCGdex by Japanese name + nearby date ----
raw = json.load(open("tcgdex_raw.json", encoding="utf-8"))["ja"]
raw = [s for s in raw if not s["id"].startswith("CS") and not s["id"].startswith("CSA")]


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s・•:：「」『』＆&]", "", s).lower()


def days(a, b):
    try: return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).days)
    except Exception: return 9999


used = set()
for r in records:
    best, best_exact = None, False
    for s in raw:
        if s["id"] in used: continue
        nm, sd = norm(s["name"]), s.get("releaseDate", "")
        if (norm(r["name"]) == nm or norm(r["name"]).endswith(nm) or nm.endswith(norm(r["name"]))) and days(r["release"], sd) <= 45:
            # prefer the "+"-style official code over the TCGdex "p" duplicate
            exact = norm(r["name"]) == nm
            if best is None or (exact and not best_exact) or (exact == best_exact and best["id"].endswith("p") and s["id"].endswith("+")):
                best, best_exact = s, exact
    if best:
        r["code"] = best["id"].replace("sm2+", "SM2+")
        used.add(best["id"])
        for twin in raw:  # consume the duplicate twin (SM1p vs SM1+)
            if twin["id"] != best["id"] and norm(twin["name"]) == norm(best["name"]) and twin.get("releaseDate") == best.get("releaseDate"):
                used.add(twin["id"])
    else:
        r["code"] = ""

MANUAL = {"ライジングフィスト": "XY3", "幻・伝説ドリームキラコレクション": "CP5", "25th ANNIVERSARY COLLECTION": "S8a",
          "Pokémon GO": "S10b", "シャイニートレジャーex": "SV4a", "30th CELEBRATION": "M6a", "闇からの挑戦": "PMCG6",
          "ステラミラクル": "SV7"}
for r in records:
    if r["name"] in MANUAL: r["code"] = MANUAL[r["name"]]
records = [r for r in records if r["release"]]  # drop announced-but-undated sets
# paired sets released together share the combined logo printed once on the list
for a, b in zip(records, records[1:]):
    if b["logo_file"] is None and a["logo_file"] and a["release"] == b["release"] and a["era"] == b["era"] and a["type"] == b["type"]:
        b["logo_file"] = a["logo_file"]
json.dump(records, open("ja_records.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(records), "records;", sum(1 for r in records if r["code"]), "with codes")
print("unmatched TCGdex:", [(s["id"], s["name"]) for s in raw if s["id"] not in used])
for r in records:
    if not r["release"] or r["cards"] is None: print("INCOMPLETE", r)
