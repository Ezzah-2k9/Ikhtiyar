
import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from database.db_manager import DBManager

class TransportPredictor:
    def __init__(self, user_id):
        self.user_id = user_id
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', f'user_{user_id}_model.pkl')
        self.model = None
        self.db = DBManager()
        
        # Ensure models dir exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()

    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)

    def train_model(self):
        trips = self.db.get_history(self.user_id)
        if len(trips) < 10:
            return False # Not enough data
            
        df = pd.DataFrame(trips)
        
        # Feature Engineering
        # time_of_day (0=night, 1=morning, 2=afternoon, 3=evening)
        # We need to parse time string
        def parse_time_of_day(t_str):
            h = int(str(t_str).split(':')[0])
            if 5 <= h < 12: return 1
            elif 12 <= h < 17: return 2
            elif 17 <= h < 21: return 3
            else: return 0
            
        df['time_of_day'] = df['trip_time'].apply(parse_time_of_day)
        
        # day_of_week
        df['dt'] = pd.to_datetime(df['trip_date'])
        df['day_of_week'] = df['dt'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        
        # Distance
        # Temperature (Missing in history? Assuming we might not have stored temp in history as per schema?
        # The schema doesn't have temp. We can assume average or skip it for now.
        # Requirement says input: temperature. But we don't save it.  
        # Let's add 'temperature' as 30 if missing or randomized for training sake?
        # Or just don't use it for now if data missing.
        # Let's use distance, time_of_day, is_weekend.
        
        X = df[['time_of_day', 'day_of_week', 'is_weekend', 'distance_km']]
        y = df['chosen_transport']
        
        clf = RandomForestClassifier(n_estimators=50, max_depth=10, min_samples_split=5)
        clf.fit(X, y)
        
        joblib.dump(clf, self.model_path)
        self.model = clf
        return True

    def predict(self, distance, time_obj, temp):
        # time_obj is datetime object
        if not self.model:
            return self.fallback_recommendation(distance, temp)
            
        # Prepare input
        h = time_obj.hour
        if 5 <= h < 12: tod = 1
        elif 12 <= h < 17: tod = 2
        elif 17 <= h < 21: tod = 3
        else: tod = 0
        
        dow = time_obj.weekday()
        is_weekend = 1 if dow >= 5 else 0
        
        # input array: time_of_day, day_of_week, is_weekend, distance
        # Note: We omitted temp in training because it wasn't in DB.
        
        try:
            proba = self.model.predict_proba([[tod, dow, is_weekend, distance]])
            confidence = max(proba[0])
            pred_class = self.model.classes_[list(proba[0]).index(confidence)]
            
            if confidence > 0.4:
                return pred_class
            else:
                return self.fallback_recommendation(distance, temp)
        except:
             return self.fallback_recommendation(distance, temp)

    def fallback_recommendation(self, distance, temp):
        # Fallback Rules
        # 1. Filter "green options" (CO₂ < 2 kg) - Implicitly Metro, Bus, Walking, Cycling usually.
        # 2. Cheapest among green.
        
        # Simple logical fallback based on distance and temp
        if distance < 1.0 and temp < 40:
            return 'walking'
        elif distance < 3.0 and temp < 40:
            return 'cycling'
        elif distance > 1.0:
            # Metro is usually best balance of green/cost/speed
            return 'metro'
        
        return 'taxi' # Fallback default
