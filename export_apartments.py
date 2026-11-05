#!/usr/bin/env python3
"""Export 'Загальна кількість квартир' for every Kyiv building from municipal.kiev.ua.

Usage:  python3 export_apartments.py [--workers 4] [--out kyiv_apartments.csv] [--limit N]

Resumable: rows already in the output CSV (by condominium id) are skipped on rerun.
Only uses the Python standard library.
"""
import argparse, csv, http.cookiejar, json, os, re, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://municipal.kiev.ua/kiev/"
CITY = "Київ"
LABEL = "Загальна кількість квартир"
FIELDS = ["street", "house", "organization", "apartments", "passport_status", "passport_date",
          "street_id", "house_id", "condominium_id", "error"]


class Session:
    """One server-side session; the site keeps the 'current house' in session state."""

    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0 (data export script)")]
        self.get("")

    def get(self, path, **params):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(5):
            try:
                with self.opener.open(url, timeout=60) as r:
                    return r.read().decode("utf-8", "replace")
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)

    def locator(self, cmd, id=None):
        params = {"cmd": cmd}
        if id:
            params["id"] = id
        return [x for x in json.loads(self.get("daemons/locator", **params))["data"] if x["id"]]

    def passport(self, condominium_id):
        self.get("renderers/house/index.jsp", id=condominium_id)
        self.get("renderers/house/menu.jsp", item="passport")
        self.get("renderers/engine/index.jsp", domain="passport")
        self.get("renderers/engine/menu.jsp", item="view")
        return self.get("renderers/engine/content.jsp")


def clean(s):
    return " ".join(re.sub(r"<[^>]+>", " ", s or "").split())


def parse(html):
    status = date = ""
    m = re.search(r'text-align:right">(.*?)</div>', html, re.S)
    if m:
        hdr = clean(m.group(1))
        d = re.search(r"\d{4}-\d{2}-\d{2}", hdr)
        date = d.group(0) if d else ""
        status = hdr.replace(date, "").strip()
    apartments = ""
    i = html.find(LABEL)
    if i >= 0:
        m = re.search(r'engine-cell-value">(.*?)</td>', html[i:], re.S)
        if m:
            apartments = clean(m.group(1))
    return apartments, status, date


local = threading.local()


def session():
    if not hasattr(local, "s"):
        local.s = Session()
    return local.s


def houses_for_street(street):
    s = session()
    out = []
    for h in s.locator("house", street["id"]):
        orgs = s.locator("condominimum", h["id"]) or [{"id": "", "name": ""}]
        for o in orgs:
            out.append({"street": street["name"], "house": h["name"], "organization": o["name"],
                        "street_id": street["id"], "house_id": h["id"], "condominium_id": o["id"]})
    return out


def fetch(row):
    row = dict(row, apartments="", passport_status="", passport_date="", error="")
    if not row["condominium_id"]:
        row["error"] = "no organization"
        return row
    try:
        html = session().passport(row["condominium_id"])
        row["apartments"], row["passport_status"], row["passport_date"] = parse(html)
        if "Немає інформації" in html:
            row["error"] = "no passport data"
        elif not row["apartments"]:
            row["error"] = "field not found"
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="kyiv_apartments.csv")
    ap.add_argument("--limit", type=int, default=0, help="only first N streets (testing)")
    a = ap.parse_args()

    done = set()
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8-sig") as f:
            done = {r["condominium_id"] for r in csv.DictReader(f)
                    if r["error"] in ("", "field not found", "no organization", "no passport data")}
    new_file = not os.path.exists(a.out)

    s = Session()
    city = next(c for c in s.locator("city") if c["name"] == CITY)
    streets = s.locator("street", city["id"])
    if a.limit:
        streets = streets[:a.limit]
    print(f"{len(streets)} streets; {len(done)} buildings already exported", flush=True)

    lock = threading.Lock()
    with open(a.out, "a", newline="", encoding="utf-8-sig") as f, ThreadPoolExecutor(a.workers) as pool, \
            ThreadPoolExecutor(2) as lister:
        w = csv.DictWriter(f, FIELDS)
        if new_file:
            w.writeheader()
        n = 0
        for si, rows in enumerate(lister.map(houses_for_street, streets), 1):
            todo = [r for r in rows if r["condominium_id"] not in done or not r["condominium_id"]]
            for fut in as_completed([pool.submit(fetch, r) for r in todo]):
                r = fut.result()
                with lock:
                    w.writerow({k: r.get(k, "") for k in FIELDS})
                    n += 1
            f.flush()
            print(f"[{si}/{len(streets)}] {streets[si-1]['name']}: {len(todo)} new (total new {n})", flush=True)


if __name__ == "__main__":
    main()
