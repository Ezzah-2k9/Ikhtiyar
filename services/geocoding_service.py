"""User-submitted place geocoding with configurable and no-key providers.

Public Nominatim is a low-volume fallback for explicit general-landmark searches.
A best-effort filter blocks common address patterns, but cannot guarantee every
private location is detected. The UI advises users to submit public landmarks
only unless they configure a trusted LocationIQ key. Requests are rate-limited,
identified, cached, and accompanied by OpenStreetMap attribution.
"""

import json
import re
import threading
import time
import unicodedata
from pathlib import Path

import requests

from config import Config


# Curated public landmarks and city centers. Coordinates point to a useful
# map pin; arbitrary or newly opened places still use LocationIQ/Nominatim.
# The station catalog is loaded from dubai_metro_stations.json below.
_KNOWN_UAE_PLACES = (
    ("Habitat School, Al Jurf, Ajman, UAE", 25.40070, 55.48517, (
        "habitat school al jurf", "habitat private school al jurf",
        "habitat school al jurf ajman", "habitat school ajman",
        "habitat private school ajman",
    )),
    ("Habitat School, Al Tallah, Ajman, UAE", 25.36415, 55.50533, (
        "habitat school al tallah", "habitat school al tallah ajman",
        "habitat private school al tallah", "habitat al tallah",
    )),
    ("International Indian School, Ajman, UAE", 25.40033, 55.49608, (
        "international indian school", "international indian school ajman",
        "international indian school ajman uae", "iis ajman",
    )),
    ("Dubai, UAE", 25.20480, 55.27080, ("dubai", "dubai city")),
    ("Abu Dhabi, UAE", 24.45390, 54.37730, ("abu dhabi", "abu dhabi city")),
    ("Sharjah, UAE", 25.34630, 55.42090, ("sharjah", "sharjah city")),
    ("Ajman, UAE", 25.40520, 55.51360, ("ajman", "ajman city")),
    ("Umm Al Quwain, UAE", 25.56470, 55.55330, (
        "umm al quwain", "umm al qaiwain", "uaq", "umm al quwain city",
    )),
    ("Ras Al Khaimah, UAE", 25.78950, 55.94320, (
        "ras al khaimah", "ras al-khaimah", "rak", "ras al khaimah city",
    )),
    ("Fujairah, UAE", 25.12880, 56.32650, ("fujairah", "fujairah city")),
    ("Al Ain, UAE", 24.20750, 55.74470, ("al ain", "al-ain")),
    ("Khor Fakkan, UAE", 25.33940, 56.35640, ("khor fakkan", "khorfakkan")),
    ("Kalba, UAE", 25.07400, 56.35260, ("kalba",)),
    ("Dibba Al Fujairah, UAE", 25.59250, 56.26100, (
        "dibba", "dibba al fujairah", "dibba fujairah",
    )),
    ("Hatta, UAE", 24.79920, 56.11140, ("hatta", "hatta dubai")),
    ("Madinat Zayed, Abu Dhabi, UAE", 23.65420, 53.70520, (
        "madinat zayed", "madinat zayed abu dhabi",
    )),
    ("Mussafah, Abu Dhabi, UAE", 24.35870, 54.51000, (
        "mussafah", "musaffah", "mussafah abu dhabi",
    )),
    ("Masdar City, Abu Dhabi, UAE", 24.43300, 54.61800, (
        "masdar city", "masdar city abu dhabi",
    )),
    ("Jebel Ali, Dubai, UAE", 24.98570, 55.02730, ("jebel ali", "jebel ali dubai")),
    ("International City, Dubai, UAE", 25.16700, 55.40300, (
        "international city", "international city dubai",
    )),
    ("Dubai Silicon Oasis, Dubai, UAE", 25.12200, 55.38200, (
        "dubai silicon oasis", "silicon oasis", "dso",
    )),
    ("Dubai International Airport (DXB), UAE", 25.25320, 55.36570, (
        "dxb", "dubai international airport", "dubai airport",
        "dubai international airport dxb",
    )),
    ("Al Maktoum International Airport (DWC), Dubai, UAE", 24.89630, 55.16140, (
        "dwc", "al maktoum airport", "al maktoum international airport",
        "dubai world central", "dubai world central airport",
    )),
    ("Zayed International Airport (AUH), Abu Dhabi, UAE", 24.43300, 54.65110, (
        "auh", "zayed international airport", "abu dhabi international airport",
        "abu dhabi airport",
    )),
    ("Sharjah International Airport (SHJ), UAE", 25.32850, 55.51720, (
        "shj", "sharjah international airport", "sharjah airport",
    )),
    ("Ras Al Khaimah International Airport (RKT), UAE", 25.61350, 55.93880, (
        "rkt", "ras al khaimah airport", "rak airport",
    )),
    ("Fujairah International Airport (FJR), UAE", 25.11220, 56.32390, (
        "fjr", "fujairah international airport", "fujairah airport",
    )),
    ("Al Ain International Airport (AAN), UAE", 24.26170, 55.60920, (
        "aan", "al ain airport", "al ain international airport",
    )),
    ("The Dubai Mall, Dubai, UAE", 25.19850, 55.27960, (
        "dubai mall", "the dubai mall", "dubai mall downtown",
    )),
    ("Burj Khalifa, Dubai, UAE", 25.19720, 55.27440, (
        "burj khalifa", "burj khalifa dubai",
    )),
    ("Downtown Dubai, UAE", 25.19450, 55.27800, (
        "downtown dubai", "downtown",
    )),
    ("Dubai Marina, UAE", 25.08050, 55.14030, (
        "dubai marina", "marina dubai", "dubai marina promenade",
    )),
    ("Jumeirah Beach Residence (JBR), Dubai, UAE", 25.07830, 55.13060, (
        "jbr", "jumeirah beach residence", "jumeirah beach residence dubai",
    )),
    ("Palm Jumeirah, Dubai, UAE", 25.11240, 55.13900, (
        "palm jumeirah", "the palm", "palm jumeirah dubai",
    )),
    ("Burj Al Arab, Dubai, UAE", 25.14130, 55.18530, ("burj al arab",)),
    ("Mall of the Emirates, Dubai, UAE", 25.11810, 55.20060, (
        "mall of the emirates", "moe dubai", "mall of emirates",
    )),
    ("Dubai Frame, UAE", 25.23540, 55.30090, ("dubai frame",)),
    ("Museum of the Future, Dubai, UAE", 25.21930, 55.28230, (
        "museum of the future", "museum of future dubai",
    )),
    ("Global Village, Dubai, UAE", 25.06710, 55.30290, ("global village",)),
    ("Dubai Miracle Garden, UAE", 25.06000, 55.24720, (
        "dubai miracle garden", "miracle garden",
    )),
    ("Atlantis, The Palm, Dubai, UAE", 25.13040, 55.11720, (
        "atlantis the palm", "atlantis dubai", "atlantis the palm dubai",
    )),
    ("Ibn Battuta Mall, Dubai, UAE", 25.04480, 55.11850, ("ibn battuta mall",)),
    ("Expo City Dubai, UAE", 24.95920, 55.15240, ("expo city", "expo city dubai")),
    ("Dubai Festival City Mall, UAE", 25.22100, 55.35130, (
        "dubai festival city", "dubai festival city mall",
    )),
    ("City Centre Deira, Dubai, UAE", 25.25200, 55.33390, (
        "city centre deira", "deira city centre", "deira city center",
    )),
    ("Dubai Marina Mall, UAE", 25.07770, 55.13890, ("dubai marina mall",)),
    ("Sheikh Zayed Grand Mosque, Abu Dhabi, UAE", 24.41280, 54.47490, (
        "sheikh zayed grand mosque", "grand mosque abu dhabi",
    )),
    ("Louvre Abu Dhabi, UAE", 24.53390, 54.39880, ("louvre abu dhabi",)),
    ("Yas Island, Abu Dhabi, UAE", 24.49060, 54.60090, ("yas island", "yas island abu dhabi")),
    ("Yas Mall, Abu Dhabi, UAE", 24.48890, 54.60790, ("yas mall",)),
    ("Ferrari World Abu Dhabi, UAE", 24.48390, 54.60820, (
        "ferrari world", "ferrari world abu dhabi",
    )),
    ("Qasr Al Watan, Abu Dhabi, UAE", 24.46160, 54.31750, (
        "qasr al watan", "presidential palace abu dhabi",
    )),
    ("Abu Dhabi Corniche, UAE", 24.47260, 54.32820, (
        "abu dhabi corniche", "corniche abu dhabi",
    )),
    ("Abu Dhabi Mall, UAE", 24.49180, 54.37210, ("abu dhabi mall",)),
    ("Sharjah Al Majaz Waterfront, UAE", 25.32340, 55.37920, (
        "al majaz waterfront", "al majaz", "al majaz sharjah",
    )),
    ("Sahara Centre, Sharjah, UAE", 25.30220, 55.37120, ("sahara centre", "sahara center")),
    ("City Centre Sharjah, UAE", 25.32550, 55.39640, ("city centre sharjah", "city center sharjah")),
    ("Ajman Museum, UAE", 25.41280, 55.44530, ("ajman museum",)),
    ("Ajman Corniche, UAE", 25.41300, 55.43560, ("ajman corniche",)),
    ("City Centre Ajman, UAE", 25.39960, 55.47920, (
        "city centre ajman", "city center ajman", "ajman city centre",
    )),
    ("Al Zahia City Centre, Sharjah, UAE", 25.31540, 55.45930, (
        "al zahia city centre", "city centre al zahia", "zahia city centre",
    )),
    ("Jebel Jais, Ras Al Khaimah, UAE", 25.93970, 56.13460, (
        "jebel jais", "jais mountain",
    )),
    ("Al Marjan Island, Ras Al Khaimah, UAE", 25.66940, 55.74790, (
        "al marjan island", "marjan island", "al marjan island rak",
    )),
    ("Dreamland Aqua Park, Umm Al Quwain, UAE", 25.47170, 55.60370, (
        "dreamland aqua park", "dreamland water park",
    )),
    ("Hatta Dam, UAE", 24.78670, 56.11830, ("hatta dam",)),
    ("Khor Fakkan Beach, UAE", 25.35270, 56.35900, (
        "khor fakkan beach", "khorfakkan beach",
    )),
    ("Fujairah Corniche, UAE", 25.13100, 56.34200, ("fujairah corniche",)),
    ("RAK Mall, Ras Al Khaimah, UAE", 25.78700, 55.97800, (
        "rak mall", "ras al khaimah mall",
    )),
    ("Fujairah City Centre, UAE", 25.11470, 56.32690, (
        "fujairah city centre", "city centre fujairah",
    )),
    ("Mall of UAQ, Umm Al Quwain, UAE", 25.57460, 55.55400, (
        "mall of uaq", "uaq mall",
    )),
)


def _normalize_place_name(value):
    normalized = unicodedata.normalize("NFKD", str(value)).casefold()
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _build_known_uae_place_index():
    index = {}
    for display_name, latitude, longitude, aliases in _KNOWN_UAE_PLACES:
        result = (latitude, longitude, display_name)
        for alias in (display_name, *aliases):
            key = _normalize_place_name(alias)
            if key:
                index[key] = result

    # Reuse the existing OSM-backed station catalog so every listed Dubai
    # Metro stop can also be selected as a route endpoint. Ignore unreadable
    # data so the rest of geocoding remains available.
    station_file = Path(__file__).resolve().parent / "dubai_metro_stations.json"
    try:
        with station_file.open("r", encoding="utf-8") as source:
            stations = json.load(source).get("stations", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        stations = []

    for station in stations:
        try:
            name = str(station["name"]).strip()
            latitude = float(station["lat"])
            longitude = float(station["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not name:
            continue
        result = (latitude, longitude, f"{name} Metro Station, Dubai, UAE")
        aliases = (
            name,
            f"{name} metro",
            f"{name} metro station",
            f"Dubai Metro {name}",
        )
        for alias in aliases:
            key = _normalize_place_name(alias)
            if key:
                index.setdefault(key, result)
    return index


_KNOWN_UAE_PLACE_INDEX = _build_known_uae_place_index()


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
        """Resolve exact curated aliases without unsafe substring matching."""
        normalized = _normalize_place_name(query)
        # Allow callers to include the country after a known UAE place.
        for suffix in (" united arab emirates", " uae"):
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
                break
        return _KNOWN_UAE_PLACE_INDEX.get(normalized)

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

        # Known public destinations resolve locally and consistently before a
        # provider can return a similarly named place elsewhere.
        fallback = GeocodingService._known_uae_place(query)
        if fallback:
            GeocodingService._cache_set(cache_key, fallback)
            return fallback

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

        GeocodingService._cache_set(cache_key, None, GeocodingService.NEGATIVE_CACHE_TTL_SECONDS)
        if GeocodingService._is_address_like(query):
            raise ValueError("For a precise street address, configure a trusted LocationIQ provider key. Public no-key geocoding is not used for address-like locations.")
        raise ValueError(f"Could not find ‘{query}’ in the UAE. Try a nearby landmark or check your spelling.")
