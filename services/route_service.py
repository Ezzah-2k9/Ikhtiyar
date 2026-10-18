"""Route-provider cascade with transparent estimate and public OSRM fallback."""

import math
import threading
import time

import requests

from config import Config
from services.openrouteservice_service import OpenRouteService
from services.geoapify_service import GeoapifyService
from services.tomtom_service import TomTomService


class RouteService:
    OSRM_DEMO_URL = "https://router.project-osrm.org/route/v1/driving"
    OSRM_MIN_INTERVAL_SECONDS = 1.05
    _osrm_request_lock = threading.Lock()
    _last_osrm_request_started = 0.0

    @staticmethod
    def _decorate(result, provider_name):
        if not result:
            return None
        for mode in ("driving", "walking", "cycling"):
            route = result.get(mode)
            if route is not None:
                route.setdefault("provider", provider_name)
                route.setdefault("is_estimate", True)
        result["provider"] = provider_name
        result["is_estimate"] = any(
            route.get("is_estimate", True)
            for route in result.values()
            if isinstance(route, dict) and "distance_km" in route
        )
        return result

    @staticmethod
    def _get_osrm_driving_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """Fetch one street-following driving route from OSRM's public demo service.

        OSRM's public demo is for reasonable non-commercial use and asks clients
        not to exceed one request per second. This app makes at most one request
        for a route calculation and enforces a process-wide minimum interval.
        It has no uptime or latency guarantee, so callers must keep an estimate
        fallback available.
        """
        with RouteService._osrm_request_lock:
            elapsed = time.monotonic() - RouteService._last_osrm_request_started
            wait_for = RouteService.OSRM_MIN_INTERVAL_SECONDS - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
            RouteService._last_osrm_request_started = time.monotonic()
            response = requests.get(
                f"{RouteService.OSRM_DEMO_URL}/"
                f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
                headers={"User-Agent": "Ikhtiyar mobility comparison app/2.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()

        routes = payload.get("routes") or []
        if payload.get("code") != "Ok" or not routes:
            return None
        route = routes[0]
        coordinates = (route.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) < 2:
            return None
        # OSRM GeoJSON is [longitude, latitude]; Leaflet uses [latitude, longitude].
        geometry = [[float(lat), float(lon)] for lon, lat in coordinates]
        return {
            "distance_km": round(float(route["distance"]) / 1000, 2),
            "duration_min": round(float(route["duration"]) / 60, 0),
            "geometry": geometry,
            "provider": "OSRM public demo",
            "is_estimate": False,
        }

    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """Try configured providers, then public OSRM for driving, then estimates."""
        straight_dist = RouteService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        if straight_dist < 0.01:
            same_point = {
                mode: {"distance_km": 0, "duration_min": 0, "geometry": [],
                       "provider": "coordinate estimate", "is_estimate": False}
                for mode in ("driving", "walking", "cycling")
            }
            same_point.update({"provider": "coordinate estimate", "is_estimate": False})
            return same_point

        providers = (
            ("OpenRouteService", bool(Config.ORS_KEY),
             lambda: OpenRouteService.get_all_routes(origin_lat, origin_lon, dest_lat, dest_lon)),
            ("Geoapify", bool(Config.GEOAPIFY_KEY),
             lambda: GeoapifyService.get_route(origin_lat, origin_lon, dest_lat, dest_lon)),
            ("TomTom", bool(Config.TOMTOM_KEY),
             lambda: TomTomService.get_route(origin_lat, origin_lon, dest_lat, dest_lon)),
        )
        for provider_name, configured, request_routes in providers:
            if not configured:
                continue
            try:
                result = RouteService._decorate(
                    request_routes(), provider_name
                )
                driving = result.get("driving", {}) if result else {}
                if driving and not driving.get("is_estimate", True):
                    return result
                print(f"{provider_name} did not return a live driving route; trying the next provider.")
            except Exception as error:
                print(f"{provider_name} route provider failed ({type(error).__name__}).")

        osrm_driving = None
        try:
            osrm_driving = RouteService._get_osrm_driving_route(
                origin_lat, origin_lon, dest_lat, dest_lon
            )
        except Exception as error:
            print(f"OSRM public demo route failed ({type(error).__name__}).")

        factors = {"driving": 1.4, "walking": 1.1, "cycling": 1.2}
        speeds = {"driving": 40, "walking": 5, "cycling": 15}
        fallback = {}
        for mode, factor in factors.items():
            distance = straight_dist * factor
            fallback[mode] = {
                "distance_km": round(distance, 2),
                "duration_min": round((distance / speeds[mode]) * 60, 0),
                "geometry": [[origin_lat, origin_lon], [dest_lat, dest_lon]],
                "provider": "built-in estimate",
                "is_estimate": True,
            }

        if osrm_driving:
            fallback["driving"] = osrm_driving
            fallback["provider"] = "OSRM public demo (driving); walking and cycling estimates"
        else:
            fallback["provider"] = "built-in estimate"
        fallback["is_estimate"] = True
        return fallback

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        earth_radius_km = 6371
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        value = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        return 2 * earth_radius_km * math.atan2(math.sqrt(value), math.sqrt(1 - value))
