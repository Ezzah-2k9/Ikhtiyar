
import requests
from config import Config

class GeocodingService:
    @staticmethod
    def get_coordinates(location_name):
        api_key = Config.LOCATIONIQ_KEY
        # If API key is the placeholder or obviously invalid, usage might fail or return error.
        # But LocationIQ free tier might work if the key is real (the one in config is a commonly used example one, likely invalid).
        # We will try the request, if it fails, fallback to common UAE locations.
        
        try:
            url = f"https://us1.locationiq.com/v1/search.php"
            params = {
                'key': api_key,
                'q': f"{location_name}, UAE",
                'format': 'json',
                'limit': 1,
                'countrycodes': 'ae'
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon']), data[0]['display_name']
        except Exception as e:
            print(f"Geocoding API failed: {e}. Using fallback.")
            
        # Fallback mechanism
        loc_lower = location_name.lower()
        if 'habitat school' in loc_lower and 'jurf' in loc_lower:
            return 25.4, 55.49, "Habitat School Al Jurf, Ajman, UAE"
        elif 'dubai mall' in loc_lower:
            return 25.1985, 55.2796, "The Dubai Mall, Dubai, UAE"
        elif 'burj khalifa' in loc_lower:
            return 25.1972, 55.2744, "Burj Khalifa, Dubai, UAE"
        elif 'marina' in loc_lower:
            return 25.0805, 55.1403, "Dubai Marina, Dubai, UAE"
        elif 'airport' in loc_lower or 'dxb' in loc_lower:
            return 25.2532, 55.3657, "Dubai International Airport, UAE"
        elif 'jbr' in loc_lower:
            return 25.0783, 55.1306, "Jumeirah Beach Residence, Dubai, UAE"
        elif 'palm' in loc_lower:
            return 25.1124, 55.1390, "Palm Jumeirah, Dubai, UAE"
        elif 'abu dhabi' in loc_lower:
            return 24.4539, 54.3773, "Abu Dhabi, UAE"
        else:
            # Default to Downtown Dubai if unknown
            return 25.1972, 55.2744, "Downtown Dubai, UAE (Fallback)"
