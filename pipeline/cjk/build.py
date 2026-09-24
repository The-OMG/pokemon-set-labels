"""Build Set Label Press data files for Japanese, Korean, Traditional Chinese and Simplified Chinese.

Sources:
  ja    Bulbapedia "List of Japanese Pokémon Trading Card Game expansions" (+ TCGdex for set codes)
  ko    pokemoncard.co.kr official product pages (names, release dates), matched to the Japanese twin
  zh-tw asia.pokemon-card.com/tw official expansion list (codes, names, dates), matched to the Japanese twin by code
  zh-cn TCGdex zh-cn (mainland Simplified Chinese line)
Korean and Traditional Chinese boosters are localizations of Japanese sets, so card counts and set symbols
come from the matching Japanese record. Anything without a Japanese twin keeps the counts its source gives, or none.
"""
import base64, hashlib, io, json, os, re, unicodedata
from PIL import Image

TODAY = __import__("datetime").date.today().isoformat()
ja = json.load(open("ja_records.json", encoding="utf-8"))
tcg = json.load(open("tcgdex_raw.json", encoding="utf-8"))
imgmap = json.load(open("img_map.json", encoding="utf-8"))

# ---------------- images ----------------
# Symbols are embedded as data URIs (the site recolours / binarises them on a canvas, like the English ones);
# Japanese logos are written as files under public/img/logos/ja/.
PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "public")
LOGO_DIR = os.path.join(PUBLIC, "img", "logos", "ja")
os.makedirs(LOGO_DIR, exist_ok=True)
_sym, _logo = {}, {}


def trimmed(fname):
    im = Image.open(imgmap[fname]).convert("RGBA")
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def symbol_uri(fname):
    if not fname or fname not in imgmap: return None
    if fname not in _sym:
        im = trimmed(fname); im.thumbnail((200, 200), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=88, method=6)
        _sym[fname] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return _sym[fname]


def logo_path(fname):
    if not fname or fname not in imgmap: return None
    if fname not in _logo:
        name = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(fname)[0].lower()).strip("-") + ".webp"
        im = trimmed(fname); im.thumbnail((1000, 500), Image.LANCZOS)
        im.save(os.path.join(LOGO_DIR, name), "WEBP", quality=85, method=6)
        _logo[fname] = "img/logos/ja/" + name
    return _logo[fname]


# Japanese era names as printed on product packaging, keyed by the English era used for filtering
ERA_NATIVE = {
    "ja": {"Original": "ポケットモンスターカードゲーム", "neo": "neo", "VS": "VS", "web": "web", "e-Card": "ポケモンカードe",
           "ADV": "ADV", "PCG": "PCG", "DP": "DP", "DPt": "DPt", "LEGEND": "LEGEND", "BW": "BW", "XY": "XY",
           "XY BREAK": "XY BREAK", "Sun & Moon": "サン＆ムーン", "Sword & Shield": "ソード＆シールド",
           "Scarlet & Violet": "スカーレット＆バイオレット", "MEGA": "MEGA"},
    "ko": {"BW": "BW", "XY": "XY", "XY BREAK": "XY BREAK", "Sun & Moon": "썬&문", "Sword & Shield": "소드&실드",
           "Scarlet & Violet": "스칼렛&바이올렛", "MEGA": "MEGA"},
    "zh-tw": {"Sun & Moon": "太陽＆月亮", "Sword & Shield": "劍＆盾", "Scarlet & Violet": "朱＆紫", "MEGA": "超級進化"},
    "zh-cn": {"Sun & Moon": "太阳&月亮", "Sword & Shield": "剑&盾", "Scarlet & Violet": "朱&紫"},
}


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s・•·:：「」『』＆&!！]", "", s).lower()


def rec(lang, name, era, typ, code, release, cards, secret, name_en="", jp=None, subtype=""):
    return {"name": name, "name_en": name_en, "series": era, "series_native": ERA_NATIVE.get(lang, {}).get(era, era),
            "type": typ, "setno": code or "", "abbr": code or "", "cards": cards, "secret": secret or 0,
            "release": release, "expno": None, "subtype": subtype,
            "symbol_img": symbol_uri(jp["symbol_file"]) if jp else None,
            "logo_img": logo_path(jp["logo_file"]) if (jp and lang == "ja") else None,
            "printed2023": False, "lang": lang}


def number(sets):
    """Sequential expansion numbers in release order, main and special counted separately (like the English data)."""
    sets.sort(key=lambda s: (s["release"], s["setno"]))
    n = {"Main Series Expansion": 0, "Special Expansion": 0}
    seen = set()
    for s in sets:
        if s["type"] in n:
            n[s["type"]] += 1; s["expno"] = n[s["type"]]
        # unique slug: caches in the page key on it, and PNG export names files with it
        base = s["lang"] + "-" + (re.sub(r"[^a-z0-9]+", "-", s["setno"].lower()).strip("-") or hashlib.md5(s["name"].encode()).hexdigest()[:8])
        slug, k = base, 2
        while slug in seen: slug, k = f"{base}-{k}", k + 1
        seen.add(slug); s["slug"] = slug
    return sets


# ---------------- Japanese ----------------
JA = []
for r in ja:
    name = r["name"]
    if name == "パールコレクション": name = "時空の創造 パールコレクション"
    if name.startswith("時空の創造:"): name = name.replace("時空の創造:", "時空の創造")
    JA.append(rec("ja", name, r["era"], r["type"], r["code"], r["release"], r["cards"], r["secret"], r["name_en"], r, r["subtype"]))
number(JA)
by_code = {r["code"]: r for r in ja if r["code"]}
by_jpname = {norm(r["name"]): r for r in ja}

# ---------------- Korean ----------------
KO_TO_JP = {  # Korean name -> Japanese code (or Japanese name for eras without codes)
    "블랙 컬렉션": "ブラックコレクション", "화이트 컬렉션": "ホワイトコレクション", "레드 컬렉션": "レッドコレクション",
    "사이코 드라이브": "サイコドライブ", "헤일 블리자드": "ヘイルブリザード", "다크러시": "ダークラッシュ",
    "드래곤 블라스트": "リューズブラスト", "드래곤 블레이드": "リューノブレード", "프리즈볼트": "フリーズボルト",
    "콜드플레어": "コールドフレア", "플라스마게일": "プラズマゲイル", "스파이럴포스": "ラセンフォース", "볼트너클": "ライデンナックル",
    "메갈로캐논": "メガロキャノン", "샤이니 컬렉션": "シャイニーコレクション", "EX 배틀 부스트": "EXバトルブースト",
    "X컬렉션": "XY1a", "Y컬렉션": "XY1b", "와일드 블레이즈": "XY2", "라이징피스트": "XY3", "팬텀게이트": "XY4",
    "가이아 볼케이노": "XY5a", "타이달스톰": "XY5b", "마그마단vs아쿠아단 더블크라이시스": "CP1", "에메랄드 브레이크": "XY6",
    "밴디트링": "XY7", "푸른 충격": "XY8a", "붉은 섬광": "XY8b", "레전드 컬렉션": "CP2", "천공의 분노": "XY9",
    "초능력의 제왕": "XY10", "포켓심쿵 컬렉션": "CP3", "프리미엄 챔피언팩": "CP4", "타오르는 투사": "XY11a",
    "냉혹한 반역자": "XY11b", "환상・전설 드림 컬렉션": "CP5", "BASE PACK 20th Anniversary": "CP6", "THE BEST OF XY": "THE BEST OF XY",
    "썬 컬렉션": "SM1S", "문 컬렉션": "SM1M", "썬&문": "SM1+", "알로라의 햇빛": "SM2K", "알로라의 달빛": "SM2L",
    "새로운 시련": "SM2+", "어둠을 밝힌 무지개": "SM3H", "빛을 삼킨 어둠": "SM3N", "빛나는 전설": "SM3+",
    "각성의 용사": "SM4S", "초차원의 침략자": "SM4A", "GX 배틀부스트": "SM4+", "울트라썬": "SM5S", "울트라문": "SM5M",
    "울트라포스": "SM5+", "금단의 빛": "SM6", "드래곤스톰": "SM6a", "챔피언로드": "SM6b", "창공의 카리스마": "SM7",
    "페어리라이즈": "SM7b", "버스트임팩트": "SM8", "플라스마 스파크": "SM7a", "다크오더": "SM8a", "태그볼트": "SM9",
    "GX 울트라샤이니": "SM8b", "나이트유니슨": "SM9a", "풀메탈월": "SM9b", "더블블레이즈": "SM10", "GG엔드": "SM10a",
    "스카이레전드": "SM10b", "미라클트윈": "SM11", "리믹스바우트": "SM11a", "드림리그": "SM11b", "얼터제네시스": "SM12",
    "TAG TEAM GX 태그올스타즈": "SM12a", "소드": "S1W", "실드": "S1H", "VMAX라이징": "S1a", "반역크래시": "S2",
    "폭염워커": "S2a", "무한존": "S3", "전설의 고동": "S3a", "앙천의 볼트태클": "S4", "샤이니스타 V": "S4a",
    "연격마스터": "S5R", "일격마스터": "S5I", "쌍벽의 파이터": "S5a", "칠흑의 가이스트": "S6K", "백은의 랜스": "S6H",
    "이브이 히어로즈": "S6a", "창공스트림": "S7R", "마천퍼펙트": "S7D", "25th ANNIVERSARY COLLECTION": "S8a",
    "퓨전아츠": "S8", "VMAX 클라이맥스": "S8b", "스타버스": "S9", "배틀리전": "S9a", "스페이스 저글러": "S10P",
    "타임게이저": "S10D", "Pokémon GO": "S10b", "다크판타스마": "S10a", "로스트어비스": "S11", "백열의 아르카나": "S11a",
    "패러다임트리거": "S12", "VSTAR 유니버스": "S12a", "바이올렛 ex": "SV1V", "스칼렛 ex": "SV1S", "트리플렛비트": "SV1a",
    "클레이버스트": "SV2D", "스노해저드": "SV2P", "포켓몬 카드 151": "SV2a", "흑염의 지배자": "SV3", "레이징서프": "SV3a",
    "미래의 일섬": "SV4M", "고대의 포효": "SV4K", "샤이니트레저 ex": "SV4a", "사이버저지": "SV5M", "와일드포스": "SV5K",
    "크림슨헤이즈": "SV5a", "변환의 가면": "SV6", "나이트원더러": "SV6a", "스텔라미라클": "SV7", "낙원드래고나": "SV7a",
    "초전브레이커": "SV8", "테라스탈 페스타 ex": "SV8a", "배틀파트너즈": "SV9", "열풍의 아레나": "SV9a", "로켓단의 영광": "SV10",
    "화이트플레어": "SV11W", "블랙볼트": "SV11B", "메가심포니아": "M1S", "메가브레이브": "M1L", "인페르노X": "M2",
    "MEGA 드림 ex": "M2a", "니힐제로": "M3", "닌자스피너": "M4", "어비스아이": "M5", "스톰에메랄다": "M6",
    "30th CELEBRATION": "M6a",
}
KO_ERA = [("MEGA", "MEGA"), ("스칼렛&바이올렛", "Scarlet & Violet"), ("소드&실드", "Sword & Shield"),
          ("썬&문", "Sun & Moon"), ("XY BREAK", "XY BREAK"), ("XY", "XY"), ("BW", "BW")]
KO = []; ko_unmatched = []
products = json.load(open("kr_official.json", encoding="utf-8"))
seen = set()
for p in products:
    t = re.sub(r"\s+", " ", p["title"])
    # booster products only: expansion packs, enhanced packs, high-class packs (not decks, kits, boxed sets)
    if not re.search(r"확장팩|하이클래스팩", t) or re.search(r"확장팩 세트|스페셜 키트|포켓몬 카드샵 세트|스페셜 에디션팩", t):
        continue
    names = re.findall(r"「\s*([^」]+?)\s*」", t) or [re.sub(r".*확장팩\s*", "", t).strip()]
    era = next((e for k, e in KO_ERA if k in t), None)
    for nm in names:
        if (nm, p["release"]) in seen: continue
        seen.add((nm, p["release"]))
        target = KO_TO_JP.get(nm)
        jp = by_code.get(target) or by_jpname.get(norm(target or "")) if target else None
        if jp:
            typ = jp["type"]
            era = era or jp["era"]
            KO.append(rec("ko", nm, jp["era"] if jp["era"] in ERA_NATIVE["ko"] else era, typ, jp["code"], p["release"],
                          jp["cards"], jp["secret"], jp["name_en"], jp))
        else:
            ko_unmatched.append((nm, p["release"], t))
            KO.append(rec("ko", nm, era or "Other", "Special Expansion", "", p["release"], None, 0))
number(KO)

# ---------------- Traditional Chinese ----------------
tw_official = json.load(open("tw_official.json", encoding="utf-8"))
tw_tcg = {s["id"]: s for s in tcg["zh-tw"]}
# TCGdex filed a few Taiwanese sets under zh-cn (codes without the mainland "C" suffix)
for s in tcg["zh-cn"]:
    if not re.search(r"C$", s["id"]) and not s["id"].startswith("csm") and s["id"] not in tw_tcg: tw_tcg[s["id"]] = s
TW_ERA = {"太陽＆月亮": "Sun & Moon", "劍＆盾": "Sword & Shield", "朱＆紫": "Scarlet & Violet", "超級進化": "MEGA"}
TW = []; tw_unmatched = []
TW_COUNTS = json.load(open("tw_counts.json"))  # printed "NNN/MMM" read off each set's first official card page
for p in tw_official:
    title = p["title"]
    m = re.match(r"(.*?)「(.+)」(.*)$", title)
    kind, nm, tail = (m.group(1).strip(), m.group(2).strip(), m.group(3).strip()) if m else ("", title, "")
    if not re.search(r"擴充包", kind): continue  # boosters only
    if tail: nm = f"{nm} {tail}"
    era = TW_ERA.get(p["series"].replace("&", "＆"), p["series"])
    jp = by_code.get(p["id"])
    if jp:
        typ = jp["type"]
        TW.append(rec("zh-tw", nm, era, typ, p["id"], p["release"], jp["cards"], jp["secret"], jp["name_en"], jp))
    else:
        src = tw_tcg.get(p["id"])
        cards = TW_COUNTS.get(p["id"]) or (src["cardCount"].get("official") if src else None)
        extra = (src["cardCount"].get("total", 0) - cards) if src and cards else 0
        typ = "Special Expansion" if re.search(r"強化|高級", kind) else "Main Series Expansion"
        tw_unmatched.append((p["id"], nm, p["release"], cards))
        TW.append(rec("zh-tw", nm, era, typ, p["id"][:1].upper() + p["id"][1:2].upper() + p["id"][2:], p["release"], cards, max(extra, 0)))
number(TW)

# ---------------- Simplified Chinese (mainland) ----------------
CN_ERA = {"太阳&月亮": "Sun & Moon", "剑&盾": "Sword & Shield", "朱&紫": "Scarlet & Violet"}
CN = []; cn_seen = set()
for s in tcg["zh-cn"]:
    if not re.search(r"C$", s["id"]) or s["id"] in cn_seen: continue
    cn_seen.add(s["id"])
    era = CN_ERA.get((s.get("serie") or {}).get("name"), "Other")
    nm = s["name"]
    typ = "Special Expansion" if s["id"].startswith("CBB") or re.search(r"\.5C$", s["id"]) else "Main Series Expansion"
    if s["id"].startswith("CSMPi"): typ = "Other"
    cc = s["cardCount"]
    CN.append(rec("zh-cn", nm, era, typ, s["id"], s.get("releaseDate", ""), cc.get("official"),
                  max(0, (cc.get("total") or 0) - (cc.get("official") or 0))))
number(CN)

# ---------------- write ----------------
LANG_META = {
    "ja": {"label": "日本語 · Japanese", "sets": JA, "source": "Bulbapedia’s Japanese expansion list (names, counts, dates, artwork) with set codes from TCGdex"},
    "ko": {"label": "한국어 · Korean", "sets": KO, "source": "pokemoncard.co.kr product pages (names, release dates); card counts, codes and symbols from the matching Japanese set"},
    "zh-tw": {"label": "繁體中文 · Traditional Chinese", "sets": TW, "source": "asia.pokemon-card.com/tw expansion list (codes, names, release dates); card counts and symbols from the matching Japanese set"},
    "zh-cn": {"label": "简体中文 · Simplified Chinese", "sets": CN, "source": "TCGdex (mainland Simplified Chinese sets); no set artwork"},
}
for lang, meta in LANG_META.items():
    fn = "sets_" + lang.replace("-", "") + ".js"
    for s in meta["sets"]: s.pop("lang", None)
    payload = {"lang": lang, "label": meta["label"], "date": TODAY, "source": meta["source"], "sets": meta["sets"]}
    open(os.path.join(PUBLIC, fn), "w", encoding="utf-8").write(
        "window.SLP_LANG = window.SLP_LANG || {};\nwindow.SLP_LANG[" + json.dumps(lang) + "] = " + json.dumps(payload, ensure_ascii=False) + ";\n")

for lang, meta in LANG_META.items():
    S = meta["sets"]
    print(lang, len(S), "sets |", sum(s["type"] == "Main Series Expansion" for s in S), "main,",
          sum(s["type"] == "Special Expansion" for s in S), "special | no count:", sum(s["cards"] is None for s in S),
          "| symbols:", sum(bool(s["symbol_img"]) for s in S), "| logos:", sum(bool(s["logo_img"]) for s in S),
          "|", S[0]["release"], "→", S[-1]["release"])
print("KO unmatched:", ko_unmatched)
print("TW unmatched:", tw_unmatched)
