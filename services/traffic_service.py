"""Server-side proxy for TomTom traffic-flow raster tiles."""

import requests
from config import Config


class TrafficService:
    BASE_URL = "https://api.tomtom.com/traffic/map/4/tile/flow/relative0"

    @staticmethod
    def is_configured():
        return bool(str(Config.TOMTOM_KEY or "").strip())

    @staticmethod
    def get_tile(zoom, x, y):
        api_key = str(Config.TOMTOM_KEY or "").strip()
        if not api_key:
            return None, "Traffic overlay is not configured.", 503
        if not (0 <= zoom <= 22 and 0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom):
            return None, "Invalid map tile coordinates.", 400
        try:
            response = requests.get(
                f"{TrafficService.BASE_URL}/{zoom}/{x}/{y}.png",
                params={"key": api_key, "tileSize": 256},
                headers={"Accept": "image/png", "User-Agent": "Ikhtiyar mobility app/2.0"},
                timeout=8,
            )
            if response.status_code != 200:
                upstream_status = response.status_code
                print(f"TomTom traffic provider returned HTTP {upstream_status}.")
                if upstream_status in (401, 403):
                    return None, f"TomTom rejected the key or Traffic Flow access (HTTP {upstream_status}).", upstream_status
                if upstream_status == 429:
                    return None, "TomTom traffic quota or rate limit reached (HTTP 429).", 429
                if upstream_status == 400:
                    return None, "TomTom rejected the traffic tile request (HTTP 400).", 502
                return None, "TomTom traffic is temporarily unavailable.", 502
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/png"):
                print("TomTom traffic provider returned a non-PNG tile response.")
                return None, "Traffic provider returned an unexpected tile format.", 502
            return response.content, None, 200
        except requests.RequestException as error:
            print(f"TomTom traffic tile failed ({type(error).__name__}).")
            return None, "Traffic data is temporarily unavailable.", 502
