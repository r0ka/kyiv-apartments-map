#!/usr/bin/env python3
"""lun_complexes.csv -> lun_data.js for the map.

Each complex: [lat, lon, name, address, apartments|null, class, status, last_completion, developer, url, houses, dup]
status: built | building | frozen | other
dup: 1 if the complex is probably already in the municipal data (address match, or a municipal building
     with exact coordinates within 30 m), so its apartments must not be added again.
"""
import csv, json, math, collections
import lun_match


def status(r):
    cs = r["construction_status"]
    if r["houses_frozen"] not in ("", "0") and r["houses_under_construction"] in ("", "0") and cs != "built":
        return "frozen"
    if cs == "built" or r["completion_status"] == "ready":
        return "built"
    if cs in ("under_construct", "preparatory_work", "in_design", "design"):
        return "building"
    if cs in ("frozen", "suspended"):
        return "frozen"
    return "other"


def last_date(s):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return max(parts, key=lambda p: (p[-4:], p)) if parts else ""


idx = lun_match.municipal_index()
grid = collections.defaultdict(list)       # ~100 m cells of exact municipal points
for r in csv.DictReader(open("kyiv_apartments_geo.csv", encoding="utf-8-sig")):
    if r["match"] == "exact":
        la, lo = float(r["lat"]), float(r["lon"])
        grid[(round(la * 1000), round(lo * 700))].append((la, lo))


def near_municipal(la, lo, m=30):
    ci, cj = round(la * 1000), round(lo * 700)
    return any(math.hypot((la - a) * 111320, (lo - b) * 71000) <= m
               for i in (ci - 1, ci, ci + 1) for j in (cj - 1, cj, cj + 1) for a, b in grid.get((i, j), []))


rows = [r for r in csv.DictReader(open("lun_complexes.csv", encoding="utf-8-sig")) if r["lat"] and not r["error"]]
seen, out = set(), []
for r in rows:
    if r["url"] in seen:
        continue
    seen.add(r["url"])
    la, lo = float(r["lat"]), float(r["lon"])
    dup = int(r["locality"] == "Київ" and (bool(lun_match.match(r["address"], idx)) or near_municipal(la, lo)))
    out.append([round(la, 6), round(lo, 6), r["name"],
                (r["locality"] + ", " if r["locality"] and r["locality"] != "Київ" else "") + r["address"],
                int(r["apartments"]) if r["apartments"].isdigit() else None, r["class"], status(r),
                last_date(r["completion_dates"]), r["developer"], r["url"].replace("https://lun.ua", ""),
                r["houses"], dup])
with open("lun_data.js", "w", encoding="utf-8") as f:
    f.write("window.LUN=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
c = collections.Counter((x[6], x[11]) for x in out)
print(len(out), "complexes; (status, dup):", sorted(c.items()))
print("built apartments added:", sum(x[4] or 0 for x in out if x[6] == "built" and not x[11]),
      "| skipped as duplicates:", sum(x[4] or 0 for x in out if x[6] == "built" and x[11]))
