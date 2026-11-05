# Квартири в будинках Києва

Interactive map of the total number of apartments («Загальна кількість квартир (приміщень, призначених для проживання)») in Kyiv residential buildings.

**Map:** https://r0ka.github.io/kyiv-apartments-map/

- Source: building passports on [municipal.kiev.ua](https://municipal.kiev.ua/kiev/) (exported 2026-11-05)
- Coordinates: matched against [OpenStreetMap](https://www.openstreetmap.org/copyright) addresses (© OpenStreetMap contributors, ODbL)
- Full table: [`kyiv_apartments_geo.csv`](kyiv_apartments_geo.csv). The `match` column is `exact`, `base` (main house number only), `street` (street centre) or empty (not located).

## Refreshing the data

```bash
python3 export_apartments.py          # resumable crawl -> kyiv_apartments.csv
curl -s -A kyiv-apartments-map https://overpass-api.de/api/interpreter \
  --data-urlencode 'data=[out:json][timeout:240];area["name:en"="Kyiv"]["admin_level"="4"]->.a;(nwr["addr:housenumber"]["addr:street"](area.a););out center tags;' \
  -o osm_kyiv_addresses.json
python3 geocode.py                    # -> kyiv_apartments_geo.csv, map_data.js
```
