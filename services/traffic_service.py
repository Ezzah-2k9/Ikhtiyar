"""Server-side proxy for TomTom traffic-flow raster tiles."""

import requests
from config import Config


class TrafficService:
    BASE_URL = "https://api.tomtom.com/traffic/map/4/tile/flow/relative0"

    @staticmethod
    def get_tile(zoom, x, y):
        if not Config.TOMTOM_KEY:
            return None, "Traffic overlay is not configured.", 503
        if not (0 <= zoom <= 22 and 0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom):
            return None, "Invalid map tile coordinates.", 400
        try:
            response = requests.get(
                f"{TrafficService.BASE_URL}/{zoom}/{x}/{y}.png",
                params={"key": Config.TOMTOM_KEY, "tileSize": 256},
                headers={"Accept": "image/png", "User-Agent": "Ikhtiyar mobility app/2.0"},
                timeout=8,
            )
            if response.status_code != 200:
                return None, f"Traffic provider returned HTTP {response.status_code}.", 502
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/png"):
                return None, "Traffic provider returned an unexpected tile format.", 502
            return response.content, None, 200
        except requests.RequestException as error:
            print(f"TomTom traffic tile failed ({type(error).__name__}).")
            return None, "Traffic data is temporarily unavailable.", 502
