# Apply the Ikhtiyar monthly-goal and map update

This is a source overlay for the existing Ikhtiyar project. It does not contain `.env` files, API keys, databases, or Git metadata. It does not change Render by itself.

1. In GitHub Codespaces, confirm you are on `render/ikhtiyar-v2` and there is no cherry-pick in progress. Upload this ZIP to the repository root.
2. Unzip it over the project root, preserving its folder paths:

   ```bash
   unzip -o ikhtiyar-monthly-map-update.zip -d .
   ```

3. Check the result and run the quick checks:

   ```bash
   git status --short --branch
   python3 -m compileall -q app.py database services ml
   node --check static/js/calculator-features.js
   git diff --check
   ```

4. Stage only the app update (this avoids adding old untracked `.patch` files from earlier troubleshooting):

   ```bash
   git add APPLY_UPDATE.md FEATURES.md RENDER_DEPLOYMENT.md TODO.md app.py database/db_manager.py database/feature_store.py services/dubai_metro_stations.json services/gamification.py services/monthly_goals.py services/traffic_service.py services/transit_availability.py services/geoapify_service.py services/geocoding_service.py services/graphhopper_service.py services/openrouteservice_service.py services/route_service.py services/tomtom_service.py services/weather_service.py static/css/feature-enhancements.css static/js/calculator-features.js templates/dashboard.html templates/index.html templates/settings.html
   git diff --cached --check
   git commit -m "Add cumulative monthly goals and refine route map"
   git push origin render/ikhtiyar-v2
   ```

5. Render is set to auto-deploy on commits to `render/ikhtiyar-v2`. Wait for that deployment to finish before testing the service.

## Live traffic requirement

A valid `TOMTOM_KEY` with access to TomTom Traffic Flow Tiles is still required in the Render service's Environment settings. The key remains server-side; never paste it into the repository or chat. After the redeploy, use **Show traffic**. If tiles still fail, the page will distinguish common 401/403 access failures, 429 quota/rate limits, and provider/server errors. Render service logs record only the provider HTTP status, not the key. A green-to-red legend is only a legend; actual colored roads appear only when TomTom returns traffic tiles.
