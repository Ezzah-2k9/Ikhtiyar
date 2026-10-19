"""Server-side proxy for live raster traffic tiles."""

import requests

from config import Config


class TrafficService:
    TOMTOM_BASE_URL = "https://api.tomtom.com/traffic/map/4/tile/flow/relative0"
    HERE_BASE_URL = "https://traffic.maps.hereapi.com/v3/flow/mc"

    @staticmethod
    def is_configured():
        return bool(
            str(Config.TOMTOM_KEY or "").strip()
            or str(getattr(Config, "HERE_API_KEY", "") or "").strip()
        )

    @staticmethod
    def _upstream_error(provider, status):
        if status in (401, 403):
            return f"{provider} rejected the key or denied traffic-tile access (HTTP {status}).", status
        if status == 429:
            return f"{provider} traffic quota or rate limit was reached (HTTP 429).", 429
        if status == 400:
            return f"{provider} rejected the traffic-tile request (HTTP 400).", 502
        return f"{provider} traffic tiles are temporarily unavailable (HTTP {status}).", 502

    @staticmethod
    def get_tile(zoom, x, y):
        if not (0 <= zoom <= 22 and 0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom):
            return None, "Invalid map tile coordinates.", 400

        providers = []
        tomtom_key = str(Config.TOMTOM_KEY or "").strip()
        here_key = str(getattr(Config, "HERE_API_KEY", "") or "").strip()
        if tomtom_key:
            providers.append((
                "TomTom",
                f"{TrafficService.TOMTOM_BASE_URL}/{zoom}/{x}/{y}.png",
                {"key": tomtom_key, "tileSize": 256},
            ))
        if here_key:
            # HERE v3 uses the standard Web Mercator column (x), row (y) order.
            providers.append((
                "HERE",
                f"{TrafficService.HERE_BASE_URL}/{zoom}/{x}/{y}/png",
                {"apiKey": here_key, "size": 256},
            ))
        if not providers:
            return None, "Set TOMTOM_KEY or HERE_API_KEY to enable live traffic.", 503

        last_error = ("Traffic providers are temporarily unavailable.", 502)
        for provider, url, params in providers:
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={"Accept": "image/png", "User-Agent": "Ikhtiyar mobility app/2.0"},
                    timeout=(3, 6),
                )
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if content_type.startswith("image/png"):
                        return response.content, None, 200
                    print(f"{provider} traffic provider returned a non-PNG tile.")
                    last_error = (f"{provider} returned an unexpected tile format.", 502)
                    continue

                upstream_status = response.status_code
                print(f"{provider} traffic provider returned HTTP {upstream_status}.")
                last_error = TrafficService._upstream_error(provider, upstream_status)
            except requests.RequestException as error:
                print(f"{provider} traffic tile failed ({type(error).__name__}).")
                last_error = (f"{provider} traffic tiles are temporarily unavailable.", 502)

        return None, last_error[0], last_error[1]
