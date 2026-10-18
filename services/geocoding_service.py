"""User-submitted place geocoding with configurable and no-key providers.

Public Nominatim is a low-volume fallback for explicit general-landmark searches.
A best-effort filter blocks common address patterns, but cannot guarantee every
private location is detected. The UI advises users to submit public landmarks
only unless they configure a trusted LocationIQ key. Requests are rate-limited,
identified, cached, and accompanied by OpenStreetMap attribution.
"""

import re
import threading
import time

import requests
from config import Config


class GeocodingService:
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    NOMINATIM_MIN_INTERVAL_SECONDS = 1.05
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
    NEGATIVE_CACHE_TTL_SECONDS = 5 * 60
    _cache = {}
    _cache_lock = threading.Lock()
    _request_lock = threading.Lock()
    _last_nominatim_start = 0.0

    @staticmethod
    def _cache_get(query):
        now = time.monotonic()
        with GeocodingService._cache_lock:
            entry = GeocodingService._cache.get(query)
            if not entry:
                return None, False
            expires_at, value = entry
            if expires_at <= now:
                GeocodingService._cache.pop(query, None)
                return None, False
            return value, True

    @staticmethod
    def _cache_set(query, value, ttl=None):
        ttl = ttl or GeocodingService.CACHE_TTL_SECONDS
        with GeocodingService._cache_lock:
            GeocodingService._cache[query] = (time.monotonic() + ttl, value)

    @staticmethod
    def _is_address_like(query):
        if re.search(r"\d", query):
            return True
        private_address_terms = re.compile(
            r"\b(home|house|villa|apartment|flat|unit|building|room|floor|office|workplace|residence|plot number|street number)\b|"
            r"(فيلا|شقة|منزل|بيت|مبنى|طابق|رقم|شارع)",
            re.IGNORECASE,
        )
        return bool(private_address_terms.search(query))

    @staticmethod
    def _locationiq(query):
        if not Config.LOCATIONIQ_KEY:
            return None
        response = requests.get(
            "https://us1.locationiq.com/v1/search.php",
            params={
                "key": Config.LOCATIONIQ_KEY,
                "q": f"{query}, UAE",
                "format": "json",
                "limit": 1,
                "countrycodes": "ae",
            },
            timeout=6,
            headers={"User-Agent": "Ikhtiyar mobility app/2.0"},
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", query)

    @staticmethod
    def _nominatim(query):
        # The public endpoint is used only for user-triggered, general place searches.
        with GeocodingService._request_lock:
            elapsed = time.monotonic() - GeocodingService._last_nominatim_start
            wait_for = GeocodingService.NOMINATIM_MIN_INTERVAL_SECONDS - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
            GeocodingService._last_nominatim_start = time.monotonic()
            response = requests.get(
                GeocodingService.NOMINATIM_URL,
                params={
                    "q": f"{query}, United Arab Emirates",
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "ae",
                    "accept-language": "en",
                },
                headers={
                    "User-Agent": "Ikhtiyar/2.0 (mobility comparison app; https://ikhtiyar-v2.onrender.com)",
                    "Referer": "https://ikhtiyar-v2.onrender.com/",
                },
                timeout=7,
            )
            response.raise_for_status()
            data = response.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", query)

    @staticmethod
    def _known_uae_place(query):
        loc_lower = query.lower()
        if "habitat school" in loc_lower and "jurf" in loc_lower:
            return 25.4, 55.49, "Habitat School Al Jurf, Ajman, UAE"
        if "dubai mall" in loc_lower:
            return 25.1985, 55.2796, "The Dubai Mall, Dubai, UAE"
        if "burj khalifa" in loc_lower:
            return 25.1972, 55.2744, "Burj Khalifa, Dubai, UAE"
        if "marina" in loc_lower:
            return 25.0805, 55.1403, "Dubai Marina, Dubai, UAE"
        if "airport" in loc_lower or "dxb" in loc_lower:
            return 25.2532, 55.3657, "Dubai International Airport, UAE"
        if "jbr" in loc_lower:
            return 25.0783, 55.1306, "Jumeirah Beach Residence, Dubai, UAE"
        if "palm" in loc_lower:
            return 25.1124, 55.1390, "Palm Jumeirah, Dubai, UAE"
        if "abu dhabi" in loc_lower:
            return 24.4539, 54.3773, "Abu Dhabi, UAE"
        return None

    @staticmethod
    def get_coordinates(location_name):
        """Resolve a location on explicit route-submit/save, caching successful results."""
        query = " ".join(str(location_name).split())
        if not query:
            raise ValueError("Enter a place name.")
        cache_key = query.casefold()
        cached, found = GeocodingService._cache_get(cache_key)
        if found:
            if cached is None:
                raise ValueError(f"Could not find ‘{query}’ in the UAE. Try a nearby landmark or configure a location provider key.")
            return cached

        try:
            result = GeocodingService._locationiq(query)
            if result:
                GeocodingService._cache_set(cache_key, result)
                return result
        except Exception as error:
            print(f"LocationIQ geocoding unavailable ({type(error).__name__}).")

        if not GeocodingService._is_address_like(query):
            try:
                result = GeocodingService._nominatim(query)
                if result:
                    GeocodingService._cache_set(cache_key, result)
                    return result
            except Exception as error:
                print(f"OpenStreetMap geocoding unavailable ({type(error).__name__}).")

        fallback = GeocodingService._known_uae_place(query)
        if fallback:
            GeocodingService._cache_set(cache_key, fallback)
            return fallback

        GeocodingService._cache_set(cache_key, None, GeocodingService.NEGATIVE_CACHE_TTL_SECONDS)
        if GeocodingService._is_address_like(query):
            raise ValueError("For a precise street address, configure a trusted LocationIQ provider key. Public no-key geocoding is not used for address-like locations.")
        raise ValueError(f"Could not find ‘{query}’ in the UAE. Try a nearby landmark or check your spelling.")
