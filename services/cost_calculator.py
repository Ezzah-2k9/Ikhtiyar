
from config import Config
from services.route_service import RouteService

class CostCalculator:
    @staticmethod
    def calculate_driving_cost(distance_km, route_geometry):
        # Fuel
        fuel_cost = (distance_km / 12.0) * 3.0
        
        # Salik
        salik_gates_count = 0
        gates = Config.SALIK_GATES
        
        # Simple detection: check if any point in route is close to a gate
        # This is expensive O(N*M). Minimize route points if possible or check only some.
        # For fallback straight line, we check points along the line.
        # If geometry is dense, we sample.
        
        # To avoid double counting, we track which gates were hit
        hit_gates = set()
        
        # Sample every 10th point to speed up if dense
        step = 1 if len(route_geometry) < 100 else len(route_geometry) // 50
        
        for i in range(0, len(route_geometry), step):
            pt = route_geometry[i] # [lat, lon]
            for idx, gate in enumerate(gates):
                if idx in hit_gates:
                    continue
                dist = RouteService.haversine(pt[0], pt[1], gate['lat'], gate['lon'])
                if dist < 0.2: # 200m radius roughly
                    hit_gates.add(idx)
        
        salik_cost = len(hit_gates) * Config.SALIK_COST
        
        # Parking (Assuming destination is mall/attraction for MVP if not specified)
        # We can pass destination name later, but for now fixed or random?
        # User defined rule: "10 AED (if destination is mall/attraction)"
        # Since we don't have dest type, let's assume 10 AED for now as safe estimate or 0.
        # Let's say 10 AED.
        parking_cost = 10.0 
        
        return round(fuel_cost + salik_cost + parking_cost, 2)

    @staticmethod
    def calculate_taxi_cost(distance_km):
        return round(Config.TAXI_BASE_FARE + (distance_km * Config.TAXI_RATE_PER_KM), 2)

    @staticmethod
    def calculate_metro_cost(distance_km):
        if distance_km < 5:
            return Config.METRO_RATE_SHORT
        elif distance_km < 15:
            return Config.METRO_RATE_MEDIUM
        else:
            return Config.METRO_RATE_LONG

    @staticmethod
    def calculate_bus_cost(distance_km):
        return round(Config.BUS_BASE_FARE + (distance_km * Config.BUS_RATE_PER_KM), 2)
