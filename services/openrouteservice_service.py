
import requests
import json
from config import Config

class OpenRouteService:
    BASE_URL = "https://api.openrouteservice.org"
    
    @staticmethod
    def get_route(origin_lat, origin_lon, dest_lat, dest_lon, transport_mode='driving-car'):
        """
        Get route using OpenRouteService API
        
        Args:
            origin_lat, origin_lon: Starting coordinates
            dest_lat, dest_lon: Destination coordinates  
            transport_mode: Mode of transport (driving-car, walking, cycling-foot)
            
        Returns:
            dict: Route information with distance, duration, and geometry
        """
        try:
            url = f"{OpenRouteService.BASE_URL}/v2/directions/{transport_mode}"
            
            headers = {
                'Authorization': Config.ORS_KEY,
                'Content-Type': 'application/json'
            }
            
            body = {
                'coordinates': [[origin_lon, origin_lat], [dest_lon, dest_lat]],
                'instructions': False,
                'geometry': True,
                'format': 'geojson'
            }
            
            response = requests.post(url, headers=headers, json=body, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            if 'routes' not in data or len(data['routes']) == 0:
                raise Exception("No route found in OpenRouteService response")
            
            route = data['routes'][0]
            
            # Convert geometry from GeoJSON format to simple coordinate pairs
            geometry = []
            if 'geometry' in route and 'coordinates' in route['geometry']:
                # OpenRouteService returns [lon, lat], we need [lat, lon]
                geometry = [[coord[1], coord[0]] for coord in route['geometry']['coordinates']]
            
            return {
                'distance_km': round(route['summary']['distance'] / 1000, 2),
                'duration_min': round(route['summary']['duration'] / 60, 0),
                'geometry': geometry
            }
            
        except requests.exceptions.RequestException as e:
            print(f"OpenRouteService API request failed ({type(e).__name__}).")
            raise Exception("OpenRouteService API request failed")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"OpenRouteService response parsing failed ({type(e).__name__}).")
            raise Exception("OpenRouteService response parsing failed")
        except Exception as e:
            print(f"OpenRouteService error ({type(e).__name__}).")
            raise
    
    @staticmethod
    def get_all_routes(origin_lat, origin_lon, dest_lat, dest_lon):
        """
        Get routes for all transport modes using OpenRouteService
        
        Returns:
            dict: Routes for driving, walking, and cycling
        """
        transport_modes = {
            'driving': 'driving-car',
            'walking': 'foot-walking', 
            'cycling': 'cycling-regular'
        }
        
        results = {}
        
        for mode, ors_mode in transport_modes.items():
            try:
                route_data = OpenRouteService.get_route(
                    origin_lat, origin_lon, dest_lat, dest_lon, ors_mode
                )
                route_data['provider'] = 'OpenRouteService'
                route_data['is_estimate'] = False
                results[mode] = route_data
                print(f"OpenRouteService {mode} route: {route_data['distance_km']}km, {route_data['duration_min']}min")
                
            except Exception as e:
                print(f"Failed to get {mode} route from OpenRouteService ({type(e).__name__}).")
                # Fallback to basic calculation
                straight_dist = OpenRouteService.haversine(origin_lat, origin_lon, dest_lat, dest_lon)
                
                distance_multipliers = {
                    'driving': 1.4,
                    'walking': 1.1, 
                    'cycling': 1.2
                }
                
                speed_multipliers = {
                    'driving': 40,  # km/h
                    'walking': 5,   # km/h
                    'cycling': 15   # km/h
                }
                
                multiplier = distance_multipliers.get(mode, 1.0)
                speed = speed_multipliers.get(mode, 40)
                
                results[mode] = {
                    'distance_km': round(straight_dist * multiplier, 2),
                    'duration_min': round((straight_dist * multiplier / speed) * 60, 0),
                    'geometry': [[origin_lat, origin_lon], [dest_lat, dest_lon]],
                    'provider': 'built-in estimate',
                    'is_estimate': True
                }
        
        return results
    
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """Calculate the great circle distance between two points on earth"""
        import math
        R = 6371  # km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = (math.sin(dLat/2) * math.sin(dLat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dLon/2) * math.sin(dLon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
