"""Conservative Dubai Metro availability checks.

Station coordinates are a local snapshot of OpenStreetMap elements tagged
station=subway and network=Dubai Metro. The live rail network remains the
source of truth; station access does not provide schedules or a path itinerary.
"""

import json
import math
from pathlib import Path

_STATION_FILE = Path(__file__).with_name("dubai_metro_stations.json")
try:
    _STATIONS = json.loads(_STATION_FILE.read_text(encoding="utf-8"))["stations"]
except (OSError, ValueError, KeyError):
    _STATIONS = []

MAX_STATION_ACCESS_KM = 1.25
MIN_METRO_TRIP_KM = 2.0


def _haversine_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _nearest_station(lat, lon):
    if not _STATIONS:
        return None, None
    station, distance = min(
        ((_station, _haversine_km(lat, lon, _station["lat"], _station["lon"])) for _station in _STATIONS),
        key=lambda pair: pair[1],
    )
    return station, distance


def check_metro_availability(origin_lat, origin_lon, destination_lat, destination_lon):
    """Return whether both endpoints are near mapped, active Dubai Metro stops."""
    origin_station, origin_distance = _nearest_station(float(origin_lat), float(origin_lon))
    destination_station, destination_distance = _nearest_station(float(destination_lat), float(destination_lon))
    straight_km = _haversine_km(float(origin_lat), float(origin_lon), float(destination_lat), float(destination_lon))

    if straight_km < MIN_METRO_TRIP_KM:
        return {
            "available": False,
            "reason": "This trip is short enough that the app does not suggest Metro.",
            "origin_station": origin_station.get("name") if origin_station else None,
            "destination_station": destination_station.get("name") if destination_station else None,
        }
    if origin_distance is None or destination_distance is None:
        return {"available": False, "reason": "Metro station coverage data is unavailable."}
    if origin_distance > MAX_STATION_ACCESS_KM or destination_distance > MAX_STATION_ACCESS_KM:
        return {
            "available": False,
            "reason": "Both ends of a Metro estimate must be within 1.25 km of a mapped Dubai Metro station.",
            "origin_station": origin_station.get("name"),
            "destination_station": destination_station.get("name"),
            "origin_access_km": round(origin_distance, 2),
            "destination_access_km": round(destination_distance, 2),
        }
    origin_ref, destination_ref = origin_station.get("ref"), destination_station.get("ref")
    origin_name = origin_station.get("name", "").strip().casefold()
    destination_name = destination_station.get("name", "").strip().casefold()
    same_station = (
        (origin_ref and destination_ref and origin_ref == destination_ref)
        or (origin_name and origin_name == destination_name)
    )
    station_pair_km = _haversine_km(
        origin_station["lat"], origin_station["lon"],
        destination_station["lat"], destination_station["lon"],
    )
    if same_station or station_pair_km < 0.75:
        return {
            "available": False,
            "reason": "Both ends resolve to the same station or a very short station pair, so Metro is not suggested.",
            "origin_station": origin_station.get("name"),
            "destination_station": destination_station.get("name"),
            "origin_access_km": round(origin_distance, 2),
            "destination_access_km": round(destination_distance, 2),
        }
    return {
        "available": True,
        "reason": "Both ends are near active Dubai Metro stations; fare and journey time are still estimates.",
        "origin_station": origin_station.get("name"),
        "destination_station": destination_station.get("name"),
        "origin_access_km": round(origin_distance, 2),
        "destination_access_km": round(destination_distance, 2),
        "straight_distance_km": round(straight_km, 2),
    }
