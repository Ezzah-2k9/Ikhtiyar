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

During deployment, Render needs fresh values for `LOCATIONIQ_KEY`, `ORS_KEY`, `TOMTOM_KEY`, `GRAPHHOPPER_KEY`, `GEOAPIFY_KEY`, and `OPENWEATHER_KEY`. `SECRET_KEY` is generated automatically; `DATABASE_URL` is linked to the new database's connection string. Enter fresh provider keys in Render's secret fields—**do not send them in chat**.

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
5. If route or weather calls fail while pages load, check that the new service has the fresh provider keys in its Environment settings.

## Security note

Earlier source on `main` contains provider credentials and the tracked SQLite file. The isolated v2 branch uses environment variables and excludes the database file, but `main` remains unchanged as requested. Consider issuing separate fresh provider keys for v2; do not revoke old keys until you are ready to update or retire the existing service, because that service may still depend on them.

New passwords are stored with scrypt. Legacy SHA-256 passwords are accepted once and automatically upgraded after a successful sign-in; no old accounts are present in the new empty database.

## Official Render references

- [Deploy a Flask App on Render](https://render.com/docs/deploy-flask)
- [Create and Connect to Render Postgres](https://render.com/docs/postgresql-creating-connecting)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Setting Your Python Version](https://render.com/docs/python-version)
- [Free instances and current limits](https://render.com/docs/free)
