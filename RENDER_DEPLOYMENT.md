# Deploy a separate Ikhtiyar service on Render

This deployment uses a **new** Render service named `ikhtiyar-v2` and a separate Free Postgres database named `ikhtiyar-v2-db`. The service and database live on the private GitHub branch `render/ikhtiyar-v2`, not `main`. This keeps the existing Ikhtiyar service and Equinox untouched.

## What is being deployed

- New service: `ikhtiyar-v2` (Free web plan).
- New database: `ikhtiyar-v2-db` (Free Postgres, fresh/empty).
- Region: Singapore, matching the existing Ikhtiyar service.
- Repository: private `Ezzah-2k9/Ikhtiyar`, branch `render/ikhtiyar-v2`.
- Database data from `main` is **not** copied. The SQLite file on `main` remains untouched.

The connected workspace already has an Ikhtiyar web service at [ikhtiyar.onrender.com](https://ikhtiyar.onrender.com), but there was no Postgres database. I have not changed that service, `main`, or Equinox. The old SQLite file contains 5 users, 5 preference rows, and 4 trips; the new Free database intentionally starts empty.

## Free database retention

Free Postgres is temporary: Render's current policy gives it 30 days from creation. It then becomes inaccessible; after a further 14-day grace period, Render deletes the database and its data. It has no backups. This can be fine for a short test, but **do not use it for data you need to keep**. If the app becomes a real service, upgrade the database before the 30-day expiry and confirm the price shown in Render.

The Free web service also spins down after 15 minutes without inbound traffic and can take about a minute to wake. Render's local filesystem is ephemeral; production data is stored in the separate Postgres database, not SQLite.

## Deployment setup

The private branch contains the updated Flask app, its logo assets, and a root-level `render.yaml` with unique names for both resources. It was created separately from `main` and does not contain the tracked SQLite database or a local `.env` file. The manifest uses the Free plan for both new resources, Singapore for both regions, and this production start command:

```text
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:app
```

It uses Python `3.12.13`. The database manager creates the required tables at app startup; no manual SQL is required.

The Blueprint declares optional environment slots for `LOCATIONIQ_KEY`, `ORS_KEY`, `TOMTOM_KEY`, `GRAPHHOPPER_KEY`, `GEOAPIFY_KEY`, and `OPENWEATHER_KEY`. Provider keys are not required for the app to start; add only the ones for services you intend to activate (see the feature summary below). `SECRET_KEY` is generated automatically; `DATABASE_URL` is linked to the new database's connection string. Enter provider keys in Render's secret fields—**do not send them in chat**.

## Mobility features and provider keys

The app remains usable without provider keys, but it must identify estimates honestly. Weather advisories use Open-Meteo's public forecast endpoint without a key; `OPENWEATHER_KEY` is only an optional fallback. If the weather provider is unavailable, the app says so instead of inventing a warning. Traffic coloring is optional and requires a valid `TOMTOM_KEY` with traffic-tile access; the key is used through an authenticated Flask proxy and is never exposed in the browser. If tiles fail, the calculator displays a safe provider status. Render logs record only TomTom's HTTP status (never the key): 401/403 usually indicates a rejected key or missing product access, 429 indicates quota/rate limiting, and 5xx indicates a provider/service failure. The traffic legend describes real TomTom flow colors, not a calculated ETA.

Configured OpenRouteService, Geoapify, or TomTom road routes are preferred. When those providers are not configured or fail, the app may request a driving route from the public OSRM demo server to draw a street route without a key. This community demo is not a production SLA: use it only for reasonable non-commercial traffic, do not exceed one request per second, and expect temporary unavailability. If OSRM is unavailable too, distance/time are labelled estimates and the map shows a dashed approximate direction rather than a false road route. Walking, cycling, and public-transit times can remain estimates. LocationIQ is optional for precise/private destinations. Without it, public OpenStreetMap Nominatim is used only after an explicit general-place search, with caching and rate limiting. A best-effort filter blocks common address patterns but is not a privacy guarantee; do not enter private locations without a trusted provider configured. The map attribution identifies OpenStreetMap contributors.

Metro is shown only when both endpoints are within 1.25 km of locally mapped Dubai Metro stations, the trip is long enough to be meaningful, and the endpoints do not resolve to the same or a very short station pair. This is a coverage filter, not a live itinerary or timetable; Metro and bus fares/times remain estimates. Saved favourites persist their label, place text, and resolved coordinates; the server verifies that reused coordinates belong to that account. Users can set a cumulative CO₂-savings target for each month in Preferences. Saved trip savings add up against that month’s target, and the dashboard reports the previous month’s result; the calculator favours lower emissions when current progress is behind pace but keeps every available mode selectable. Targets, favourites, XP, streaks, weekly challenge rewards, and one-use route quote claims are stored in the same SQLite/PostgreSQL-compatible database. Route selections use short-lived server-signed quotes to ignore edited client estimates and prevent replaying multiple options from one calculation. The database manager creates the additive tables on startup.

Optional key summary: `TOMTOM_KEY` enables the traffic overlay and can also supply road routing; `ORS_KEY` and `GEOAPIFY_KEY` enable road routing; `LOCATIONIQ_KEY` enables trusted address geocoding; `OPENWEATHER_KEY` is only a weather fallback. `GRAPHHOPPER_KEY` remains in the existing environment template but is not currently selected by the route-provider cascade.

## Local development

Copy `.env.example` to `.env` and enter your own credentials locally:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Leave `DATABASE_URL` blank locally to use SQLite. `.gitignore` excludes `.env`, SQLite databases, Python environments, and caches. Do not remove those rules or upload `ikhtiyar.db`.

## Verify after deployment

1. Confirm Render shows only the new resources `ikhtiyar-v2` and `ikhtiyar-v2-db` for this branch; don't select or change the existing Ikhtiyar service.
2. Wait for the v2 build and deploy to finish, then open the new service URL.
3. Create a new test account, sign in, save a preference, calculate/record a route, and verify History and Dashboard.
4. Test PDF export if available.
5. Confirm weather advisories load; without `TOMTOM_KEY`, the traffic button should report that live traffic is not configured. Add valid routing/geocoding keys if you need provider-backed directions or precise address lookup.
6. Set a monthly target in Preferences; confirm saved trips accumulate on the calculator/dashboard, and an earlier month's reached/missed result appears after month rollover. Verify a route outside Dubai Metro coverage does not show a Metro card; save a place with a custom label and reuse it as either endpoint; record trips and confirm streak/XP/challenges on the dashboard.

## Security note

Earlier source on `main` contains provider credentials and the tracked SQLite file. The isolated v2 branch uses environment variables and excludes the database file, but `main` remains unchanged as requested. Consider issuing separate fresh provider keys for v2; do not revoke old keys until you are ready to update or retire the existing service, because that service may still depend on them.

New passwords are stored with scrypt. Legacy SHA-256 passwords are accepted once and automatically upgraded after a successful sign-in; no old accounts are present in the new empty database.

## Official Render references

- [Deploy a Flask App on Render](https://render.com/docs/deploy-flask)
- [Create and Connect to Render Postgres](https://render.com/docs/postgresql-creating-connecting)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Setting Your Python Version](https://render.com/docs/python-version)
- [Free instances and current limits](https://render.com/docs/free)
- [OpenStreetMap Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
- [Open-Meteo API documentation](https://open-meteo.com/en/docs)
- [TomTom Traffic Flow Tiles documentation](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/raster-flow-tiles/)
