#!/usr/bin/env python3
"""Turn osm_kyiv_food.json (Overpass export) into stores_data.js for the map.

Each store: [lat, lon, name, brand, category]
"""
import json, re, collections

CATEGORIES = {
    "supermarket": "Супермаркет", "convenience": "Продукти / мінімаркет", "grocery": "Продукти / мінімаркет",
    "general": "Продукти / мінімаркет", "food": "Продукти / мінімаркет",
    "marketplace": "Ринок", "department_store": "Гіпермаркет / універмаг", "wholesale": "Гіпермаркет / універмаг",
    "alcohol": "Алкоголь / напої", "beverages": "Алкоголь / напої",
    "bakery": "Пекарня", "butcher": "М'ясо / риба", "seafood": "М'ясо / риба",
    "dairy": "Молочні / делікатеси", "deli": "Молочні / делікатеси", "frozen_food": "Заморожені продукти",
    "greengrocer": "Овочі / фрукти",
}
# brand aliases -> canonical name (compared case-insensitively, ignoring punctuation)
ALIASES = {"атб маркет": "АТБ", "атб": "АТБ", "atb": "АТБ", "сільпо": "Сільпо", "silpo": "Сільпо",
           "novus": "Novus", "новус": "Novus", "фора": "Фора", "fora": "Фора", "varus": "Varus",
           "ашан": "Ашан", "auchan": "Ашан", "metro": "Metro", "метро": "Metro", "епіцентр": "Епіцентр",
           "біле сухе": "Біле Сухе", "le silpo": "Сільпо", "thrash траш": "Траш"}
GENERIC = {"продукти", "мінімаркет", "магазин", "гастроном", "продмаркет", "супермаркет", "продуктовий магазин", "минимаркет"}


def key(s):
    return re.sub(r"[^\w]+", " ", s.lower()).strip()


def main():
    els = json.load(open("osm_kyiv_food.json", encoding="utf-8"))["elements"]
    canon = {}
    raw = collections.Counter()
    for e in els:
        t = e["tags"]
        b = t.get("brand") or t.get("name") or ""
        if b:
            raw[key(b)] += 1
            canon.setdefault(key(b), b)          # first spelling seen wins
    out = []
    for e in els:
        t = e["tags"]
        cat = CATEGORIES.get(t.get("shop") or ("marketplace" if t.get("amenity") == "marketplace" else ""))
        if not cat:
            continue
        lat, lon = (e["lat"], e["lon"]) if "lat" in e else (e["center"]["lat"], e["center"]["lon"])
        name = t.get("name") or t.get("brand") or ""
        b = t.get("brand") or t.get("name") or ""
        k = key(b)
        brand = ALIASES.get(k) or ("" if not k or k in GENERIC or raw[k] < 2 else canon[k])
        out.append([round(lat, 6), round(lon, 6), name, brand, cat])
    with open("stores_data.js", "w", encoding="utf-8") as f:
        f.write("window.STORES=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(len(out), "stores;", collections.Counter(s[4] for s in out).most_common())
    print(collections.Counter(s[3] for s in out if s[3]).most_common(15))


if __name__ == "__main__":
    main()
