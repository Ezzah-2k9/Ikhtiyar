
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response
from datetime import datetime
import csv
import io
import math
import re
from config import Config
from database.db_manager import DBManager
from services.geocoding_service import GeocodingService
from services.route_service import RouteService
from services.cost_calculator import CostCalculator
from services.co2_calculator import CO2Calculator
from services.weather_service import WeatherService
from ml.predictor import TransportPredictor
from ml.trip_recommender import TripRecommender
import os

app = Flask(__name__)
app.config.from_object(Config)

db = DBManager()

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
    
    return render_template('index.html', username=session['username'], trip_count=trip_count)

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
        data = request.json
        origin_name = data.get('origin')
        dest_name = data.get('destination')
        
        if not origin_name or not dest_name:
            return jsonify({'error': 'Origin and destination are required'}), 400
        
        print(f"Route request: {origin_name} -> {dest_name}")
        
        # 1. Geocode
        try:
            o_lat, o_lon, o_display = GeocodingService.get_coordinates(origin_name)
            d_lat, d_lon, d_display = GeocodingService.get_coordinates(dest_name)
        except Exception as e:
            print(f"Geocoding failed: {e}")
            return jsonify({'error': f'Geocoding failed: {str(e)}'}), 400

        # 2. Routes (Driving used as baseline dist usually, or specific route for each)
        try:
            routes = RouteService.get_route(o_lat, o_lon, d_lat, d_lon)
            print(f"Route service returned: {routes}")
        except Exception as e:
            print(f"Route calculation failed: {e}")
            return jsonify({'error': f'Route calculation failed: {str(e)}'}), 500
        
        # 3. Weather
        try:
            weather = WeatherService.get_weather(o_lat, o_lon)
            temp = weather['temp']
        except Exception as e:
            print(f"Weather service failed: {e}")
            temp = 25  # Default temperature
        
        # 4. Predict
        predictor = TransportPredictor(session['user_id'])
        recommended_mode = predictor.predict(routes['driving']['distance_km'], datetime.now(), temp)
        
        # 5. Build Results
        results = []
        modes = ['driving', 'taxi', 'metro', 'bus', 'walking', 'cycling']
        
        # Base distances
        dist_driving = routes['driving']['distance_km']
        dist_walking = routes['walking']['distance_km']
        dist_cycling = routes['cycling']['distance_km']
        
        # Custom Route Logic for Metro/Bus (Estimation)
        straight_dist = RouteService.haversine(o_lat, o_lon, d_lat, d_lon)
        
        driving_co2 = CO2Calculator.calculate_emissions('driving', dist_driving)
        
        for mode in modes:
            res = {}
            res['mode'] = mode
            res['is_recommended'] = (mode == recommended_mode)
            
            if mode == 'driving':
                res['distance'] = dist_driving
                res['time'] = routes['driving']['duration_min']
                res['cost'] = CostCalculator.calculate_driving_cost(dist_driving, routes['driving']['geometry'])
                res['geometry'] = routes['driving']['geometry']
                
            elif mode == 'taxi':
                res['distance'] = dist_driving
                res['time'] = routes['driving']['duration_min']
                res['cost'] = CostCalculator.calculate_taxi_cost(dist_driving)
                res['geometry'] = routes['driving']['geometry']
                 
            elif mode == 'metro':
                est_dist = straight_dist * 1.15
                est_time = (est_dist / 40) * 60 + 20
                res['distance'] = round(est_dist, 2)
                res['time'] = round(est_time, 0)
                res['cost'] = CostCalculator.calculate_metro_cost(est_dist)
                res['geometry'] = [[o_lat, o_lon], [d_lat, d_lon]]
                
            elif mode == 'bus':
                est_dist = straight_dist * 1.3
                est_time = (est_dist / 25) * 60
                res['distance'] = round(est_dist, 2)
                res['time'] = round(est_time, 0)
                res['cost'] = CostCalculator.calculate_bus_cost(est_dist)
                res['geometry'] = [[o_lat, o_lon], [d_lat, d_lon]]
                
            elif mode == 'walking':
                res['distance'] = dist_walking
                res['time'] = routes['walking']['duration_min']
                res['cost'] = 0
                res['geometry'] = routes['walking']['geometry']
                 
            elif mode == 'cycling':
                res['distance'] = dist_cycling
                res['time'] = routes['cycling']['duration_min']
                res['cost'] = 0
                res['geometry'] = routes['cycling']['geometry']

            res['co2'] = CO2Calculator.calculate_emissions(mode, res['distance'])
            res['calories'] = CO2Calculator.calculate_calories(mode, res['distance'])
            
            results.append(res)

        # Rank routes by the member's saved speed/cost/environment priorities.
        prefs = db.get_preferences(session['user_id']) or {}
        raw_weights = [
            max(1, min(10, int(prefs.get('priority_speed', 5)))),
            max(1, min(10, int(prefs.get('priority_cost', 5)))),
            max(1, min(10, int(prefs.get('priority_environment', 5))))
        ]
        weight_total = sum(raw_weights) or 1
        weights = [value / weight_total for value in raw_weights]
        metrics = {
            'time': [float(item.get('time', 0) or 0) for item in results],
            'cost': [float(item.get('cost', 0) or 0) for item in results],
            'co2': [float(item.get('co2', 0) or 0) for item in results]
        }
        def utility(value, values):
            low, high = min(values), max(values)
            return 1.0 if high == low else (high - value) / (high - low)
        budget = float(prefs.get('budget_per_trip', 50) or 0)
        max_walk_temp = float(prefs.get('max_walking_temp', 40) or 40)
        for index, item in enumerate(results):
            score = (
                weights[0] * utility(metrics['time'][index], metrics['time']) +
                weights[1] * utility(metrics['cost'][index], metrics['cost']) +
                weights[2] * utility(metrics['co2'][index], metrics['co2'])
            )
            if budget > 0 and float(item.get('cost', 0) or 0) > budget:
                score *= 0.75
            if temp is not None and float(temp) > max_walk_temp and item.get('mode') in ('walking', 'cycling'):
                score *= 0.75
            if item.get('mode') == recommended_mode:
                score += 0.04
            item['_preference_score'] = score
        best_mode = max(results, key=lambda item: item['_preference_score'])['mode'] if results else recommended_mode
        for item in results:
            item['is_recommended'] = item.get('mode') == best_mode
            item.pop('_preference_score', None)

        return jsonify({
            'origin': {'name': o_display, 'lat': o_lat, 'lon': o_lon},
            'destination': {'name': d_display, 'lat': d_lat, 'lon': d_lon},
            'results': results,
            'driving_co2_baseline': driving_co2
        })
        
    except Exception as e:
        print(f"Unexpected error in calculate_route: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/record_trip', methods=['POST'])
def record_trip():
    if 'user_id' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    
    # Calculate savings. Respect the member's choice not to retain new trip records.
    driving_co2 = data.get('driving_co2_baseline', 0)
    chosen_co2 = data.get('co2')
    saved = max(0, driving_co2 - chosen_co2)
    privacy = db.get_privacy_settings(session['user_id'])
    if not privacy.get('save_trip_history', True):
        return jsonify({'success': True, 'saved_co2': saved, 'saved_to_history': False})
    
    db.add_trip(
        session['user_id'],
        data['origin']['name'], data['origin']['lat'], data['origin']['lon'],
        data['destination']['name'], data['destination']['lat'], data['destination']['lon'],
        data['mode'],
        data['cost'],
        data['time'],
        chosen_co2,
        saved,
        data['distance']
    )
    
    # Check for retraining
    hist = db.get_history(session['user_id'])
    if len(hist) % 10 == 0:
        try:
            pred = TransportPredictor(session['user_id'])
            pred.train_model()
            
            if len(hist) == 10:
                rec = TripRecommender(session['user_id'])
                rec.train_model()
        except Exception as e:
            print(f"Model training error: {e}")
        
    return jsonify({'success': True, 'saved_co2': saved, 'saved_to_history': True})

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
    # psycopg2 returns DATE/TIME columns as Python objects. Flask's JSON
    # serializer cannot encode datetime.time values in the dashboard's tojson block.
    for trip in recent:
        for field in ('trip_date', 'trip_time'):
            value = trip.get(field)
            if hasattr(value, 'isoformat'):
                trip[field] = value.isoformat()
    
    return render_template('dashboard.html', stats=stats, recent=recent, username=session['username'])

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

        flash('That settings action is not recognized.', 'error')
        return redirect(url_for('settings'))

    user = db.get_user_by_id(user_id) or {}
    prefs = db.get_preferences(user_id) or {
        'priority_speed': 5, 'priority_cost': 5, 'priority_environment': 5,
        'max_walking_temp': 40, 'budget_per_trip': 50
    }
    privacy = db.get_privacy_settings(user_id)
    active_tab = request.args.get('tab', 'profile')
    if active_tab not in ('profile', 'preferences', 'privacy'):
        active_tab = 'profile'
    return render_template(
        'settings.html', user=user, prefs=prefs, privacy=privacy,
        username=session['username'], email=user.get('email', ''), active_tab=active_tab
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
