
import requests
import math
from config import Config
from services.openrouteservice_service import OpenRouteService
from services.geoapify_service import GeoapifyService
from services.tomtom_service import TomTomService

class RouteService:
    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """
        Get route using OpenRouteService API as primary service for accurate routing
        """
        # Try OpenRouteService first for best routing accuracy
        try:
            ors_result = OpenRouteService.get_all_routes(origin_lat, origin_lon, dest_lat, dest_lon)
            if ors_result and ors_result['driving']['geometry']:
                print("Using OpenRouteService API for highly accurate routing")
                return ors_result
        except Exception as e:
            print(f"OpenRouteService service failed: {e}")
        
        # Try Geoapify as fallback
        try:
            geoapify_result = GeoapifyService.get_route(origin_lat, origin_lon, dest_lat, dest_lon)
            if geoapify_result and geoapify_result['driving']['geometry']:
                print("Using Geoapify API for highly accurate road routing")
                return geoapify_result
        except Exception as e:
            print(f"Geoapify service failed: {e}")
        
        # Try TomTom as final fallback
        try:
            tomtom_result = TomTomService.get_route(origin_lat, origin_lon, dest_lat, dest_lon)
            if tomtom_result and tomtom_result['driving']['geometry']:
                print("Using TomTom API for accurate road routing")
                return tomtom_result
        except Exception as e:
            print(f"TomTom service failed: {e}")
        
        # Final fallback - return basic structure
        straight_dist = RouteService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        return {
            'driving': {'distance_km': round(straight_dist * 1.4, 2), 'duration_min': round((straight_dist * 1.4 / 40) * 60, 0), 'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]]},
            'walking': {'distance_km': round(straight_dist * 1.1, 2), 'duration_min': round((straight_dist * 1.1 / 5) * 60, 0), 'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]]},
            'cycling': {'distance_km': round(straight_dist * 1.2, 2), 'duration_min': round((straight_dist * 1.2 / 15) * 60, 0), 'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]]}
        }

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371 # km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2) * math.sin(dLat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
