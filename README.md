# Квартири в будинках Києва

Interactive map of the total number of apartments («Загальна кількість квартир (приміщень, призначених для проживання)») in Kyiv residential buildings.

**Map:** https://r0ka.github.io/kyiv-apartments-map/

- Source: building passports on [municipal.kiev.ua](https://municipal.kiev.ua/kiev/) (exported 2026-11-05)
- New builds: public complex pages on [lun.ua](https://lun.ua/) (exported 2026-11-06; cottage towns without apartment counts skipped)
- Stores: OpenStreetMap `shop=*` / `amenity=marketplace` (© OpenStreetMap contributors, ODbL)
- Coordinates: matched against [OpenStreetMap](https://www.openstreetmap.org/copyright) addresses (© OpenStreetMap contributors, ODbL)
- **Radius:** pick a centre (button, or «Радіус звідси» in a building card), drag it, set 100 m–5 km; shows buildings, apartments, organisations inside and exports them as CSV.
- **New builds (ЛУН):** ~1,770 apartment complexes in Kyiv and the region from lun.ua (apartments, class, developer, completion date), coloured by status: built / under construction / frozen. Inside the radius their apartments are shown separately, because built complexes may already be in the municipal data.
- **Competitors (food stores):** ~3,900 Kyiv food shops from OpenStreetMap (supermarkets, minimarkets, markets, bakeries…). Filter by category, highlight chains (АТБ, Сільпо, Фора…); inside the radius you get store count by chain, apartments per store and distance to the nearest store. CSV export for buildings and stores.
- **Filters:** apartment count range, approximate locations, buildings without data.
- Full table: [`kyiv_apartments_geo.csv`](kyiv_apartments_geo.csv). The `match` column is `exact`, `base` (main house number only), `street` (street centre) or empty (not located).

## Refreshing the data

```bash
python3 export_apartments.py          # resumable crawl -> kyiv_apartments.csv
curl -s -A kyiv-apartments-map https://overpass-api.de/api/interpreter \
  --data-urlencode 'data=[out:json][timeout:240];area["name:en"="Kyiv"]["admin_level"="4"]->.a;(nwr["addr:housenumber"]["addr:street"](area.a););out center tags;' \
  -o osm_kyiv_addresses.json
python3 geocode.py                    # -> kyiv_apartments_geo.csv, map_data.js
# stores: same Overpass call with
#   (nwr["shop"~"^(supermarket|convenience|grocery|greengrocer|butcher|bakery|deli|dairy|seafood|frozen_food|food|alcohol|beverages|general|department_store|wholesale)$"](area.a);nwr["amenity"="marketplace"](area.a);)
#   saved as osm_kyiv_food.json, then:
python3 stores.py                     # -> stores_data.js
python3 lun_export.py                 # ~2 h, resumable -> lun_complexes.csv
python3 lun_data.py                   # -> lun_data.js
```
