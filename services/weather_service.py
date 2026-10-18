"""Current-condition travel advisories.

Open-Meteo supplies the default no-key weather feed. Advisories here are
threshold-based travel guidance, not official UAE emergency warnings.
"""

import requests
from config import Config


WEATHER_CODES = {
    0: ("Clear", "clear sky"),
    1: ("Mostly clear", "mainly clear"),
    2: ("Partly cloudy", "partly cloudy"),
    3: ("Cloudy", "overcast"),
    45: ("Fog", "fog"),
    48: ("Fog", "rime fog"),
    51: ("Drizzle", "light drizzle"),
    53: ("Drizzle", "moderate drizzle"),
    55: ("Drizzle", "dense drizzle"),
    56: ("Freezing drizzle", "light freezing drizzle"),
    57: ("Freezing drizzle", "dense freezing drizzle"),
    61: ("Rain", "light rain"),
    63: ("Rain", "moderate rain"),
    65: ("Heavy rain", "heavy rain"),
    66: ("Freezing rain", "light freezing rain"),
    67: ("Freezing rain", "heavy freezing rain"),
    71: ("Snow", "light snow"),
    73: ("Snow", "moderate snow"),
    75: ("Heavy snow", "heavy snow"),
    77: ("Snow grains", "snow grains"),
    80: ("Showers", "light rain showers"),
    81: ("Showers", "moderate rain showers"),
    82: ("Heavy showers", "violent rain showers"),
    85: ("Snow showers", "light snow showers"),
    86: ("Snow showers", "heavy snow showers"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm", "thunderstorm with hail"),
    99: ("Thunderstorm", "severe thunderstorm with hail"),
}


class WeatherService:
    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

    @staticmethod
    def _advisories(weather, max_walking_temp):
        alerts = []
        apparent = weather.get("apparent_temp")
        code = weather.get("weather_code")
        precipitation = weather.get("precipitation_mm") or 0
        wind_gust = weather.get("wind_gust_kph") or 0
        visibility = weather.get("visibility_m")

        if apparent is not None and apparent >= max_walking_temp:
            alerts.append({
                "severity": "warning",
                "title": "Heat advisory",
                "message": (
                    f"Feels-like temperature is {apparent:.0f}°C, at or above your "
                    f"{max_walking_temp:.0f}°C walking comfort limit. Consider transit or a vehicle."
                ),
            })
        if code in (95, 96, 99):
            alerts.append({
                "severity": "warning",
                "title": "Thunderstorm advisory",
                "message": "Thunderstorm conditions are reported near your destination. Avoid exposed outdoor travel.",
            })
        if code in (65, 67, 82) or precipitation >= 5:
            alerts.append({
                "severity": "warning",
                "title": "Heavy rain advisory",
                "message": "Heavy rain may reduce visibility and make walking or cycling less comfortable.",
            })
        elif code in (51, 53, 55, 61, 63, 80, 81) or precipitation >= 1:
            alerts.append({
                "severity": "caution",
                "title": "Wet-weather caution",
                "message": "Rain or showers are reported. Allow extra time and use care on foot or by bicycle.",
            })
        if wind_gust >= 65:
            alerts.append({
                "severity": "warning",
                "title": "Strong-wind advisory",
                "message": f"Wind gusts are around {wind_gust:.0f} km/h; exposed cycling and walking may be difficult.",
            })
        elif wind_gust >= 45:
            alerts.append({
                "severity": "caution",
                "title": "Wind caution",
                "message": f"Wind gusts are around {wind_gust:.0f} km/h. Take care on exposed routes.",
            })
        if code in (45, 48) or (visibility is not None and visibility < 1000):
            alerts.append({
                "severity": "caution",
                "title": "Low-visibility caution",
                "message": "Fog or low visibility is reported. Drivers should slow down and allow extra space.",
            })
        return alerts

    @staticmethod
    def _normalize(temp, apparent, condition, description, code, precipitation,
                   wind_kph, gust_kph, visibility, source, max_walking_temp):
        weather = {
            "temp": float(temp) if temp is not None else None,
            "apparent_temp": float(apparent) if apparent is not None else None,
            "condition": condition or "Unknown",
            "description": description or "Current conditions",
            "weather_code": code,
            "precipitation_mm": float(precipitation or 0),
            "wind_kph": float(wind_kph or 0),
            "wind_gust_kph": float(gust_kph or 0),
            "visibility_m": float(visibility) if visibility is not None else None,
            "source": source,
            "is_live": True,
            "advisories": [],
            "advisory_disclaimer": "Travel advisories are threshold-based guidance, not official government alerts.",
        }
        weather["advisories"] = WeatherService._advisories(weather, max_walking_temp)
        return weather

    @staticmethod
    def _get_open_meteo(lat, lon, max_walking_temp):
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,apparent_temperature,precipitation,weather_code,"
                "wind_speed_10m,wind_gusts_10m,visibility"
            ),
            "timezone": "Asia/Dubai",
            "forecast_days": 1,
        }
        response = requests.get(
            WeatherService.OPEN_METEO_URL,
            params=params,
            timeout=6,
            headers={"User-Agent": "Ikhtiyar mobility app/2.0"},
        )
        response.raise_for_status()
        current = response.json().get("current") or {}
        if "temperature_2m" not in current:
            raise ValueError("Weather response did not include current conditions")
        code = current.get("weather_code")
        condition, description = WEATHER_CODES.get(code, ("Unknown", "current conditions"))
        return WeatherService._normalize(
            current.get("temperature_2m"), current.get("apparent_temperature"),
            condition, description, code, current.get("precipitation"),
            current.get("wind_speed_10m"), current.get("wind_gusts_10m"),
            current.get("visibility"), "Open-Meteo", max_walking_temp,
        )

    @staticmethod
    def _get_open_weather(lat, lon, max_walking_temp):
        if not Config.OPENWEATHER_KEY:
            return None
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": Config.OPENWEATHER_KEY, "units": "metric"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        main = data.get("main", {})
        current = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        rain = data.get("rain", {}).get("1h", 0)
        gust = float(wind.get("gust", 0) or 0) * 3.6
        return WeatherService._normalize(
            main.get("temp"), main.get("feels_like"), current.get("main"),
            current.get("description"), current.get("id"), rain,
            float(wind.get("speed", 0) or 0) * 3.6, gust,
            data.get("visibility"), "OpenWeather", max_walking_temp,
        )

    @staticmethod
    def get_weather(lat, lon, max_walking_temp=40):
        """Return live current conditions when available, otherwise unknown weather.

        Open-Meteo is tried first so weather advisories work without a private key.
        OpenWeather is an optional fallback if the project has a configured key.
        """
        try:
            return WeatherService._get_open_meteo(lat, lon, max_walking_temp)
        except Exception as error:
            print(f"Open-Meteo request failed ({type(error).__name__}).")
        try:
            fallback = WeatherService._get_open_weather(lat, lon, max_walking_temp)
            if fallback:
                return fallback
        except Exception as error:
            print(f"OpenWeather fallback failed ({type(error).__name__}).")
        return {
            "temp": None,
            "apparent_temp": None,
            "condition": "Unavailable",
            "description": "Live weather could not be retrieved",
            "weather_code": None,
            "precipitation_mm": None,
            "wind_kph": None,
            "wind_gust_kph": None,
            "visibility_m": None,
            "source": None,
            "is_live": False,
            "advisories": [],
            "advisory_disclaimer": "No live conditions are available. No weather warning can be confirmed.",
        }
