#!/usr/bin/env python3
"""Export new-build complexes (ЖК) for Kyiv + Kyiv region from lun.ua.

Reads the public sitemap (https://lun.ua/sitemaps/building_uk.xml), visits every /new/kyiv/<slug>
page (allowed by robots.txt) politely, and pulls the schema.org JSON-LD + embedded status data.

Output: lun_complexes.csv  (resumable: already exported URLs are skipped)
Usage:  python3 lun_export.py [--workers 2] [--delay 1.0] [--limit N]
"""
import argparse, csv, json, os, re, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
SITEMAP = "https://lun.ua/sitemaps/building_uk.xml"
OUT = "lun_complexes.csv"
FIELDS = ["name", "url", "locality", "address", "lat", "lon", "apartments", "class", "houses", "floors",
          "construction_status", "completion_status", "houses_built", "houses_under_construction",
          "houses_frozen", "completion_dates", "developer", "price_low", "price_high", "error"]
PROPS = {"Кількість квартир": "apartments", "Клас": "class", "Будинків": "houses", "Поверховість": "floors"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "uk"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(5 * 2 ** attempt)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError("retries exhausted")


def unesc(s):
    return s.replace('\\"', '"')


def parse(url, html):
    row = {k: "" for k in FIELDS}
    row["url"] = url
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if "ApartmentComplex" not in str(d.get("@type")):
            continue
        a, g, o = d.get("address", {}), d.get("geo", {}), d.get("offers", {})
        row.update(name=d.get("name", ""), locality=a.get("addressLocality", ""), address=a.get("streetAddress", ""),
                   lat=g.get("latitude", ""), lon=g.get("longitude", ""),
                   price_low=o.get("lowPrice", ""), price_high=o.get("highPrice", ""),
                   developer="; ".join(s.get("name", "") for s in (o.get("seller") or []) if isinstance(s, dict)))
        for p in d.get("additionalProperty", []):
            if p.get("name") in PROPS:
                row[PROPS[p["name"]]] = p.get("value", "")
    s = unesc(html)
    st = re.search(r'"statuses":\{(.*?)"lastQueueHistory"', s)
    if st:
        def f(k):
            m = re.search(rf'"{k}":"?([^",]*)"?', st.group(1))
            return m.group(1) if m else ""
        row.update(construction_status=f("constructionStatus"), completion_status=f("completionStatus"),
                   houses_built=f("housesBuilt"), houses_under_construction=f("housesUnderConstruct"),
                   houses_frozen=f("housesFrozen"))
    posts = sorted(set(re.findall(r'"post":"([^"]+)"', s)), key=lambda x: (x[-4:], x))
    row["completion_dates"] = ", ".join(posts)
    m = re.search(r"\d+", row["apartments"] or "")
    row["apartments"] = m.group(0) if m else ""
    if not row["name"]:
        row["error"] = "no complex data"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--delay", type=float, default=1.0, help="pause per worker between pages, seconds")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", get(SITEMAP)) if "/new/kyiv/" in u]
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8-sig") as f:
            done = {r["url"] for r in csv.DictReader(f) if not r["error"].startswith(("URLError", "Remote", "Timeout", "Runtime", "HTTP Error 5", "HTTP Error 429"))}
    todo = [u for u in urls if u not in done][: a.limit or None]
    print(f"{len(urls)} complexes in sitemap, {len(done)} done, {len(todo)} to fetch", flush=True)

    lock, n = threading.Lock(), [0]
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()

        def work(u):
            try:
                row = parse(u, get(u))
            except Exception as e:
                row = {k: "" for k in FIELDS}
                row.update(url=u, error=f"{type(e).__name__}: {e}"[:200])
            time.sleep(a.delay)
            with lock:
                w.writerow(row); f.flush(); n[0] += 1
                if n[0] % 50 == 0:
                    print(f"{n[0]}/{len(todo)}", flush=True)

        with ThreadPoolExecutor(a.workers) as pool:
            list(pool.map(work, todo))
    print("done", flush=True)


if __name__ == "__main__":
    main()
