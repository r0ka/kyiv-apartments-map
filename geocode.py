#!/usr/bin/env python3
"""Attach coordinates to kyiv_apartments.csv by matching addresses with OpenStreetMap data.

Input:  kyiv_apartments.csv, osm_kyiv_addresses.json (Overpass export of Kyiv addr:* objects)
Output: kyiv_apartments_geo.csv (adds lat, lon, match), map_data.js (for kyiv_map.html)

match = exact   street + house number found in OSM
        base    only the base number found (e.g. 12/5 -> 12, 7А -> 7): approximate point
        street  only the street found: point is the street's centre (very approximate)
        (empty) not found
"""
import csv, json, re, collections, difflib

TYPES = {"вул": "вулиця", "просп": "проспект", "пров": "провулок", "бульв": "бульвар",
         "пл": "площа", "шосе": "шосе", "узвіз": "узвіз", "наб": "набережна", "туп": "тупик",
         "проїзд": "проїзд", "алея": "алея", "дорога": "дорога", "просіка": "просіка", "лінія": "лінія",
         "майдан": "майдан", "острів": "острів"}
FULL = set(TYPES.values())
OTHER_PLACE = re.compile(r"\b(м\.|м\s|смт|с\.|Борщагівка|Ірпінь|Вишневе)\b", re.I)


def norm_word(w):
    return re.sub(r"[«»\"“”„]", "", w.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")).strip(".,")


def tokens(s):
    return frozenset(norm_word(w) for w in re.split(r"[\s\-\u2010-\u2015]+", s) if w)


def site_street(name):
    """'Бандери Степана (Московський) просп' -> type, [token sets: current, old]."""
    m = re.match(r"^(.*?)\s*(?:\((.*?)\))?\s*(\S+)$", name.strip())
    main, old, typ = m.group(1), m.group(2), m.group(3)
    if typ.lower() not in TYPES:          # e.g. '17 км Житомирське шосе' / unusual endings
        main, old, typ = name, None, ""
    typ = TYPES.get(typ.lower(), "")
    if old and OTHER_PLACE.search(old):   # '(смт Козин)', '(м.Ірпінь)': other locality
        return typ, [], True
    names = [tokens(main)] + ([tokens(old)] if old else [])
    return typ, names, bool(OTHER_PLACE.search(name))


def osm_street(name):
    t = tokens(name)
    typ = next((w for w in t if w in FULL), "")
    return typ, t - {typ}


def norm_house(h):
    h = re.sub(r"\(.*?\)", "", h).upper().replace(" ", "")
    h = re.sub(r"(\d)-([А-ЯІЇЄҐ])\b", r"\1\2", h)          # 9-А -> 9А
    h = h.replace("К.", "К").replace("КОРП.", "К").replace("КОРП", "К")
    return h


def base_house(h):
    m = re.match(r"\d+", h)
    return m.group(0) if m else h


def main():
    osm = json.load(open("osm_kyiv_addresses.json", encoding="utf-8"))["elements"]
    by_street = collections.defaultdict(dict)   # (type, tokens) -> house -> (lat, lon)
    for e in osm:
        t = e["tags"]
        lat, lon = (e["lat"], e["lon"]) if "lat" in e else (e["center"]["lat"], e["center"]["lon"])
        key = osm_street(t["addr:street"])
        key = (key[0], key[1])
        for hn in t["addr:housenumber"].split(";"):
            by_street[key].setdefault(norm_house(hn), (lat, lon))
    streets_by_tokens = collections.defaultdict(list)
    for key in by_street:
        streets_by_tokens[key[1]].append(key)

    def find_street(typ, names):
        for t in names:
            cands = [k for k in streets_by_tokens.get(t, []) if not typ or k[0] == typ] \
                    or streets_by_tokens.get(t, [])
            if cands:
                return cands[0]
        for t in names:                           # OSM name is a subset ('Антоновича' vs 'Антоновича Володимира')
            cands = [k for k in by_street if (k[0] == typ or not typ) and k[1] and k[1] < t]
            cands = [k for k in cands if len(k[1]) >= 1 and any(len(w) > 3 for w in k[1])]
            if len(cands) == 1:
                return cands[0]
        for t in names:                           # spelling variants ('Геннадія' vs 'Генадія')
            for k in by_street:
                if (k[0] == typ or not typ) and len(k[1]) == len(t) and len(t) > 0 and all(
                        max(difflib.SequenceMatcher(None, a, b).ratio() for b in k[1]) >= 0.85 for a in t):
                    return k
        return None

    rows = list(csv.DictReader(open("kyiv_apartments.csv", encoding="utf-8-sig")))
    seen, out, cache = set(), [], {}
    for r in rows:                                # drop duplicates left by resumed runs
        k = (r["condominium_id"], r["house_id"])
        if k in seen:
            continue
        seen.add(k)
        if r["street"] not in cache:
            typ, names, other = site_street(r["street"])
            cache[r["street"]] = None if other else find_street(typ, names)
        sk = cache[r["street"]]
        lat = lon = match = ""
        if sk:
            houses = by_street[sk]
            h = norm_house(r["house"])
            if h in houses:
                (lat, lon), match = houses[h], "exact"
            elif base_house(h) in houses:
                (lat, lon), match = houses[base_house(h)], "base"
            else:
                pts = list(houses.values())
                lat = sum(p[0] for p in pts) / len(pts)
                lon = sum(p[1] for p in pts) / len(pts)
                match = "street"
        r.update(lat=lat and round(lat, 6), lon=lon and round(lon, 6), match=match)
        out.append(r)

    fields = list(rows[0].keys()) + ["lat", "lon", "match"]
    with open("kyiv_apartments_geo.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(out)

    pts = [[r["lat"], r["lon"], r["street"], r["house"], r["organization"],
            int(r["apartments"]) if r["apartments"].isdigit() else None,
            r["passport_date"], r["match"][0]]
           for r in out if r["lat"] != ""]
    with open("map_data.js", "w", encoding="utf-8") as f:
        f.write("window.BUILDINGS=" + json.dumps(pts, ensure_ascii=False, separators=(",", ":")) + ";\n")

    c = collections.Counter(r["match"] or "none" for r in out)
    print(f"{len(out)} buildings: " + ", ".join(f"{k}={v}" for k, v in c.most_common()))
    unmatched = collections.Counter(r["street"] for r in out if not r["match"])
    print("top unmatched streets:", unmatched.most_common(15))


if __name__ == "__main__":
    main()
