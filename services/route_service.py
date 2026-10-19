"""Road routing with provider failover and an explicitly labeled estimate."""

import math

from config import Config
from services.geoapify_service import GeoapifyService
from services.openrouteservice_service import OpenRouteService
from services.tomtom_service import TomTomService


class RouteService:
    @staticmethod
    def _valid_geometry(geometry):
        if not isinstance(geometry, list) or len(geometry) < 2:
            return False
        for point in geometry:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return False
            try:
                lat, lon = float(point[0]), float(point[1])
            except (TypeError, ValueError):
                return False
            if not (math.isfinite(lat) and math.isfinite(lon)
                    and -90 <= lat <= 90 and -180 <= lon <= 180):
                return False
        return True

    @staticmethod
    def _estimate(distance, origin_lat, origin_lon, dest_lat, dest_lon, mode):
        factors = {"driving": 1.4, "walking": 1.1, "cycling": 1.2}
        speeds = {"driving": 40, "walking": 5, "cycling": 15}
        estimated_distance = distance * factors[mode]
        return {
            "distance_km": round(estimated_distance, 2),
            "duration_min": round(estimated_distance / speeds[mode] * 60, 0),
            "geometry": [[origin_lat, origin_lon], [dest_lat, dest_lon]],
            "provider": "built-in estimate",
            "is_estimate": True,
        }

    @staticmethod
    def _result_with_driving_route(route, provider_name, straight_dist,
                                   origin_lat, origin_lon, dest_lat, dest_lon):
        if not isinstance(route, dict) or not RouteService._valid_geometry(route.get("geometry")):
            raise ValueError("Provider returned no usable road geometry")
        try:
            distance_km = float(route["distance_km"])
            duration_min = float(route["duration_min"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Provider returned incomplete route metrics")
        if not (math.isfinite(distance_km) and distance_km > 0
                and math.isfinite(duration_min) and duration_min >= 0):
            raise ValueError("Provider returned invalid route metrics")

        driving = {
            "distance_km": round(distance_km, 2),
            "duration_min": round(duration_min, 0),
            "geometry": route["geometry"],
            "provider": provider_name,
            "is_estimate": False,
        }
        return {
            "driving": driving,
            "walking": RouteService._estimate(
                straight_dist, origin_lat, origin_lon, dest_lat, dest_lon, "walking"
            ),
            "cycling": RouteService._estimate(
                straight_dist, origin_lat, origin_lon, dest_lat, dest_lon, "cycling"
            ),
            "provider": provider_name,
            "is_estimate": False,
        }

    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """Try each configured road router until one returns real route geometry."""
        straight_dist = RouteService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        if straight_dist < 0.01:
            same_point = {
                mode: {
                    "distance_km": 0,
                    "duration_min": 0,
                    "geometry": [],
                    "provider": "coordinate estimate",
                    "is_estimate": False,
                }
                for mode in ("driving", "walking", "cycling")
            }
            same_point.update({"provider": "coordinate estimate", "is_estimate": False})
            return same_point

        providers = (
            ("OpenRouteService", Config.ORS_KEY,
             lambda: OpenRouteService.get_route(
                 origin_lat, origin_lon, dest_lat, dest_lon, "driving-car"
             )),
            ("Geoapify", Config.GEOAPIFY_KEY,
             lambda: GeoapifyService.get_driving_route(
                 origin_lat, origin_lon, dest_lat, dest_lon
             )),
            ("TomTom", Config.TOMTOM_KEY,
             lambda: TomTomService.get_driving_route(
                 origin_lat, origin_lon, dest_lat, dest_lon
             )),
        )

        for provider_name, api_key, request_route in providers:
            if not str(api_key or "").strip():
                continue
            try:
                result = RouteService._result_with_driving_route(
                    request_route(), provider_name, straight_dist,
                    origin_lat, origin_lon, dest_lat, dest_lon,
                )
                print(f"{provider_name} returned a road route with "
                      f"{len(result['driving']['geometry'])} geometry points.")
                return result
            except Exception as error:
                # Keep provider error bodies and credentials out of user responses/logs.
                print(f"{provider_name} route failed ({type(error).__name__}); trying next provider.")

        fallback = {
            mode: RouteService._estimate(
                straight_dist, origin_lat, origin_lon, dest_lat, dest_lon, mode
            )
            for mode in ("driving", "walking", "cycling")
        }
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
