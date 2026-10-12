
import requests
from config import Config

class WeatherService:
    @staticmethod
    def get_weather(lat, lon):
        api_key = Config.OPENWEATHER_KEY
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': api_key,
                'units': 'metric'
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return {
                'temp': data['main']['temp'],
                'condition': data['weather'][0]['main'],
                'description': data['weather'][0]['description']
            }
            
        except Exception as e:
            print(f"Weather API failed: {e}. Using fallback.")
            # Fallback based on typical Dubai weather if real fails
            # Maybe random variation or fixed
            return {
                'temp': 35.0,
                'condition': 'Clear',
                'description': 'sunny'
            }
