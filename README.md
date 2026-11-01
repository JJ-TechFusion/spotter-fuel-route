# Fuel Route Planner

Django API that takes a start and finish in the USA and returns the driving route, the cheapest places to refuel along it, and the total fuel cost.

- Vehicle range: 500 miles, 10 mpg
- Fuel prices: `data/fuel_prices.csv` (the supplied file)
- Routing: [OSRM](https://project-osrm.org) public server, free and keyless. **One routing call per trip**; repeat requests are served from cache.
- Geocoding: offline, from the US Census gazetteer bundled in `data/`. No geocoding API calls at all.

Why it's built this way, and what I'd change next, is in [NOTES.md](NOTES.md).

## Setup

### What you need

- **Python 3.12 or newer.** Django 6.1 won't install on older versions. Check with `python3 --version`.
- **git**
- **Internet access** while the server is running, for the routing calls to OSRM. Setup itself works offline once the packages are installed, because all the data files are already in the repo.

There's no database server to install. It uses SQLite, which comes with Python.

### 1. Get the code

```bash
git clone <repo-url> spotter-fuel-route
cd spotter-fuel-route
```

### 2. Create a virtual environment and install packages

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If `python3` points to an older version, call the right one directly, for example `python3.13 -m venv .venv`.

With the venv active, `python --version` should show 3.12 or newer. If it doesn't, see Troubleshooting.

### 3. Create the database

```bash
python manage.py migrate
```

This creates `db.sqlite3` with two tables: places and fuel stations.

### 4. Load the data

```bash
python manage.py load_data
```

It takes a few seconds and should print:

```
Loaded 52489 places and 6423 fuel stations.
Skipped 203 US stations with no gazetteer match, e.g. [...]
```

It reads three files from `data/`:

| File | What it is |
| --- | --- |
| `fuel_prices.csv` | The fuel price list supplied with the assignment |
| `gaz_places.zip` | US Census list of cities and towns, with coordinates |
| `gaz_cousubs.zip` | US Census list of townships and New England towns, used to fill gaps |

You can run it again at any time. It clears the old rows and reloads, so this is also how you pick up a new price file: replace `data/fuel_prices.csv` and run it again.

**Don't skip this step.** Without it every request fails with "Unknown US city", because the city table is empty.

### 5. Start the server

```bash
python manage.py runserver
```

The API is now on `http://127.0.0.1:8000`.

### 6. Check it works

```bash
curl "http://127.0.0.1:8000/api/trips/?start=Chicago,%20IL&finish=Denver,%20CO"
```

You should get JSON with `total_cost`, `fuel_stops` and `map_url`. Open the `map_url` in a browser to see the route.

The first request for a trip takes 1 to 2 seconds, mostly waiting on OSRM. Asking for the same trip again should be almost instant.

### Using Postman

Create a `GET` request to `http://127.0.0.1:8000/api/trips/` and add two query params:

| Key | Value |
| --- | --- |
| `start` | `New York, NY` |
| `finish` | `Los Angeles, CA` |

Postman encodes the spaces and commas for you. To see the map, copy `map_url` from the response into a browser.

Or import `postman/spotter-fuel-route.postman_collection.json` and `postman/local.postman_environment.json`: 18 ready-made requests (trips, map, errors) with tests that check the totals and the 500-mile legs, not only status codes. Run it from the command line with `npx newman run postman/spotter-fuel-route.postman_collection.json -e postman/local.postman_environment.json`.

### Running the tests

```bash
python manage.py test
```

19 tests. They don't call OSRM (it's mocked) and use their own temporary database, so they work offline and don't touch your loaded data.

### Configuration

The defaults work for local use. To change them, set these environment variables before starting the server:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | a dev-only key | Set a real one anywhere outside your own machine |
| `DJANGO_DEBUG` | `1` | Set to `0` to turn debug mode off |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames the server answers to |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Point at another OSRM server, e.g. a self-hosted one |

Vehicle and planning values (range, mpg, how far off the route a station can be, the per-stop overhead) are constants at the bottom of `config/settings.py`.

### Troubleshooting

| Problem | Fix |
| --- | --- |
| `pip install` fails on Django | Your Python is older than 3.12. Recreate the venv with a newer Python. |
| `python --version` shows an old version even with the venv active | Your shell has `python` or `pip` set as an alias, which overrides the venv. Run `unalias python pip`, or call the venv's Python directly: `.venv/bin/python manage.py runserver` |
| Every request says "Unknown US city" | You haven't run `python manage.py load_data`. |
| "Unknown US city" or "Use 'City, ST'" for a real place | Use the two-letter state code (`Austin, TX`, not `Austin, Texas`), or pass coordinates instead (`30.27,-97.74`). |
| 502 "Routing service is unavailable" | The public OSRM server is down or unreachable. Check your connection and try again in a minute. |
| `no such table` errors | Run `python manage.py migrate`, then `load_data`. |
| Want a clean start | Delete `db.sqlite3`, then run `migrate` and `load_data` again. |

## API

### `GET /api/trips/?start=<location>&finish=<location>`

A location is `City, ST` (`Chicago, IL`) or `lat,lon` (`41.88,-87.63`).

```bash
curl "http://127.0.0.1:8000/api/trips/?start=New%20York,%20NY&finish=Los%20Angeles,%20CA"
```

```json
{
  "start": {"lat": 40.6631, "lon": -73.93872},
  "finish": {"lat": 34.01965, "lon": -118.41081},
  "distance_miles": 2810.4,
  "duration_hours": 50.3,
  "total_gallons": 281.04,
  "total_cost": 864.91,
  "fuel_stops": [
    {
      "station": {"id": 62790, "name": "7-ELEVEN #40084", "address": "US-46/US-1/US-9", "city": "Palisades Park",
                  "state": "NJ", "price": 3.099, "location": {"lat": 40.84702, "lon": -73.99706}},
      "mile": 9.0,
      "gallons": 39.39,
      "cost": 122.06
    }
  ],
  "route": {"type": "LineString", "coordinates": [[-73.93872, 40.6631], "..."]},
  "map_url": "http://127.0.0.1:8000/api/trips/map/?start=...&finish=..."
}
```

`route` is GeoJSON, so it drops straight into Leaflet, Mapbox or geojson.io.

### `GET /api/trips/map/?start=...&finish=...`

The same trip drawn on a Leaflet map: route, numbered fuel stops, totals. Uses the cached plan, so no extra routing call.

### Errors

| Status | When |
| --- | --- |
| 400 | Missing parameter, unknown city, or a point outside the contiguous USA |
| 422 | No drivable route, or a stretch longer than 500 miles with no fuel station |
| 502 | The routing service is down |

## How it works

```
fuel/
  domain/          pure Python, no Django
    entities.py    Coordinate, Station, Route, FuelStop, TripPlan
    geo.py         match stations to the route and give each a mile marker
    optimizer.py   choose the stops
  application/
    plan_trip.py   use case: parse locations -> route -> nearby stations -> stops (cached)
  infrastructure/
    osrm.py        routing client
    repositories.py  ORM queries returning domain entities
    gazetteer.py   readers for the bundled data files
  api/             DRF serializers, views, urls
  management/commands/load_data.py
```

1. **Load (once).** `load_data` reads the Census places and county-subdivision gazetteers, then geocodes each station to its city's coordinates. Duplicate OPIS ids keep the lowest price. Canadian stations are skipped (the API is USA only), as are ~200 US stations in tiny unincorporated places the gazetteer doesn't list; 6,423 stations load.
2. **Route.** One OSRM call returns the full route geometry, thinned to a point every half mile.
3. **Stations on the route.** A bounding-box DB query, then a grid pre-filter, then an exact point-to-segment distance (numpy). Stations within 10 miles of the route are kept, each with its mile marker along the route.
4. **Stops.** Dynamic programming from the destination backwards: at each stop, buy exactly the fuel for the leg to the next stop (a leg is at most 500 miles). It minimises total fuel cost plus a $5 overhead per stop, so the plan doesn't add a stop to save a few cents. On NY to LA that is 7 stops for $864.91, versus 18 stops for $852.50 with no overhead.

The planning itself takes about 100 ms on a cross-country trip; the rest of a cold request is the OSRM call (about 1 to 1.5 s). Cached repeats return in about 10 ms.

### Assumptions

- The tank starts empty. The first stop is at the start (the first station on the route, or any within its first 10 miles) and the fuel to reach it is charged at that station's price, so `total_cost` covers the whole trip and `total_gallons` = distance / 10.
- Stations are placed at their city's centre, as the CSV has no coordinates. The 10-mile corridor absorbs that.
- Detours to a station are not added to the distance.

Settings live at the bottom of `config/settings.py` (`VEHICLE_RANGE_MILES`, `VEHICLE_MPG`, `STATION_CORRIDOR_MILES`, `FUEL_STOP_OVERHEAD_USD`, `OSRM_BASE_URL`).
