
from config import Config

class CO2Calculator:
    @staticmethod
    def calculate_emissions(mode, distance_km):
        factor = 0
        if mode == 'driving': factor = Config.EMISSION_CAR
        elif mode == 'taxi': factor = Config.EMISSION_TAXI
        elif mode == 'metro': factor = Config.EMISSION_METRO
        elif mode == 'bus': factor = Config.EMISSION_BUS
        elif mode == 'walking': factor = Config.EMISSION_WALK
        elif mode == 'cycling': factor = Config.EMISSION_CYCLE
        
        # Emissions in kg
        return round((distance_km * factor) / 1000.0, 2)

    @staticmethod
    def calculate_calories(mode, distance_km):
        if mode == 'walking':
            return int(distance_km * Config.CALORIES_WALK)
        elif mode == 'cycling':
            return int(distance_km * Config.CALORIES_CYCLE)
        return 0
