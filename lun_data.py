#!/usr/bin/env python3
"""lun_complexes.csv -> lun_data.js for the map.

Each complex: [lat, lon, name, address, apartments|null, class, status, last_completion, developer, url, houses,
               apts_built, apts_building, apts_stopped, n_built, n_building, n_stopped]

LUN's complex-level "constructionStatus" says "built" as soon as ONE house is built, so the status is derived from
the per-house states instead:
  built    every house built
  partial  some houses built, others under construction or stopped
  building no house built, at least one under construction / preparatory work / in design
  frozen   no house built or under construction, at least one suspended / frozen
Apartments are split by house state using LUN's per-house flat counts when they add up to the complex total
(±10 %), otherwise in proportion to the number of houses.
"""
import csv, json, sys, collections

SRC = sys.argv[1] if len(sys.argv) > 1 else "lun_complexes.csv"
BUILT = {"built"}
BUILDING = {"under_construct", "preparatory_work", "in_design", "design"}
STOPPED = {"suspended", "frozen", "canceled"}


def group(state):
    return "built" if state in BUILT else "building" if state in BUILDING else "stopped" if state in STOPPED else None


def houses_of(r):
    """[(group, flats|None)] per house; falls back to the complex-level counters."""
    if r.get("houses_detail"):
        hs = [(group(s), f) for s, f, _ in json.loads(r["houses_detail"])]
        if hs and all(g for g, _ in hs):
            return hs
    n = lambda k: int(r.get(k) or 0)
    hs = [("built", None)] * n("houses_built") + [("building", None)] * n("houses_under_construction") \
        + [("stopped", None)] * (n("houses_frozen") + n("houses_suspended"))
    if not hs:   # nothing per house: use the complex flag
        cs = r["construction_status"]
        hs = [("built" if cs == "built" else "stopped" if cs in STOPPED else "building", None)]
    return hs


def split(total, hs):
    out = collections.Counter()
    flats = [f or 0 for _, f in hs]
    if total and sum(flats) and abs(sum(flats) - total) <= 0.1 * total:
        for (g, _), f in zip(hs, flats):
            out[g] += f
    elif total:
        for g, _ in hs:
            out[g] += total / len(hs)
    return {k: round(v) for k, v in out.items()}


def status(cnt):
    if cnt["built"] and not (cnt["building"] or cnt["stopped"]):
        return "built"
    if cnt["built"]:
        return "partial"
    if cnt["building"]:
        return "building"
    return "frozen"


def last_date(s):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return max(parts, key=lambda p: (p[-4:], p)) if parts else ""


rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8-sig")) if r["lat"] and not r["error"]]
seen, out = set(), []
for r in rows:
    if r["url"] in seen:
        continue
    seen.add(r["url"])
    total = int(r["apartments"]) if r["apartments"].isdigit() else None
    hs = houses_of(r)
    cnt = collections.Counter(g for g, _ in hs)
    a = split(total, hs)
    out.append([round(float(r["lat"]), 6), round(float(r["lon"]), 6), r["name"],
                (r["locality"] + ", " if r["locality"] and r["locality"] != "Київ" else "") + r["address"],
                total, r["class"], status(cnt), last_date(r["completion_dates"]), r["developer"],
                r["url"].replace("https://lun.ua", ""), r["houses"],
                a.get("built", 0), a.get("building", 0), a.get("stopped", 0),
                cnt["built"], cnt["building"], cnt["stopped"]])
with open("lun_data.js", "w", encoding="utf-8") as f:
    f.write("window.LUN=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
print(len(out), "complexes;", collections.Counter(c[6] for c in out).most_common(),
      "| apartments built", sum(c[11] for c in out), "building", sum(c[12] for c in out), "stopped", sum(c[13] for c in out))
