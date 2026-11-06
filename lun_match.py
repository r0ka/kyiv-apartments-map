"""Match lun.ua complexes to municipal.kiev.ua buildings by address, to avoid double-counting apartments."""
import csv, re, collections
import geocode as g

TYPES = {"вул": "вулиця", "просп": "проспект", "пров": "провулок", "бульв": "бульвар", "пл": "площа",
         "наб": "набережна", "набережна": "набережна", "шосе": "шосе", "узвіз": "узвіз", "проїзд": "проїзд",
         "туп": "тупик", "дорога": "дорога", "площа": "площа", "проспект": "проспект", "бульвар": "бульвар"}


def municipal_index():
    """house number -> [(street tokens, row)]"""
    idx = collections.defaultdict(list)
    for r in csv.DictReader(open("kyiv_apartments_geo.csv", encoding="utf-8-sig")):
        typ, names, other = g.site_street(r["street"])
        if other:
            continue
        for t in names:
            idx[g.norm_house(r["house"])].append((t, r))
    return idx


def same_street(a, b):
    """'антоновича' vs 'антоновича володимира': equal, or one is a subset with a meaningful word."""
    if not a or not b:
        return False
    return a == b or ((a < b or b < a) and any(len(w) > 3 for w in (a & b)))


def houses(spec):
    """'14-20' -> 14..20, '1, 1а, 1б' -> [1,1А,1Б], '26а' -> [26А]"""
    out = []
    for part in re.split(r",\s*", spec):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m and int(m.group(2)) - int(m.group(1)) <= 40:
            out += [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif re.match(r"\d", part):
            out.append(g.norm_house(part.split(" ")[0]))
    return out


def parse(addr):
    """'вул. Булгакова, 13' / 'Харківське шосе, 19' / 'просп. Берестейський, 119-121' -> (tokens, [houses])"""
    first = addr.split(" / ")[0]
    if "," not in first:
        return None
    street, spec = first.split(",", 1)
    words = [w.strip(".") for w in street.split()]
    words = [w for w in words if w.lower() not in TYPES]
    return (g.tokens(" ".join(words)), houses(spec)) if words else None


def match(addr, idx):
    """Return matched municipal rows (deduplicated) or []."""
    p = parse(addr)
    if not p:
        return []
    t, hs = p
    rows = {}
    for h in hs:
        for tt, r in idx.get(h, []):
            if same_street(t, tt):
                rows[r["condominium_id"] or r["house_id"]] = r
    return list(rows.values())


if __name__ == "__main__":
    idx = municipal_index()
    lun = [r for r in csv.DictReader(open("lun_complexes.csv", encoding="utf-8-sig")) if not r["error"] and r["locality"] == "Київ"]
    c = collections.Counter()
    for r in lun:
        c[(r["construction_status"], bool(match(r["address"], idx)))] += 1
    for k, v in sorted(c.items()):
        print(k, v)
