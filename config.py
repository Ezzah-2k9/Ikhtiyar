import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-12345'
    
    # Database configuration - Support both SQLite (dev) and PostgreSQL (prod)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    # Render has historically exposed PostgreSQL URLs with either scheme.
    # psycopg2 and DBManager require the canonical postgresql:// prefix.
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = 'postgresql://' + DATABASE_URL[len('postgres://'):]
    if DATABASE_URL:
        # Production PostgreSQL
        DB_PATH = DATABASE_URL
    else:
        # Development SQLite
        DB_PATH = os.path.join(os.path.dirname(__file__), 'ikhtiyar.db')
    
    # API Keys - Check environment variables first
    LOCATIONIQ_KEY = os.environ.get('LOCATIONIQ_KEY', '')
    ORS_KEY = os.environ.get('ORS_KEY', '')
    # TOMTOM_KEY is the documented Render variable. Accept the common alias too
    # so existing deployments named TOMTOM_API_KEY do not silently disable it.
    TOMTOM_KEY = os.environ.get('TOMTOM_KEY') or os.environ.get('TOMTOM_API_KEY', '')
    HERE_API_KEY = os.environ.get('HERE_API_KEY', '')
    GRAPHHOPPER_KEY = os.environ.get('GRAPHHOPPER_KEY', '')
    GEOAPIFY_KEY = os.environ.get('GEOAPIFY_KEY', '')
    OPENWEATHER_KEY = os.environ.get('OPENWEATHER_KEY', '')
    
    # Constants
    SALIK_GATES = [
        {'name': 'Al Maktoum Bridge', 'lat': 25.2565, 'lon': 55.3348},
        {'name': 'Al Garhoud Bridge', 'lat': 25.2523, 'lon': 55.3486},
        {'name': 'Airport Tunnel', 'lat': 25.2432, 'lon': 55.3663},
        {'name': 'Al Safa', 'lat': 25.1922, 'lon': 55.2542},
        {'name': 'Al Barsha', 'lat': 25.1150, 'lon': 55.1960},
        {'name': 'Al Mamzar', 'lat': 25.2885, 'lon': 55.3422},
        {'name': 'Meydan', 'lat': 25.1665, 'lon': 55.3062},
        {'name': 'Jebel Ali', 'lat': 25.0170, 'lon': 55.0920}
    ]
    
    DRIVING_FUEL_COST_PER_KM = 3.0 / 12.0 # 3 AED per 12km
    SALIK_COST = 4.0
    PARKING_MALL_COST = 10.0
    
    TAXI_BASE_FARE = 12.0
    TAXI_RATE_PER_KM = 2.5
    
    METRO_RATE_SHORT = 3.0
    METRO_RATE_MEDIUM = 5.0
    METRO_RATE_LONG = 7.5
    
    BUS_BASE_FARE = 3.0
    BUS_RATE_PER_KM = 0.20
    
    # Emission Factors (g/km)
    EMISSION_CAR = 192
    EMISSION_TAXI = 150
    EMISSION_METRO = 45
    EMISSION_BUS = 89
    EMISSION_WALK = 0
    EMISSION_CYCLE = 0
    
    # Calories (kcal/km)
    CALORIES_WALK = 50
    CALORIES_CYCLE = 40
