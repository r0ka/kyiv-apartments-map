#!/usr/bin/env python3
"""lun_complexes.csv -> lun_data.js for the map.

Each complex: [lat, lon, name, address, apartments|null, class, status, last_completion, developer, url, houses]
status: built | building | frozen | other
"""
import csv, json, re, collections


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


rows = [r for r in csv.DictReader(open("lun_complexes.csv", encoding="utf-8-sig")) if r["lat"] and not r["error"]]
seen, out = set(), []
for r in rows:
    if r["url"] in seen:
        continue
    seen.add(r["url"])
    out.append([round(float(r["lat"]), 6), round(float(r["lon"]), 6), r["name"],
                (r["locality"] + ", " if r["locality"] and r["locality"] != "Київ" else "") + r["address"],
                int(r["apartments"]) if r["apartments"].isdigit() else None, r["class"], status(r),
                last_date(r["completion_dates"]), r["developer"], r["url"].replace("https://lun.ua", ""),
                r["houses"]])
with open("lun_data.js", "w", encoding="utf-8") as f:
    f.write("window.LUN=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
print(len(out), "complexes;", collections.Counter(c[6] for c in out).most_common(),
      "| raw statuses:", collections.Counter(r["construction_status"] for r in rows).most_common())
