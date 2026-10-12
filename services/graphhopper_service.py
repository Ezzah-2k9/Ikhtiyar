
import requests
import math
from config import Config

class GraphHopperService:
    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
        """
        Get route from GraphHopper API with highly accurate road following
        """
        api_key = Config.GRAPHHOPPER_KEY
        
        # Check if identical (approx)
        if abs(origin_lat - dest_lat) < 0.0001 and abs(origin_lon - dest_lon) < 0.0001:
            return {
                'driving': {'distance_km': 0, 'duration_min': 0, 'geometry': []},
                'walking': {'distance_km': 0, 'duration_min': 0, 'geometry': []},
                'cycling': {'distance_km': 0, 'duration_min': 0, 'geometry': []}
            }
        
        res = {}
        modes = {
            'driving': 'car',
            'walking': 'foot',
            'cycling': 'bicycle'
        }
        
        for mode_key, vehicle in modes.items():
            try:
                # GraphHopper Routing API
                url = "https://graphhopper.com/api/1/route"
                
                params = {
                    'key': api_key,
                    'point': [f"{origin_lat},{origin_lon}", f"{dest_lat},{dest_lon}"],
                    'vehicle': vehicle,
                    'locale': 'en',
                    'calc_points': 'true',
                    'points_encoded': 'false',
                    'instructions': 'false',
                    'elevation': 'false',
                    'debug': 'false',
                    'out_encoder': 'polyline'
                }
                
                print(f"GraphHopper request URL: {url}")
                print(f"GraphHopper params: {params}")
                
                response = requests.get(url, params=params, timeout=10)
                print(f"GraphHopper response status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"GraphHopper error response: {response.text}")
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                try:
                    data = response.json()
                    print(f"GraphHopper JSON response: {data}")
                except ValueError as e:
                    print(f"GraphHopper JSON parse error: {e}")
                    print(f"GraphHopper raw response: {response.text}")
                    raise Exception(f"Invalid JSON response: {e}")
                
                if 'paths' in data and len(data['paths']) > 0:
                    path = data['paths'][0]
                    
                    # Extract distance and time
                    dist_m = path['distance']
                    dist_km = dist_m / 1000.0
                    time_ms = path['time']
                    dur_min = time_ms / 60000.0  # Convert ms to minutes
                    
                    # Extract geometry (polyline)
                    geometry = []
                    if 'points' in path:
                        for point in path['points']:
                            # GraphHopper provides lat,lon directly
                            geometry.append([point[0], point[1]])  # [lat, lon]
                    
                    res[mode_key] = {
                        'distance_km': round(dist_km, 2),
                        'duration_min': round(dur_min, 0),
                        'geometry': geometry
                    }
                    print(f"GraphHopper success for {mode_key}: {dist_km}km, {dur_min}min, {len(geometry)} points")
                else:
                    print(f"GraphHopper no paths found in response: {data}")
                    raise Exception("No route found in GraphHopper response")
                    
            except Exception as e:
                print(f"GraphHopper API ({mode_key}) failed: {e}. Using fallback.")
                # Fallback: Haversine distance * factor
                straight_dist = GraphHopperService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
                
                factors = {'driving': 1.4, 'walking': 1.1, 'cycling': 1.2}
                speeds = {'driving': 40, 'walking': 5, 'cycling': 15} # km/h
                
                est_dist = straight_dist * factors[mode_key]
                est_dur = (est_dist / speeds[mode_key]) * 60
                
                # Create a simple straight line for geometry
                res[mode_key] = {
                    'distance_km': round(est_dist, 2),
                    'duration_min': round(est_dur, 0),
                    'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]]
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
