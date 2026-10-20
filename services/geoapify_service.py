
import requests
import math
from config import Config

class GeoapifyService:
    @staticmethod
    def get_driving_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """Request only the driving route so provider failover stays bounded."""
        api_key = str(Config.GEOAPIFY_KEY or "").strip()
        if not api_key:
            raise ValueError("Geoapify key is not configured")
        response = requests.get(
            "https://api.geoapify.com/v1/routing",
            params={
                "apiKey": api_key,
                "waypoints": f"{origin_lat},{origin_lon}|{dest_lat},{dest_lon}",
                "mode": "drive",
                "units": "metric",
                "format": "geojson",
            },
            timeout=(3, 5),
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features") or []
        if not features:
            raise ValueError("Geoapify returned no route")
        feature = features[0]
        properties = feature.get("properties") or {}
        route_geometry = feature.get("geometry") or {}
        coordinates = route_geometry.get("coordinates") or []
        geometry_type = route_geometry.get("type")
        if geometry_type == "LineString":
            lines = [coordinates]
        elif geometry_type == "MultiLineString":
            lines = coordinates
        else:
            lines = []
        if not lines:
            raise ValueError("Geoapify returned no route geometry")
        geometry = []
        for line in lines:
            for point in line:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                pair = [float(point[1]), float(point[0])]
                if not geometry or pair != geometry[-1]:
                    geometry.append(pair)
        if len(geometry) < 2:
            raise ValueError("Geoapify returned invalid route geometry")
        return {
            "distance_km": float(properties["distance"]) / 1000,
            "duration_min": float(properties["time"]) / 60,
            "geometry": geometry,
        }

    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """
        Get route from Geoapify API with highly accurate road following
        """
        api_key = Config.GEOAPIFY_KEY
        
        # Check if identical (approx)
        if abs(origin_lat - dest_lat) < 0.0001 and abs(origin_lon - dest_lon) < 0.0001:
            return {
                'driving': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'Geoapify', 'is_estimate': False},
                'walking': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'Geoapify', 'is_estimate': False},
                'cycling': {'distance_km': 0, 'duration_min': 0, 'geometry': [], 'provider': 'Geoapify', 'is_estimate': False}
            }
        
        res = {}
        modes = {
            'driving': 'drive',
            'walking': 'walk',
            'cycling': 'bicycle'
        }
        
        for mode_key, travel_mode in modes.items():
            try:
                # Geoapify Routing API
                url = "https://api.geoapify.com/v1/routing"
                
                params = {
                    'apiKey': api_key,
                    'waypoints': f"{origin_lat},{origin_lon}|{dest_lat},{dest_lon}",
                    'mode': travel_mode,
                    'units': 'metric',
                    'returnGeometry': 'true',
                    'returnInstructions': 'false',
                    'returnElevation': 'false'
                }
                
                response = requests.get(url, params=params, timeout=5)
                print(f"Geoapify response status: {response.status_code}")
                
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")
                
                try:
                    data = response.json()
                except ValueError as e:
                    print(f"Geoapify JSON parse failed ({type(e).__name__}).")
                    raise Exception("Invalid Geoapify JSON response")
                
                if 'features' in data and len(data['features']) > 0:
                    feature = data['features'][0]
                    
                    # Extract distance and time
                    properties = feature.get('properties', {})
                    dist_m = properties.get('distance', 0)
                    dist_km = dist_m / 1000.0
                    time_sec = properties.get('time', 0)
                    dur_min = time_sec / 60.0
                    
                    # Extract geometry (polyline)
                    geometry = []
                    geometry_data = feature.get('geometry', {})
                    if geometry_data.get('type') == 'LineString':
                        coordinates = geometry_data.get('coordinates', [])
                        for coord in coordinates:
                            # Geoapify provides [lon, lat]
                            geometry.append([coord[1], coord[0]])  # Convert to [lat, lon]
                    
                    res[mode_key] = {
                        'distance_km': round(dist_km, 2),
                        'duration_min': round(dur_min, 0),
                        'geometry': geometry,
                        'provider': 'Geoapify',
                        'is_estimate': False
                    }
                    print(f"Geoapify success for {mode_key}: {dist_km}km, {dur_min}min, {len(geometry)} points")
                else:
                    raise Exception("No route found in Geoapify response")
                    
            except Exception as e:
                print(f"Geoapify API ({mode_key}) failed ({type(e).__name__}); using estimate.")
                # Fallback: Haversine distance * factor
                straight_dist = GeoapifyService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
                
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
