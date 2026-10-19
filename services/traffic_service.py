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
                headers={"Accept": "image/png, application/json", "User-Agent": "Ikhtiyar mobility app/2.0"},
                timeout=8,
            )
            if response.status_code != 200:
                detail = ""
                try:
                    payload = response.json()
                    error = payload.get("detailedError") or {}
                    detail = error.get("message") or payload.get("message") or ""
                except (ValueError, AttributeError):
                    detail = response.text.strip()
                detail = " ".join(str(detail).split())[:180]
                message = f"TomTom traffic provider returned HTTP {response.status_code}"
                if detail:
                    message += f": {detail}"
                print(message + ".")
                status = response.status_code if response.status_code in (401, 403, 429) else 502
                return None, message + ".", status
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/png"):
                print("TomTom traffic provider returned a non-PNG tile response.")
                return None, "Traffic provider returned an unexpected tile format.", 502
            return response.content, None, 200
        except requests.RequestException as error:
            print(f"TomTom traffic tile failed ({type(error).__name__}).")
            return None, "Traffic data is temporarily unavailable.", 502
