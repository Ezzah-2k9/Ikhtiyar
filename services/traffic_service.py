"""Server-side proxy for TomTom live raster traffic tiles."""

import re
import xml.etree.ElementTree as ET

import requests

from config import Config


class TrafficService:
    TOMTOM_BASE_URL = "https://api.tomtom.com/traffic/map/4/tile/flow/relative0"

    @staticmethod
    def is_configured():
        return bool(str(Config.TOMTOM_KEY or "").strip())

    @staticmethod
    def _safe_provider_message(response, api_key):
        """Extract a short provider error without returning credentials or markup."""
        message = ""
        try:
            payload = response.json()
        except (AttributeError, ValueError):
            payload = None

        if isinstance(payload, dict):
            detail = payload.get("detailedError") or payload.get("error") or payload
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("description") or ""
            elif isinstance(detail, str):
                message = detail

        if not message:
            raw = getattr(response, "text", "") or ""
            try:
                root = ET.fromstring(raw)
            except (ET.ParseError, TypeError, ValueError):
                root = None
            if root is not None:
                message = root.attrib.get("description") or root.attrib.get("message") or ""
                if not message:
                    for node in root.iter():
                        if node.tag.rsplit("}", 1)[-1].lower() in ("message", "description") and node.text:
                            message = node.text
                            break

        if not message:
            return ""

        message = str(message)
        if api_key:
            message = message.replace(api_key, "[redacted]")
        message = re.sub(
            r"(?i)([?&](?:key|apikey|api_key)=)[^&\s]+",
            r"\1[redacted]",
            message,
        )
        message = re.sub(
            r"(?i)((?:api[-_ ]?)?key\s*[:=]\s*)[^\s,;]+",
            r"\1[redacted]",
            message,
        )
        return " ".join(message.split())[:240]

    @staticmethod
    def _upstream_error(provider, status):
        if status in (401, 403):
            message = f"{provider} denied traffic-tile access (HTTP {status})."
        elif status == 429:
            message = f"{provider} traffic quota or rate limit was reached (HTTP 429)."
        elif status == 400:
            message = f"{provider} rejected the traffic-tile request (HTTP 400)."
        else:
            message = f"{provider} traffic tiles are temporarily unavailable (HTTP {status})."
        client_status = status if status in (401, 403, 429) else 502
        return message, client_status

    @staticmethod
    def get_tile(zoom, x, y):
        if not (0 <= zoom <= 22 and 0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom):
            return None, "Invalid map tile coordinates.", 400, {
                "source": "application",
                "code": "INVALID_TILE_COORDINATES",
            }

        tomtom_key = str(Config.TOMTOM_KEY or "").strip()
        if not tomtom_key:
            return None, "Set TOMTOM_KEY to enable live traffic.", 503, {
                "source": "application",
                "code": "TRAFFIC_PROVIDER_NOT_CONFIGURED",
            }

        provider = "TomTom"
        try:
            response = requests.get(
                f"{TrafficService.TOMTOM_BASE_URL}/{zoom}/{x}/{y}.png",
                params={"key": tomtom_key, "tileSize": 256},
                headers={"Accept": "image/png", "User-Agent": "Ikhtiyar mobility app/2.0"},
                timeout=(3, 6),
            )
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if content_type.startswith("image/png"):
                    return response.content, None, 200, {
                        "source": "provider",
                        "provider": provider,
                        "upstream_status": 200,
                    }
                print(f"{provider} traffic provider returned a non-PNG tile.")
                return None, f"{provider} returned an unexpected tile format.", 502, {
                    "source": "provider",
                    "provider": provider,
                    "upstream_status": 200,
                    "code": "UNEXPECTED_TILE_FORMAT",
                }

            upstream_status = response.status_code
            detail = TrafficService._safe_provider_message(response, tomtom_key)
            # Never log provider response bodies or request URLs: either could carry credentials.
            print(f"{provider} traffic provider returned HTTP {upstream_status}.")
            message, client_status = TrafficService._upstream_error(provider, upstream_status)
            return None, message, client_status, {
                "source": "provider",
                "provider": provider,
                "upstream_status": upstream_status,
                "detail": detail,
                "code": "UPSTREAM_HTTP_ERROR",
            }
        except requests.RequestException as error:
            error_code = "UPSTREAM_TIMEOUT" if isinstance(error, requests.Timeout) else "UPSTREAM_NETWORK_ERROR"
            print(f"{provider} traffic tile failed ({type(error).__name__}).")
            message = (
                f"{provider} traffic tile request timed out."
                if error_code == "UPSTREAM_TIMEOUT"
                else f"{provider} traffic tiles are temporarily unavailable."
            )
            return None, message, 502, {
                "source": "provider",
                "provider": provider,
                "upstream_status": None,
                "code": error_code,
            }

