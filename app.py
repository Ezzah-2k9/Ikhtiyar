
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from datetime import datetime, timedelta
import csv
import io
import math
import re
from uuid import uuid4
from config import Config
from database.db_manager import DBManager
from database.feature_store import FeatureStore
from services.geocoding_service import GeocodingService
from services.route_service import RouteService
from services.cost_calculator import CostCalculator
from services.co2_calculator import CO2Calculator
from services.weather_service import WeatherService
from services.transit_availability import check_metro_availability
from services.traffic_service import TrafficService
from services.gamification import build_weekly_challenges, current_week_start, level_from_points, uae_today
from services.monthly_goals import GOAL_METRICS, build_goal_state, month_key, previous_month_key
from ml.predictor import TransportPredictor
from ml.trip_recommender import TripRecommender
import os

app = Flask(__name__)
app.config.from_object(Config)
trip_quote_serializer = URLSafeTimedSerializer(app.secret_key)

db = DBManager()
feature_store = FeatureStore(db)


def monthly_goal_context(user_id, history, today=None):
    today = today or uae_today()
    privacy = db.get_privacy_settings(user_id)
    history_saving_enabled = bool(privacy.get('save_trip_history', True))
    period = month_key(today)
    current = build_goal_state(
        feature_store.get_monthly_goal(user_id, period), history, today
    )
    if current:
        current['history_saving_enabled'] = history_saving_enabled
    previous_period = previous_month_key(today)
    previous = build_goal_state(
        feature_store.get_monthly_goal(user_id, previous_period), history, today,
        finished=True,
    )
    if previous:
        outcome = 'reached' if previous['reached'] else 'was not met'
        previous['notice'] = (
            f"Last month's {previous['goal_label']} target {outcome}: "
            f"{previous['current_value']:.2f} / {previous['target_value']:.2f} {previous['goal_unit']}. "
            "You can set a new target for this month."
        )
    return {
        'current': current,
        'previous_notice': previous,
        'history_saving_enabled': history_saving_enabled,
    }

@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        user = db.verify_user(identifier, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        success, msg = db.register_user(username, email, password)
        if success:
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        else:
            flash(msg)
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
def index():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    # Get trip count for AI progress banner
    history = db.get_history(session['user_id'])
    trip_count = len(history)
    monthly_goal = monthly_goal_context(session['user_id'], history)['current']
    
    return render_template(
        'index.html', username=session['username'], trip_count=trip_count,
        traffic_available=TrafficService.is_configured(), monthly_goal=monthly_goal
    )

@app.route('/api/saved-destinations', methods=['GET', 'POST'])
def saved_destinations_api():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'GET':
        destinations = feature_store.get_saved_destinations(session['user_id'])
        return jsonify({'destinations': [
            {'destination_id': item['destination_id'], 'label': item['label'], 'place_name': item['place_name'],
             'latitude': item.get('latitude'), 'longitude': item.get('longitude')}
            for item in destinations
        ]})

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'A saved place name and label are required.'}), 400
    label = str(data.get('label', '')).strip()
    place_name = str(data.get('place_name', '')).strip()
    if not 2 <= len(label) <= 40:
        return jsonify({'error': 'The saved-place label must be 2–40 characters.'}), 400
    if not 2 <= len(place_name) <= 140:
        return jsonify({'error': 'The place name must be 2–140 characters.'}), 400
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if (latitude is None) != (longitude is None):
        return jsonify({'error': 'Saved-place coordinates must include both latitude and longitude.'}), 400
    if latitude is not None:
        try:
            latitude, longitude = float(latitude), float(longitude)
            if not (math.isfinite(latitude) and math.isfinite(longitude)
                    and -90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'Saved-place coordinates are invalid.'}), 400
    success, result = feature_store.add_saved_destination(
        session['user_id'], label, place_name, latitude, longitude
    )
    if not success:
        return jsonify({'error': result}), 409
    return jsonify({'success': True, 'destination': result}), 201

@app.route('/api/saved-destinations/<int:destination_id>', methods=['DELETE'])
def delete_saved_destination_api(destination_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    deleted = feature_store.delete_saved_destination(session['user_id'], destination_id)
    if not deleted:
        return jsonify({'error': 'Saved place not found.'}), 404
    return jsonify({'success': True})

@app.route('/api/traffic/<int:zoom>/<int:x>/<int:y>.png')
def traffic_tile(zoom, x, y):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    image, error, status = TrafficService.get_tile(zoom, x, y)
    if status != 200:
        return jsonify({'error': error}), status
    response = Response(image, mimetype='image/png')
    response.headers['Cache-Control'] = 'private, max-age=60'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.route('/recommendations')
def recommendations():
    """Get AI trip recommendations for the user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        privacy = db.get_privacy_settings(session['user_id'])
        if not privacy.get('personalized_recommendations', True):
            return jsonify({'ai_ready': False, 'recommendations': [], 'personalization_disabled': True})
        history = db.get_history(session['user_id'])
        trip_count = len(history)
        
        if trip_count < 10:
            return jsonify({
                'ai_ready': False,
                'recommendations': [],
                'trips_needed': 10 - trip_count
            })
        
        recommender = TripRecommender(session['user_id'])
        recs = recommender.get_recommendations(num_recommendations=6)
        
        return jsonify({
            'ai_ready': True,
            'recommendations': recs
        })
    except Exception as e:
        print(f"Recommendations error: {e}")
        return jsonify({
            'ai_ready': False,
            'recommendations': [],
            'error': str(e)
        }), 500

@app.route('/calculate_route', methods=['POST'])
def calculate_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(silent=True) or {}
        origin_name = str(data.get('origin', '')).strip()
        dest_name = str(data.get('destination', '')).strip()
        # Route ranking is based on saved preferences and the persistent monthly goal.
        goal = 'balanced'
        if not origin_name or not dest_name:
            return jsonify({'error': 'Origin and destination are required'}), 400
        if len(origin_name) > 140 or len(dest_name) > 140:
            return jsonify({'error': 'Place names must be 140 characters or less.'}), 400

        try:
            def resolve_place(name, prefix):
                raw_lat, raw_lon = data.get(f'{prefix}_lat'), data.get(f'{prefix}_lon')
                saved_id = data.get(f'{prefix}_saved_id')
                if raw_lat is None and raw_lon is None and saved_id is None:
                    return GeocodingService.get_coordinates(name)
                if raw_lat is None or raw_lon is None or saved_id is None:
                    raise ValueError('Choose a saved place to reuse its stored coordinates.')
                lat, lon = float(raw_lat), float(raw_lon)
                if not (math.isfinite(lat) and math.isfinite(lon)
                        and -90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError('Saved coordinates are outside valid latitude/longitude ranges.')
                try:
                    saved_id = int(saved_id)
                except (TypeError, ValueError):
                    raise ValueError('The selected saved place is invalid.')
                saved_place = feature_store.get_saved_destination(session['user_id'], saved_id)
                if not saved_place or saved_place.get('latitude') is None or saved_place.get('longitude') is None:
                    raise ValueError('The selected saved place could not be verified.')
                if abs(float(saved_place['latitude']) - lat) > 1e-6 or abs(float(saved_place['longitude']) - lon) > 1e-6:
                    raise ValueError('The selected saved place coordinates do not match your saved record.')
                return lat, lon, name

            o_lat, o_lon, o_display = resolve_place(origin_name, 'origin')
            d_lat, d_lon, d_display = resolve_place(dest_name, 'destination')
        except Exception as error:
            print(f"Geocoding failed ({type(error).__name__}).")
            return jsonify({'error': f'Geocoding failed: {str(error)}'}), 400

        try:
            routes = RouteService.get_route(o_lat, o_lon, d_lat, d_lon)
        except Exception as error:
            print(f"Route calculation failed ({type(error).__name__}).")
            return jsonify({'error': 'Route calculation failed. Please try again.'}), 500

        user_history = db.get_history(session['user_id'])
        goal_context = monthly_goal_context(session['user_id'], user_history)
        monthly_goal = goal_context['current']
        prefs = db.get_preferences(session['user_id']) or {}
        max_walk_temp = float(prefs.get('max_walking_temp', 40) or 40)
        try:
            weather = WeatherService.get_weather(d_lat, d_lon, max_walk_temp)
        except Exception as error:
            print(f"Weather service failed ({type(error).__name__}).")
            weather = {'is_live': False, 'temp': None, 'apparent_temp': None,
                       'advisories': [], 'description': 'Live weather unavailable'}
        apparent_temp = weather.get('apparent_temp') if weather.get('is_live') else None

        metro_info = check_metro_availability(o_lat, o_lon, d_lat, d_lon)
        straight_dist = RouteService.haversine(o_lat, o_lon, d_lat, d_lon)
        driving = routes['driving']
        walking = routes['walking']
        cycling = routes['cycling']
        dist_driving = float(driving['distance_km'])

        try:
            predictor = TransportPredictor(session['user_id'])
            recommended_mode = predictor.predict(
                dist_driving, datetime.now(), apparent_temp if apparent_temp is not None else 40
            )
        except Exception as error:
            print(f"Transport predictor unavailable: {error}")
            recommended_mode = 'driving'

        monthly_goal_active = bool(
            monthly_goal and goal_context['history_saving_enabled']
            and not monthly_goal['reached']
        )
        goal_label = (
            f"MONTHLY {monthly_goal['goal_label'].upper()} GOAL" if monthly_goal_active
            else 'YOUR PREFERENCES'
        )
        modes = ['driving', 'taxi', 'bus', 'walking', 'cycling']
        if metro_info.get('available'):
            modes.insert(2, 'metro')

        driving_co2 = CO2Calculator.calculate_emissions('driving', dist_driving)
        results = []
        for mode in modes:
            result = {'mode': mode, 'geometry': [], 'is_estimate': False, 'note': ''}
            if mode == 'driving':
                road_geometry = driving.get('geometry', [])
                route_is_estimate = bool(driving.get('is_estimate', True))
                result.update({
                    'distance': dist_driving,
                    'time': driving['duration_min'],
                    'cost': CostCalculator.calculate_driving_cost(dist_driving, road_geometry),
                    'geometry': road_geometry,
                    'is_estimate': route_is_estimate,
                })
                if result['is_estimate']:
                    result['note'] = 'Road distance and time are estimates; no live driving route is available.'
            elif mode == 'taxi':
                route_is_estimate = bool(driving.get('is_estimate', True))
                result.update({
                    'distance': dist_driving,
                    'time': driving['duration_min'],
                    'cost': CostCalculator.calculate_taxi_cost(dist_driving),
                    'geometry': driving.get('geometry', []),
                    'is_estimate': route_is_estimate,
                })
                result['note'] = 'Taxi fare is estimated and is not a live ride quote.'
            elif mode == 'metro':
                metro_distance = straight_dist * 1.15
                result.update({
                    'distance': round(metro_distance, 2),
                    'time': round((metro_distance / 40) * 60 + 20, 0),
                    'cost': CostCalculator.calculate_metro_cost(metro_distance),
                    'geometry': [],
                    'is_estimate': True,
                    'note': 'Estimated Metro option: both ends are near active stations; fare and time are not live transit data.',
                })
            elif mode == 'bus':
                bus_distance = straight_dist * 1.3
                result.update({
                    'distance': round(bus_distance, 2),
                    'time': round((bus_distance / 25) * 60, 0),
                    'cost': CostCalculator.calculate_bus_cost(bus_distance),
                    'geometry': [],
                    'is_estimate': True,
                    'note': 'Estimated bus fare and time; no live bus route or schedule is available.',
                })
            elif mode == 'walking':
                result.update({
                    'distance': walking['distance_km'],
                    'time': walking['duration_min'],
                    'cost': 0,
                    'geometry': walking.get('geometry', []),
                    'is_estimate': bool(walking.get('is_estimate', True)),
                })
                if result['is_estimate']:
                    result['note'] = 'Walking distance and time use a straight-line estimate.'
            elif mode == 'cycling':
                result.update({
                    'distance': cycling['distance_km'],
                    'time': cycling['duration_min'],
                    'cost': 0,
                    'geometry': cycling.get('geometry', []),
                    'is_estimate': bool(cycling.get('is_estimate', True)),
                })
                if result['is_estimate']:
                    result['note'] = 'Cycling distance and time use a straight-line estimate.'

            result['co2'] = CO2Calculator.calculate_emissions(mode, result['distance'])
            result['calories'] = CO2Calculator.calculate_calories(mode, result['distance'])
            results.append(result)

        raw_preferences = [
            max(1, min(10, int(prefs.get('priority_speed', 5)))),
            max(1, min(10, int(prefs.get('priority_cost', 5)))),
            max(1, min(10, int(prefs.get('priority_environment', 5)))),
        ]
        if monthly_goal_active:
            # A monthly goal can influence ranking, but every option remains selectable.
            if monthly_goal['goal_metric'] in ('co2_saved', 'sustainable_trips'):
                raw_preferences[2] = max(raw_preferences[2], 3 * (raw_preferences[0] + raw_preferences[1]))
            elif monthly_goal['goal_metric'] == 'budget':
                raw_preferences[1] = max(raw_preferences[1], 3 * (raw_preferences[0] + raw_preferences[2]))
            elif monthly_goal['goal_metric'] == 'active_distance':
                raw_preferences[2] = max(raw_preferences[2], 2 * (raw_preferences[0] + raw_preferences[1]))
        weight_sum = sum(raw_preferences) or 1
        weights = [value / weight_sum for value in raw_preferences]

        def utility(value, values):
            low, high = min(values), max(values)
            return 1.0 if high == low else (high - value) / (high - low)

        score_metrics = {
            'time': [float(item['time'] or 0) for item in results],
            'cost': [float(item['cost'] or 0) for item in results],
            'co2': [float(item['co2'] or 0) for item in results],
            'distance': [float(item['distance'] or 0) for item in results],
        }
        goal_metric = monthly_goal.get('goal_metric') if monthly_goal_active else None
        budget = float(prefs.get('budget_per_trip', 50) or 0)
        for index, item in enumerate(results):
            score = (
                weights[0] * utility(score_metrics['time'][index], score_metrics['time'])
                + weights[1] * utility(score_metrics['cost'][index], score_metrics['cost'])
                + weights[2] * utility(score_metrics['co2'][index], score_metrics['co2'])
            )
            if budget > 0 and float(item['cost'] or 0) > budget:
                score *= 0.85
            if goal_metric == 'active_distance':
                score *= 1.2 if item['mode'] in ('walking', 'cycling') else 0.8
            if apparent_temp is not None and apparent_temp >= max_walk_temp and item['mode'] in ('walking', 'cycling'):
                score *= 0.65
            if item['mode'] == recommended_mode:
                score += 0.02
            item['_rank_score'] = score

        results.sort(key=lambda item: item['_rank_score'], reverse=True)
        route_quote_id = uuid4().hex
        for rank, item in enumerate(results, start=1):
            item['rank'] = rank
            item['is_recommended'] = rank == 1
            item.pop('_rank_score', None)
            item['quote_token'] = trip_quote_serializer.dumps({
                'user_id': int(session['user_id']),
                'quote_id': route_quote_id,
                'origin': {'name': o_display, 'lat': o_lat, 'lon': o_lon},
                'destination': {'name': d_display, 'lat': d_lat, 'lon': d_lon},
                'mode': item['mode'],
                'cost': float(item['cost']),
                'time': float(item['time']),
                'distance': float(item['distance']),
                'co2': float(item['co2']),
                'driving_co2_baseline': float(driving_co2),
            }, salt='ikhtiyar-route-quote')

        if driving.get('is_estimate', True):
            route_estimate_note = (
                f"Driving road source: {routes.get('provider', 'built-in estimate')}. The dashed map line is only an approximate direction, not a street-level route. "
                "Set a valid ORS_KEY, GEOAPIFY_KEY, or TOMTOM_KEY (also accepted as TOMTOM_API_KEY) with routing access for a street-following route. "
            )
        else:
            route_estimate_note = f"Driving road source: {driving.get('provider', routes.get('provider', 'routing provider'))}; the solid map line follows mapped streets. Walking, cycling, and public-transit values may still be estimates. "
        route_estimate_note += (
            f"Metro check: {metro_info.get('reason', 'station coverage could not be confirmed')} "
            "Metro coverage uses mapped Dubai stations, not a live itinerary or timetable."
        )

        return jsonify({
            'origin': {'name': o_display, 'lat': o_lat, 'lon': o_lon},
            'destination': {'name': d_display, 'lat': d_lat, 'lon': d_lon},
            'requested_origin_name': origin_name,
            'requested_destination_name': dest_name,
            'results': results,
            'driving_co2_baseline': driving_co2,
            'goal': 'monthly' if monthly_goal_active else 'preferences',
            'goal_label': goal_label,
            'monthly_goal': monthly_goal,
            'weather': weather,
            'metro_availability': metro_info,
            'route_provider': routes.get('provider', 'built-in estimate'),
            'route_is_estimate': routes.get('is_estimate', True),
            'route_estimate_note': route_estimate_note,
        })
    except Exception as error:
        print(f"Unexpected route calculation error ({type(error).__name__}).")
        return jsonify({'error': 'Route calculation failed unexpectedly. Please try again.'}), 500

@app.route('/record_trip', methods=['POST'])
def record_trip():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    try:
        token = data.get('quote_token')
        if not isinstance(token, str) or not token:
            return jsonify({'error': 'Recalculate the route before selecting a transport option.'}), 400
        try:
            quote = trip_quote_serializer.loads(
                token, salt='ikhtiyar-route-quote', max_age=1800
            )
        except SignatureExpired:
            return jsonify({'error': 'This route selection expired. Please calculate the route again.'}), 400
        except BadSignature:
            return jsonify({'error': 'This route selection could not be verified. Please calculate again.'}), 400

        user_id = int(session['user_id'])
        if quote.get('user_id') != user_id:
            return jsonify({'error': 'This route selection belongs to a different account.'}), 403
        mode = str(quote.get('mode', '')).lower()
        if data.get('mode') and str(data['mode']).lower() != mode:
            return jsonify({'error': 'The selected transport does not match the route quote.'}), 400
        allowed_modes = {'driving', 'taxi', 'metro', 'bus', 'walking', 'cycling'}
        if mode not in allowed_modes:
            return jsonify({'error': 'Choose a valid transport option.'}), 400

        origin = quote.get('origin') or {}
        destination = quote.get('destination') or {}
        required = (origin.get('name'), origin.get('lat'), origin.get('lon'),
                    destination.get('name'), destination.get('lat'), destination.get('lon'))
        if not all(value is not None for value in required):
            return jsonify({'error': 'The route quote is incomplete. Please calculate the route again.'}), 400
        driving_co2 = float(quote['driving_co2_baseline'])
        chosen_co2 = float(quote['co2'])
        cost, duration, distance = float(quote['cost']), float(quote['time']), float(quote['distance'])
        if not all(math.isfinite(value) and value >= 0 for value in (driving_co2, chosen_co2, cost, duration, distance)):
            return jsonify({'error': 'The route quote contains invalid values. Please calculate again.'}), 400
        saved = max(0, driving_co2 - chosen_co2)

        privacy = db.get_privacy_settings(user_id)
        if not privacy.get('save_trip_history', True):
            return jsonify({'success': True, 'saved_co2': saved, 'saved_to_history': False})
        if not feature_store.claim_trip_quote(user_id, quote.get('quote_id')):
            return jsonify({'error': 'A transport option for this route was already recorded. Calculate a new route to continue.'}), 409
        db.add_trip(
            user_id, origin['name'], origin['lat'], origin['lon'],
            destination['name'], destination['lat'], destination['lon'], mode,
            cost, duration, chosen_co2, saved, distance
        )

        trip_day = uae_today()
        reward = feature_store.award_trip_points(
            user_id, trip_day, mode, saved
        )
        history = db.get_history(user_id)
        challenges = build_weekly_challenges(history, trip_day)
        challenge_rewards = []
        week_start = current_week_start(trip_day).isoformat()
        for challenge in challenges:
            if challenge['is_complete'] and feature_store.award_weekly_challenge(
                user_id, week_start, challenge['key'], challenge['reward_xp']
            ):
                challenge_rewards.append({
                    'key': challenge['key'],
                    'title': challenge['title'],
                    'points_awarded': challenge['reward_xp'],
                })
        reward['challenge_rewards'] = challenge_rewards
        reward['total_points'] = feature_store.get_gamification(user_id)['total_points']

        if len(history) % 10 == 0:
            try:
                predictor = TransportPredictor(user_id)
                predictor.train_model()
                if len(history) == 10:
                    TripRecommender(user_id).train_model()
            except Exception as error:
                print(f"Model training error: {error}")

        return jsonify({
            'success': True, 'saved_co2': saved, 'saved_to_history': True,
            'gamification': reward,
        })
    except (TypeError, ValueError, KeyError) as error:
        print(f"record_trip validation error ({type(error).__name__}).")
        return jsonify({'error': 'Trip details are invalid. Please calculate the route again.'}), 400
    except Exception as error:
        print(f"record_trip failed ({type(error).__name__}).")
        return jsonify({'error': 'The trip could not be saved right now.'}), 500

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    stats = db.get_monthly_stats(session['user_id'])
    if not stats:
        stats = {
            'total_trips': 0, 'total_cost': 0, 'total_co2': 0, 'co2_saved': 0,
            'driving_trips': 0, 'taxi_trips': 0, 'metro_trips': 0, 'bus_trips': 0, 
            'walking_trips': 0, 'cycling_trips': 0, 'green_points': 0
        }
    
    # Recent trips
    history = db.get_history(session['user_id'])
    recent = history[:5]
    monthly_goals = monthly_goal_context(session['user_id'], history)
    today = uae_today()
    week_start = current_week_start(today).isoformat()
    weekly_challenges = build_weekly_challenges(history, today)
    for challenge in weekly_challenges:
        if challenge['is_complete']:
            feature_store.award_weekly_challenge(
                session['user_id'], week_start, challenge['key'], challenge['reward_xp']
            )
        challenge['rewarded'] = bool(challenge['is_complete'])
    progress = feature_store.get_gamification(session['user_id'])
    last_trip_date = str(progress.get('last_trip_date') or '')[:10]
    current_streak = int(progress.get('current_streak') or 0)
    if last_trip_date not in {today.isoformat(), (today - timedelta(days=1)).isoformat()}:
        current_streak = 0
    gamification = level_from_points(progress.get('total_points', 0))
    gamification.update({
        'current_streak': current_streak,
        'best_streak': int(progress.get('best_streak') or 0),
        'last_trip_date': last_trip_date or None,
    })
    # psycopg2 returns DATE/TIME columns as Python objects. Flask's JSON
    # serializer cannot encode datetime.time values in the dashboard's tojson block.
    for trip in recent:
        for field in ('trip_date', 'trip_time'):
            value = trip.get(field)
            if hasattr(value, 'isoformat'):
                trip[field] = value.isoformat()
    
    return render_template(
        'dashboard.html', stats=stats, recent=recent, username=session['username'],
        gamification=gamification, weekly_challenges=weekly_challenges,
        monthly_goal=monthly_goals['current'], monthly_goal_notice=monthly_goals['previous_notice']
    )

@app.route('/history')
def history():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    history = db.get_history(session['user_id'])
    return render_template('history.html', history=history, username=session['username'])

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'profile':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not 2 <= len(username) <= 50:
                flash('Username must be between 2 and 50 characters.', 'error')
                return redirect(url_for('settings', tab='profile'))
            if len(email) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                flash('Enter a valid email address.', 'error')
                return redirect(url_for('settings', tab='profile'))
            if new_password or confirm_password:
                if len(new_password) < 8:
                    flash('A new password must be at least 8 characters.', 'error')
                    return redirect(url_for('settings', tab='profile'))
                if new_password != confirm_password:
                    flash('The new password and confirmation do not match.', 'error')
                    return redirect(url_for('settings', tab='profile'))
                if not current_password:
                    flash('Enter your current password to change it.', 'error')
                    return redirect(url_for('settings', tab='profile'))

            success, message = db.update_user_account(
                user_id, username, email,
                current_password=current_password if new_password else None,
                new_password=new_password or None
            )
            if success:
                session['username'] = username
                flash(message + (' Password changed successfully.' if new_password else ''), 'success')
            else:
                flash(message, 'error')
            return redirect(url_for('settings', tab='profile'))

        if action == 'preferences':
            try:
                speed = int(request.form.get('priority_speed', 5))
                cost = int(request.form.get('priority_cost', 5))
                environment = int(request.form.get('priority_environment', 5))
                max_walk_temp = float(request.form.get('max_walking_temp', 40))
                budget = float(request.form.get('budget_per_trip', 50))
                if not all(1 <= value <= 10 for value in (speed, cost, environment)):
                    raise ValueError('Priority scores must be between 1 and 10.')
                if not math.isfinite(max_walk_temp) or not 20 <= max_walk_temp <= 55:
                    raise ValueError('Walking temperature must be between 20 and 55 °C.')
                if not math.isfinite(budget) or not 0 <= budget <= 10000:
                    raise ValueError('Trip budget must be between 0 and 10,000 AED.')
                db.update_preferences(user_id, speed, cost, environment, max_walk_temp, budget)
                flash('Travel preferences saved. Route recommendations will use them.', 'success')
            except (TypeError, ValueError) as error:
                flash(str(error) or 'Please enter valid preference values.', 'error')
            return redirect(url_for('settings', tab='preferences'))

        if action == 'privacy':
            db.update_privacy_settings(
                user_id,
                request.form.get('save_trip_history') == 'on',
                request.form.get('personalized_recommendations') == 'on'
            )
            flash('Privacy settings saved.', 'success')
            return redirect(url_for('settings', tab='privacy'))

        if action == 'monthly_goal':
            try:
                metric = str(request.form.get('goal_metric', 'co2_saved'))
                if metric not in GOAL_METRICS:
                    raise ValueError('Choose a valid monthly goal metric.')
                target = float(request.form.get('target_value', '0'))
                if not math.isfinite(target) or target <= 0 or target > 100000:
                    raise ValueError('Enter a positive monthly target within the allowed range.')
                period = month_key(uae_today())
                feature_store.save_monthly_goal(user_id, period, round(target, 2), metric)
                flash('Monthly travel goal saved. All saved trips this month count toward it.', 'success')
            except (TypeError, ValueError) as error:
                flash(str(error) or 'Enter a valid monthly CO₂ target.', 'error')
            return redirect(url_for('settings', tab='preferences'))

        flash('That settings action is not recognized.', 'error')
        return redirect(url_for('settings'))

    user = db.get_user_by_id(user_id) or {}
    prefs = db.get_preferences(user_id) or {
        'priority_speed': 5, 'priority_cost': 5, 'priority_environment': 5,
        'max_walking_temp': 40, 'budget_per_trip': 50
    }
    privacy = db.get_privacy_settings(user_id)
    current_month = month_key(uae_today())
    monthly_goal = feature_store.get_monthly_goal(user_id, current_month)
    monthly_goal_state = build_goal_state(monthly_goal, db.get_history(user_id), uae_today())
    if monthly_goal_state:
        monthly_goal_state['history_saving_enabled'] = bool(privacy.get('save_trip_history', True))
    active_tab = request.args.get('tab', 'profile')
    if active_tab not in ('profile', 'preferences', 'privacy'):
        active_tab = 'profile'
    return render_template(
        'settings.html', user=user, prefs=prefs, privacy=privacy,
        username=session['username'], email=user.get('email', ''), active_tab=active_tab,
        monthly_goal=monthly_goal_state
    )

@app.route('/settings/export')
def export_personal_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['Date', 'Origin', 'Destination', 'Transport', 'Distance (km)', 'Cost (AED)', 'CO2 (kg)', 'CO2 saved (kg)'])
    for trip in db.get_history(session['user_id']):
        writer.writerow([
            trip.get('trip_date', ''), trip.get('origin_name', ''), trip.get('destination_name', ''),
            trip.get('chosen_transport', ''), trip.get('distance_km', 0), trip.get('chosen_cost', 0),
            trip.get('chosen_co2', 0), trip.get('co2_saved', 0)
        ])
    response = make_response('﻿' + output.getvalue())
    response.mimetype = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename="ikhtiyar-trip-history.csv"'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/dashboard/pdf')
def download_dashboard_pdf():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from io import BytesIO
        from flask import make_response
        
        user_id = session['user_id']
        username = session['username']
        history = db.get_history(user_id)
        stats = db.get_monthly_stats(user_id)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#5D1F1A'),
            alignment=1
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#D4AF37'),
        )
        
        normal_style = styles['Normal']
        story = []
        
        story.append(Paragraph("اختيار IKHTIYAR", title_style))
        story.append(Paragraph("Activity Report", title_style))
        story.append(Paragraph(f"Generated for: {username}", normal_style))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", normal_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Summary Statistics", heading_style))
        story.append(Spacer(1, 12))
        
        stats_data = [
            ['Metric', 'Value'],
            ['Total Trips', str(stats.get('total_trips', 0) if stats else 0)],
            ['CO₂ Saved (kg)', f"{stats.get('co2_saved', 0) if stats else 0:.2f}"],
            ['Total Cost (AED)', f"{stats.get('total_cost', 0) if stats else 0:.2f}"],
            ['Green Points', str(stats.get('green_points', 0) if stats else 0)]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8F4E6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2C2416')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#D4AF37')),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.white),
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 30))
        
        story.append(Paragraph("Recent Trips", heading_style))
        story.append(Spacer(1, 12))
        
        if history:
            trips_data = [['Route', 'Transport', 'Distance', 'Cost', 'CO₂ Saved']]
            
            for trip in history[:10]:
                route = f"{trip.get('origin_name', 'Unknown')} → {trip.get('destination_name', 'Unknown')}"
                transport = trip.get('chosen_transport', 'Unknown').title()
                distance = f"{trip.get('distance_km', 0):.1f} km"
                cost = f"{trip.get('chosen_cost', 0):.2f} AED"
                co2_saved = f"-{trip.get('co2_saved', 0):.2f} kg" if trip.get('co2_saved', 0) > 0 else "0 kg"
                
                trips_data.append([route, transport, distance, cost, co2_saved])
            
            trips_table = Table(trips_data, colWidths=[2.5*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1*inch])
            trips_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5D1F1A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Roman'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E8DCC4')),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
            ]))
            
            story.append(trips_table)
        else:
            story.append(Paragraph("No trips recorded yet.", normal_style))
        
        story.append(Spacer(1, 30))
        story.append(Paragraph("Thank you for using Ikhtiyar - Your Smart Transport Choice", normal_style))
        
        doc.build(story)
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=ikhtiyar-activity-report-{username}.pdf'
        
        return response
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        return jsonify({'error': 'Failed to generate PDF'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')
