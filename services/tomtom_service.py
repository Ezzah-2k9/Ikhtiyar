
import requests
import math
from config import Config

class TomTomService:
    @staticmethod
    def get_driving_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """Request one TomTom car route and return its street-level polyline."""
        api_key = str(Config.TOMTOM_KEY or "").strip()
        if not api_key:
            raise ValueError("TomTom key is not configured")
        url = (
            "https://api.tomtom.com/routing/1/calculateRoute/"
            f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
        )
        response = requests.get(
            url,
            params={
                "key": api_key,
                "travelMode": "car",
                "routeType": "fastest",
                "routeRepresentation": "polyline",
            },
            timeout=(3, 5),
        )
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes") or []
        if not routes:
            raise ValueError("TomTom returned no route")
        route = routes[0]
        summary = route.get("summary") or {}
        geometry = []
        for leg in route.get("legs") or []:
            for point in leg.get("points") or []:
                try:
                    geometry.append([
                        float(point["latitude"]), float(point["longitude"])
                    ])
                except (KeyError, TypeError, ValueError):
                    continue
        if len(geometry) < 2:
            raise ValueError("TomTom returned no usable route geometry")
        return {
            "distance_km": float(summary["lengthInMeters"]) / 1000,
            "duration_min": float(summary["travelTimeInSeconds"]) / 60,
            "geometry": geometry,
        }

    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """
        Get route from TomTom API with accurate road following
        """
        api_key = Config.TOMTOM_KEY
        
        # Check if identical (approx)
        if abs(origin_lat - dest_lat) < 0.0001 and abs(origin_lon - dest_lon) < 0.0001:
            return {
                'driving': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'TomTom', 'is_estimate': False},
                'walking': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'TomTom', 'is_estimate': False},
                'cycling': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'TomTom', 'is_estimate': False}
            }
        
        res = {}
        modes = {
            'driving': 'car',
            'walking': 'pedestrian',
            'cycling': 'bicycle'
        }
        
        for mode_key, travel_mode in modes.items():
            try:
                # TomTom Routing API
                # TomTom v1 route locations are latitude,longitude pairs in
                # the path. travelMode is a query parameter, not a URL segment.
                url = (
                    "https://api.tomtom.com/routing/1/calculateRoute/"
                    f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
                )
                
                params = {
                    'key': api_key,
                    'travelMode': travel_mode,
                    'traffic': 'true',
                    'routeRepresentation': 'polyline',
                    'computeBestOrder': 'true',
                    'routeType': 'fastest',
                    'avoid': 'unpavedRoads',
                    'sectionType': 'traffic'
                }
                
                response = requests.get(url, params=params, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                if 'routes' in data and len(data['routes']) > 0:
                    route = data['routes'][0]
                    
                    # Extract distance and time
                    dist_m = route['summary']['lengthInMeters']
                    dist_km = dist_m / 1000.0
                    time_sec = route['summary']['travelTimeInSeconds']
                    dur_min = time_sec / 60.0
                    
                    # Extract geometry (polyline)
                    geometry = []
                    if 'legs' in route:
                        for leg in route['legs']:
                            if 'points' in leg:
                                for point in leg['points']:
                                    # TomTom provides lat,lon directly
                                    geometry.append([point['latitude'], point['longitude']])
                    
                    res[mode_key] = {
                        'distance_km': round(dist_km, 2),
                        'duration_min': round(dur_min, 0),
                        'geometry': geometry,
                        'provider': 'TomTom',
                        'is_estimate': False
                    }
                else:
                    raise Exception("No route found in TomTom response")
                    
            except Exception as e:
                print(f"TomTom API ({mode_key}) failed ({type(e).__name__}); using estimate.")
                # Fallback: Haversine distance * factor
                straight_dist = TomTomService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
                
                factors = {'driving': 1.4, 'walking': 1.1, 'cycling': 1.2}
                speeds = {'driving': 40, 'walking': 5, 'cycling': 15} # km/h
                
                est_dist = straight_dist * factors[mode_key]
                est_dur = (est_dist / speeds[mode_key]) * 60
                
                # Create a simple straight line for geometry
                res[mode_key] = {
                    'distance_km': round(est_dist, 2),
                    'duration_min': round(est_dur, 0),
                    'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]],
                    'provider': 'built-in estimate',
                    'is_estimate': True
                }
        
        return res
    
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points on earth
        """
        R = 6371 # km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2) * math.sin(dLat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
