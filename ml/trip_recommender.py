
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import RandomForestClassifier
from database.db_manager import DBManager

class TripRecommender:
    def __init__(self, user_id):
        self.user_id = user_id
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', f'user_{user_id}_trip_rec.pkl')
        self.model = None
        self.db = DBManager()
        
        # UAE destinations dataset with features
        self.uae_destinations = self._load_uae_destinations()
        
        # Ensure models dir exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()
    
    def _load_uae_destinations(self):
        """Load UAE destinations with categorized features"""
        destinations = [
            # Dubai
            {"name": "Burj Khalifa", "city": "Dubai", "category": "landmark", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 1, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "Dubai Mall", "city": "Dubai", "category": "shopping", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 1, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "Dubai Marina", "city": "Dubai", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 1, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Jumeirah Beach", "city": "Dubai", "category": "beach", "type": "natural", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Gold Souk", "city": "Dubai", "category": "shopping", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 1, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Dubai Museum", "city": "Dubai", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Global Village", "city": "Dubai", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 1, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "Ski Dubai", "city": "Dubai", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            
            # Abu Dhabi
            {"name": "Sheikh Zayed Grand Mosque", "city": "Abu Dhabi", "category": "cultural", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Louvre Abu Dhabi", "city": "Abu Dhabi", "category": "cultural", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 1, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Yas Island", "city": "Abu Dhabi", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 1, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "Ferrari World", "city": "Abu Dhabi", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "Corniche Beach", "city": "Abu Dhabi", "category": "beach", "type": "natural", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Qasr Al Watan", "city": "Abu Dhabi", "category": "cultural", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            
            # Sharjah
            {"name": "Sharjah Museum of Islamic Civilization", "city": "Sharjah", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Al Noor Mosque", "city": "Sharjah", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Al Qasba", "city": "Sharjah", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 0},
            {"name": "Sharjah Aquarium", "city": "Sharjah", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 0, "entertainment": 1, "nature": 1, "beach": 0},
            
            # Ajman
            {"name": "Ajman Beach", "city": "Ajman", "category": "beach", "type": "natural", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Ajman Museum", "city": "Ajman", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            
            # Umm Al Quwain
            {"name": "Dreamland Aqua Park", "city": "Umm Al Quwain", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 0, "beach": 0},
            {"name": "UAQ Marine Museum", "city": "Umm Al Quwain", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 1, "beach": 0},
            
            # Ras Al Khaimah
            {"name": "Jebel Jais", "city": "Ras Al Khaimah", "category": "adventure", "type": "natural", "family_friendly": 0, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 0, "entertainment": 1, "nature": 1, "beach": 0},
            {"name": "RAK Beach", "city": "Ras Al Khaimah", "category": "beach", "type": "natural", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Suwaidi Pearls Farm", "city": "Ras Al Khaimah", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 1, "beach": 0},
            
            # Fujairah
            {"name": "Fujairah Beach", "city": "Fujairah", "category": "beach", "type": "natural", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 1},
            {"name": "Fujairah Museum", "city": "Fujairah", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Snoopy Island", "city": "Fujairah", "category": "adventure", "type": "natural", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 0, "entertainment": 1, "nature": 1, "beach": 1},
            
            # Al Ain
            {"name": "Al Ain Zoo", "city": "Al Ain", "category": "entertainment", "type": "modern", "family_friendly": 1, "adventure": 0, "cultural": 0, "shopping": 0, "dining": 1, "entertainment": 1, "nature": 1, "beach": 0},
            {"name": "Jebel Hafeet", "city": "Al Ain", "category": "adventure", "type": "natural", "family_friendly": 1, "adventure": 1, "cultural": 0, "shopping": 0, "dining": 0, "entertainment": 1, "nature": 1, "beach": 0},
            {"name": "Al Ain Museum", "city": "Al Ain", "category": "cultural", "type": "traditional", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 0, "beach": 0},
            {"name": "Al Ain Oasis", "city": "Al Ain", "category": "nature", "type": "natural", "family_friendly": 1, "adventure": 0, "cultural": 1, "shopping": 0, "dining": 0, "entertainment": 0, "nature": 1, "beach": 0}
        ]
        
        return pd.DataFrame(destinations)
    
    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
    
    def train_model(self):
        """Train recommendation model based on user trip history"""
        trips = self.db.get_history(self.user_id)
        if len(trips) < 10:
            return False
        
        df = pd.DataFrame(trips)
        
        # Analyze user preferences from trip destinations
        user_preferences = self._analyze_user_preferences(df)
        
        # Create training data based on user's visited destinations
        training_data = []
        for _, trip in df.iterrows():
            dest_name = trip['destination_name']
            # Find matching destination in UAE dataset
            matches = self.uae_destinations[self.uae_destinations['name'].str.contains(dest_name, case=False, na=False)]
            
            if not matches.empty:
                dest_features = matches.iloc[0]
                # User liked this destination (they visited it)
                training_data.append({
                    **dest_features.to_dict(),
                    'preferred': 1
                })
        
        if len(training_data) < 5:
            return False
        
        train_df = pd.DataFrame(training_data)
        
        # Features for training
        feature_cols = ['family_friendly', 'adventure', 'cultural', 'shopping', 'dining', 'entertainment', 'nature', 'beach']
        X = train_df[feature_cols]
        y = train_df['preferred']
        
        # Train Random Forest for preference prediction
        clf = RandomForestClassifier(n_estimators=50, max_depth=8, min_samples_split=2)
        clf.fit(X, y)
        
        # Save model and user preferences
        model_data = {
            'classifier': clf,
            'user_preferences': user_preferences,
            'feature_columns': feature_cols
        }
        
        joblib.dump(model_data, self.model_path)
        self.model = model_data
        return True
    
    def _analyze_user_preferences(self, df):
        """Analyze user preferences from trip history"""
        preferences = {
            'avg_distance': df['distance_km'].mean() if not df.empty else 0,
            'preferred_transport': df['chosen_transport'].mode().iloc[0] if not df.empty else 'driving',
            'time_patterns': self._analyze_time_patterns(df),
            'city_frequency': df['destination_name'].value_counts().to_dict()
        }
        return preferences
    
    def _analyze_time_patterns(self, df):
        """Analyze time patterns from trip data"""
        if df.empty:
            return {'morning': 0, 'afternoon': 0, 'evening': 0, 'night': 0}
        
        def get_time_period(time_str):
            try:
                hour = int(str(time_str).split(':')[0])
                if 5 <= hour < 12: return 'morning'
                elif 12 <= hour < 17: return 'afternoon'
                elif 17 <= hour < 21: return 'evening'
                else: return 'night'
            except:
                return 'morning'
        
        df['time_period'] = df['trip_time'].apply(get_time_period)
        return df['time_period'].value_counts().to_dict()
    
    def get_recommendations(self, num_recommendations=5):
        """Get trip recommendations for the user"""
        if not self.model:
            return self._get_fallback_recommendations(num_recommendations)
        
        # Get user's visited destinations
        user_trips = self.db.get_history(self.user_id)
        visited_destinations = set([trip['destination_name'].lower() for trip in user_trips])
        
        # Predict preference scores for all destinations
        feature_cols = self.model['feature_columns']
        classifier = self.model['classifier']
        
        scores = []
        for _, dest in self.uae_destinations.iterrows():
            if dest['name'].lower() not in visited_destinations:
                features = dest[feature_cols].values.reshape(1, -1)
                score = classifier.predict_proba(features)[0][1]  # Probability of preference
                scores.append((dest['name'], dest['city'], dest['category'], score))
        
        # Sort by score and get top recommendations
        scores.sort(key=lambda x: x[3], reverse=True)
        recommendations = []
        
        for name, city, category, score in scores[:num_recommendations]:
            recommendations.append({
                'name': name,
                'city': city,
                'category': category,
                'confidence_score': round(score * 100, 1),
                'reason': self._get_recommendation_reason(name, category)
            })
        
        return recommendations
    
    def _get_fallback_recommendations(self, num_recommendations=5):
        """Fallback recommendations when model is not trained"""
        # Popular UAE destinations that are generally well-liked
        popular_destinations = [
            "Burj Khalifa", "Dubai Mall", "Sheikh Zayed Grand Mosque", 
            "Jumeirah Beach", "Yas Island", "Louvre Abu Dhabi", 
            "Global Village", "Al Ain Zoo", "Jebel Jais", "Fujairah Beach"
        ]
        
        user_trips = self.db.get_history(self.user_id)
        visited_destinations = set([trip['destination_name'].lower() for trip in user_trips])
        
        recommendations = []
        for dest_name in popular_destinations:
            if dest_name.lower() not in visited_destinations and len(recommendations) < num_recommendations:
                dest_info = self.uae_destinations[self.uae_destinations['name'] == dest_name]
                if not dest_info.empty:
                    dest = dest_info.iloc[0]
                    recommendations.append({
                        'name': dest['name'],
                        'city': dest['city'],
                        'category': dest['category'],
                        'confidence_score': 75.0,  # Default confidence
                        'reason': f"Popular {dest['category']} destination in {dest['city']}"
                    })
        
        return recommendations
    
    def _get_recommendation_reason(self, name, category):
        """Generate a reason for the recommendation"""
        reasons = {
            'landmark': "Iconic UAE landmark you shouldn't miss",
            'shopping': "Great shopping experience based on your interests",
            'beach': "Beautiful beach destination for relaxation",
            'cultural': "Rich cultural experience awaits",
            'entertainment': "Fun entertainment destination",
            'adventure': "Exciting adventure for thrill seekers",
            'nature': "Natural beauty and tranquility"
        }
        return reasons.get(category, "Recommended based on your preferences")
