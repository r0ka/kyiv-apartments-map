#!/usr/bin/env python3
"""Find the most attractive spots for a new minimarket.

Demand      = apartments in municipal buildings within RADIUS of the spot
Competition = competing food stores (minimarket / supermarket / hypermarket / market) within RADIUS
Score       = demand / (competition + 1)

Every point of a 100 m grid over Kyiv is scored; spots need at least MIN_APTS apartments in reach, and the
best ones are picked greedily at least MIN_GAP apart. LUN new-builds are attached for information only.

Output: spots_data.js -> window.SPOTS = [[lat, lon, score, apts, stores, nearest_m, buildings, lun_built,
                                          lun_building, near_address], ...]  (best first)
"""
import json, math, re, collections

RADIUS, STEP, MIN_APTS, MIN_GAP, TOP = 500, 100, 1500, 800, 25
MAX_APTS_PER_BUILDING = 1500
COMPETING = {"Продукти / мінімаркет", "Супермаркет", "Гіпермаркет / універмаг", "Ринок"}
KY = 111320.0                                  # metres per degree latitude
KX = 111320.0 * math.cos(math.radians(50.45))  # metres per degree longitude at Kyiv


def load(path, var):
    return json.loads(re.sub(rf"^window\.{var}=|;\s*$", "", open(path, encoding="utf-8").read()))


def xy(lat, lon):
    return lon * KX, lat * KY


class Grid:
    """Bucket points into RADIUS-sized cells for fast neighbourhood queries."""
    def __init__(self, items):
        self.cells = collections.defaultdict(list)
        for it in items:
            x, y = xy(it[0], it[1])
            self.cells[(int(x // RADIUS), int(y // RADIUS))].append((x, y, it))

    def near(self, x, y, r=RADIUS):
        cx, cy = int(x // RADIUS), int(y // RADIUS)
        k = int(math.ceil(r / RADIUS))
        for i in range(cx - k, cx + k + 1):
            for j in range(cy - k, cy + k + 1):
                for px, py, it in self.cells.get((i, j), ()):
                    d = math.hypot(px - x, py - y)
                    if d <= r:
                        yield d, it


def main():
    # exact or near-exact points; >1500 apartments in one building are data errors on the source site
    # (e.g. Харківське шосе 19А = 48 610), so those values are ignored
    buildings = [b for b in load("map_data.js", "BUILDINGS") if b[7] in ("e", "b")]
    buildings = [b[:5] + [None if (b[5] or 0) > MAX_APTS_PER_BUILDING else b[5]] + b[6:] for b in buildings]
    stores = [s for s in load("stores_data.js", "STORES") if s[4] in COMPETING]
    lun = load("lun_data.js", "LUN")
    gb, gs, gl = Grid(buildings), Grid(stores), Grid(lun)

    xs = [xy(b[0], b[1]) for b in buildings]
    x0, x1 = min(p[0] for p in xs), max(p[0] for p in xs)
    y0, y1 = min(p[1] for p in xs), max(p[1] for p in xs)

    cands = []
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            near_b = list(gb.near(x, y))
            apts = sum(b[5] or 0 for _, b in near_b)
            # the spot itself should be inside the housing, not in a park: a building within 150 m
            if apts >= MIN_APTS and any(d <= 150 for d, _ in near_b):
                comp = list(gs.near(x, y, 1500))
                n_in = sum(1 for d, _ in comp if d <= RADIUS)
                nearest = min((d for d, _ in comp), default=1500)
                score = apts / (n_in + 1)
                cands.append((score, nearest, x, y, apts, n_in, len(near_b), near_b))
            x += STEP
        y += STEP

    cands.sort(key=lambda c: (-c[0], -c[1]))
    picked = []
    for c in cands:
        if all(math.hypot(c[2] - p[2], c[3] - p[3]) >= MIN_GAP for p in picked):
            picked.append(c)
            if len(picked) == TOP:
                break

    out = []
    for score, nearest, x, y, apts, n_in, nb, near_b in picked:
        lat, lon = y / KY, x / KX
        lb = [c for _, c in gl.near(x, y) if c[6] == "built"]
        lu = [c for _, c in gl.near(x, y) if c[6] == "building"]
        d0, b0 = min(near_b, key=lambda t: t[0])
        out.append([round(lat, 6), round(lon, 6), round(score), apts, n_in, round(nearest), nb,
                    sum(c[4] or 0 for c in lb), sum(c[4] or 0 for c in lu), f"{b0[2]}, {b0[3]}"])
    with open("spots_data.js", "w", encoding="utf-8") as f:
        f.write("window.SPOTS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"{len(cands)} candidate points scored; top {len(out)}:")
    for i, s in enumerate(out, 1):
        print(f"{i:2}. {s[9][:45]:45}  score {s[2]:>5}  apts {s[3]:>5}  stores {s[4]}  nearest {s[5]:>4} m  "
              f"LUN built {s[7]}, building {s[8]}")


if __name__ == "__main__":
    main()
