# Deploy a separate Ikhtiyar service on Render

This guide prepares a **new** Render service named `ikhtiyar-v2` and a separate Postgres database named `ikhtiyar-v2-db`. It deliberately keeps the existing `Ikhtiyar` service and `Equinox` untouched. The code will be published on the private GitHub branch `render/ikhtiyar-v2`, not on `main`; the current Render service is linked to `main` and remains unchanged.

## What I found in your connected account

- The selected Render workspace already has an `Ikhtiyar` web service at [ikhtiyar.onrender.com](https://ikhtiyar.onrender.com), linked to the private repository `Ezzah-2k9/Ikhtiyar`, branch `main`, in Singapore.
- There is no Postgres database in this workspace yet.
- The current local `ikhtiyar.db` contains zero users and zero trips, so this copy has no records to migrate.
- The new code uses the GitHub repo's existing logo files, and the new Render resources use unique names so a Blueprint cannot match the existing `Ikhtiyar` service.

## Before applying the Blueprint

You need a decision about database retention and cost:

- **Free demo database:** no database compute charge, but Render Free Postgres expires 30 days after creation; it becomes inaccessible, and after a further 14-day grace period Render deletes it and its data. Free Postgres has no backups. Use it only for a short demo with data you are willing to lose.
- **Persistent database:** use a paid Postgres plan. The current Render Blueprint spec defaults an unpinned new database to `0.1c-256mb`, which may create a recurring charge. Review the exact price shown in your Render workspace before applying anything. Paid Postgres includes point-in-time recovery and on-demand logical exports.

The web service is configured on Render's Free plan (it sleeps after idle time). The database's plan is intentionally **not** pinned until you choose. Do not apply the Blueprint without reviewing the database plan and displayed cost.

## 1. Push the separate deployment branch

The updated files are not in the GitHub repo yet. The deployment branch should be created from the current `main` branch and receive the prepared code while preserving the repository's existing logo assets. This branch is isolated: it will not push to or change `main`.

The branch must include the root-level `render.yaml`, `.python-version`, `.gitignore`, `.env.example`, and the updated Flask files. Never put actual API keys in these files.

## 2. Check the local environment file

For local development, copy `.env.example` to `.env` and enter your own **rotated** provider credentials:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Leave `DATABASE_URL` blank locally to use SQLite. `.gitignore` excludes `.env`, SQLite databases, Python environments, and caches. Do not remove those rules or upload `ikhtiyar.db`.

## 3. Create the separate Render resources

1. Open the [Render Dashboard](https://dashboard.render.com/).
2. Choose **New → Blueprint** (sometimes shown as **Blueprint Instance**).
3. Select the private repository `Ezzah-2k9/Ikhtiyar` and branch `render/ikhtiyar-v2`.
4. Confirm the resources shown are only `ikhtiyar-v2` and `ikhtiyar-v2-db`. Their region is set to Singapore to match the existing Ikhtiyar deployment; Render does not let you change a resource's region after creation.
5. **Choose the Postgres plan and review its current price before applying.** For a short-lived demo, add `plan: free` under `ikhtiyar-v2-db` in `render.yaml`, then commit/push that branch update. For ongoing user accounts and trip records, keep/select a paid plan after reviewing the price.
6. Render will prompt for `LOCATIONIQ_KEY`, `ORS_KEY`, `TOMTOM_KEY`, `GRAPHHOPPER_KEY`, `GEOAPIFY_KEY`, and `OPENWEATHER_KEY`. Enter fresh rotated values in Render's secret fields. `SECRET_KEY` is generated automatically, and `DATABASE_URL` is wired to the new database's connection string.
7. Inspect the proposed resource list, names, region, and costs. Apply only when they match the plan you chose.

The web service is configured to install `requirements.txt` and run:

```text
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:app
```

The app is pinned to Python `3.12.13`, compatible with the pinned package versions. Its database manager creates the needed tables on first startup; you do not need to manually create tables or upload the SQLite file.

## 4. Verify the new deployment

1. Wait for the new Blueprint deploy to finish; check the new service's **Events/Logs** if it fails.
2. Open the new `ikhtiyar-v2` Render URL. The existing `ikhtiyar.onrender.com` service should remain unchanged.
3. Create a test account, sign in, save a preference, calculate/record a route, and verify History/Dashboard.
4. Test PDF export if available.
5. If routes or weather fail while the rest of the site loads, check the fresh provider keys in the new service's Environment settings.

## Security notes

Earlier source versions had third-party provider credentials embedded in `config.py` and `render.yaml`. Those values were removed from the prepared code. **Rotate/regenerate those keys before deployment**, especially if an earlier copy was uploaded or shared. Store new values only in Render's secret prompts or in your ignored local `.env` file.

New passwords are stored with scrypt. A legacy SHA-256 password is accepted once and upgraded automatically when that user signs in successfully; the included database has no user rows.

## Free-plan behavior

Render Free web services spin down after 15 minutes without incoming traffic, and waking them can take about a minute. Their local filesystem is ephemeral, so the production database must be Postgres rather than the SQLite file. Free Postgres is limited to 1 GB, expires after 30 days, and is deleted after the 14-day grace period. Check the [current limits and pricing](https://render.com/docs/free) before applying a plan.

## Official Render references

- [Deploy a Flask App on Render](https://render.com/docs/deploy-flask)
- [Create and Connect to Render Postgres](https://render.com/docs/postgresql-creating-connecting)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Setting Your Python Version](https://render.com/docs/python-version)
- [Free instances and current limits](https://render.com/docs/free)
