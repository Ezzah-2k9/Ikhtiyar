
import sqlite3
import hashlib
from datetime import datetime
from config import Config
import os

# Check if using PostgreSQL
if Config.DB_PATH.startswith('postgresql://'):
    import psycopg2
    import psycopg2.extras as psycopg2_extras
    USING_POSTGRES = True
else:
    USING_POSTGRES = False


class DBManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self.init_db()

    def get_connection(self):
        if USING_POSTGRES:
            conn = psycopg2.connect(self.db_path)
            cursor = conn.cursor(cursor_factory=psycopg2_extras.RealDictCursor)
            return conn, cursor
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn, conn.cursor()

    def init_db(self):
        if USING_POSTGRES:
            conn, cursor = self.get_connection()
            try:
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS trips (
                    trip_id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    origin_name TEXT NOT NULL,
                    origin_lat REAL,
                    origin_lon REAL,
                    destination_name TEXT NOT NULL,
                    destination_lat REAL,
                    destination_lon REAL,
                    chosen_transport TEXT NOT NULL,
                    chosen_cost REAL DEFAULT 0,
                    chosen_time REAL DEFAULT 0,
                    chosen_co2 REAL DEFAULT 0,
                    co2_saved REAL DEFAULT 0,
                    distance_km REAL DEFAULT 0,
                    trip_date DATE DEFAULT CURRENT_DATE,
                    trip_time TIME DEFAULT CURRENT_TIME,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS monthly_stats (
                    stat_id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    total_trips INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    total_co2 REAL DEFAULT 0,
                    co2_saved REAL DEFAULT 0,
                    driving_trips INTEGER DEFAULT 0,
                    taxi_trips INTEGER DEFAULT 0,
                    metro_trips INTEGER DEFAULT 0,
                    bus_trips INTEGER DEFAULT 0,
                    walking_trips INTEGER DEFAULT 0,
                    cycling_trips INTEGER DEFAULT 0,
                    green_points INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, month)
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    priority_speed INTEGER DEFAULT 5,
                    priority_cost INTEGER DEFAULT 5,
                    priority_environment INTEGER DEFAULT 5,
                    max_walking_temp REAL DEFAULT 40.0,
                    budget_per_trip REAL DEFAULT 50.0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_privacy_settings (
                    user_id INTEGER PRIMARY KEY,
                    save_trip_history BOOLEAN NOT NULL DEFAULT TRUE,
                    personalized_recommendations BOOLEAN NOT NULL DEFAULT TRUE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                conn.commit()
            finally:
                cursor.close()
                conn.close()
        else:
            conn, cursor = self.get_connection()
            try:
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS trips (
                    trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    origin_name TEXT NOT NULL,
                    origin_lat REAL,
                    origin_lon REAL,
                    destination_name TEXT NOT NULL,
                    destination_lat REAL,
                    destination_lon REAL,
                    chosen_transport TEXT NOT NULL,
                    chosen_cost REAL DEFAULT 0,
                    chosen_time REAL DEFAULT 0,
                    chosen_co2 REAL DEFAULT 0,
                    co2_saved REAL DEFAULT 0,
                    distance_km REAL DEFAULT 0,
                    trip_date DATE DEFAULT (date('now')),
                    trip_time TIME DEFAULT (time('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS monthly_stats (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    total_trips INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    total_co2 REAL DEFAULT 0,
                    co2_saved REAL DEFAULT 0,
                    driving_trips INTEGER DEFAULT 0,
                    taxi_trips INTEGER DEFAULT 0,
                    metro_trips INTEGER DEFAULT 0,
                    bus_trips INTEGER DEFAULT 0,
                    walking_trips INTEGER DEFAULT 0,
                    cycling_trips INTEGER DEFAULT 0,
                    green_points INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, month)
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    priority_speed INTEGER DEFAULT 5,
                    priority_cost INTEGER DEFAULT 5,
                    priority_environment INTEGER DEFAULT 5,
                    max_walking_temp REAL DEFAULT 40.0,
                    budget_per_trip REAL DEFAULT 50.0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_privacy_settings (
                    user_id INTEGER PRIMARY KEY,
                    save_trip_history INTEGER NOT NULL DEFAULT 1,
                    personalized_recommendations INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                ''')

                conn.commit()
            finally:
                cursor.close()
                conn.close()

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, email, password):
        conn, cursor = self.get_connection()
        hashed_pw = self.hash_password(password)
        try:
            if USING_POSTGRES:
                cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id',
                               (username, email, hashed_pw))
                user_id = cursor.fetchone()['id']
            else:
                cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                               (username, email, hashed_pw))
                user_id = cursor.lastrowid

            if USING_POSTGRES:
                cursor.execute('INSERT INTO user_preferences (user_id) VALUES (%s)', (user_id,))
            else:
                cursor.execute('INSERT INTO user_preferences (user_id) VALUES (?)', (user_id,))

            conn.commit()
            return True, user_id
        except Exception as e:
            conn.rollback()
            if USING_POSTGRES:
                if 'unique' in str(e).lower():
                    return False, "Username or Email already exists"
            else:
                if isinstance(e, sqlite3.IntegrityError):
                    return False, "Username or Email already exists"
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def verify_user(self, identifier, password):
        conn, cursor = self.get_connection()
        hashed_pw = self.hash_password(password)

        if USING_POSTGRES:
            cursor.execute('SELECT * FROM users WHERE (username = %s OR email = %s) AND password = %s',
                           (identifier, identifier, hashed_pw))
            user = cursor.fetchone()

            if user:
                cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user['id'],))
                conn.commit()
                cursor.close()
                conn.close()
                return dict(user)
        else:
            cursor.execute('SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?',
                           (identifier, identifier, hashed_pw))
            user = cursor.fetchone()

            if user:
                cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
                conn.commit()
                cursor.close()
                conn.close()
                return dict(user)

        cursor.close()
        conn.close()
        return None

    def get_user_by_id(self, user_id):
        conn, cursor = self.get_connection()
        if USING_POSTGRES:
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(user) if user else None

    def update_user_account(self, user_id, username, email, current_password=None, new_password=None):
        """Update account identity; password changes require the current password."""
        conn, cursor = self.get_connection()
        try:
            if new_password:
                if USING_POSTGRES:
                    cursor.execute('SELECT password FROM users WHERE id = %s', (user_id,))
                else:
                    cursor.execute('SELECT password FROM users WHERE id = ?', (user_id,))
                row = cursor.fetchone()
                if not row:
                    return False, 'Account not found.'
                stored_hash = row['password']
                if self.hash_password(current_password or '') != stored_hash:
                    return False, 'Current password is incorrect; no changes were made.'

                if USING_POSTGRES:
                    cursor.execute(
                        'UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s',
                        (username, email, self.hash_password(new_password), user_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE users SET username = ?, email = ?, password = ? WHERE id = ?',
                        (username, email, self.hash_password(new_password), user_id)
                    )
            else:
                if USING_POSTGRES:
                    cursor.execute('UPDATE users SET username = %s, email = %s WHERE id = %s', (username, email, user_id))
                else:
                    cursor.execute('UPDATE users SET username = ?, email = ? WHERE id = ?', (username, email, user_id))

            if cursor.rowcount == 0:
                conn.rollback()
                return False, 'Account not found.'
            conn.commit()
            return True, 'Account details updated.'
        except Exception as error:
            conn.rollback()
            message = str(error).lower()
            if 'unique' in message or 'duplicate' in message:
                return False, 'That username or email address is already in use.'
            return False, 'Could not update your account. Please try again.'
        finally:
            cursor.close()
            conn.close()

    def get_preferences(self, user_id):
        conn, cursor = self.get_connection()
        if USING_POSTGRES:
            cursor.execute('SELECT * FROM user_preferences WHERE user_id = %s', (user_id,))
        else:
            cursor.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        prefs = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(prefs) if prefs else None

    def update_preferences(self, user_id, speed, cost, env, max_walk_temp, budget):
        conn, cursor = self.get_connection()
        if USING_POSTGRES:
            cursor.execute('''
                UPDATE user_preferences
                SET priority_speed = %s, priority_cost = %s, priority_environment = %s,
                    max_walking_temp = %s, budget_per_trip = %s
                WHERE user_id = %s
            ''', (speed, cost, env, max_walk_temp, budget, user_id))
        else:
            cursor.execute('''
                UPDATE user_preferences
                SET priority_speed = ?, priority_cost = ?, priority_environment = ?,
                    max_walking_temp = ?, budget_per_trip = ?
                WHERE user_id = ?
            ''', (speed, cost, env, max_walk_temp, budget, user_id))
        conn.commit()
        cursor.close()
        conn.close()

    def get_privacy_settings(self, user_id):
        conn, cursor = self.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute('SELECT * FROM user_privacy_settings WHERE user_id = %s', (user_id,))
            else:
                cursor.execute('SELECT * FROM user_privacy_settings WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if not row:
                return {'save_trip_history': True, 'personalized_recommendations': True}
            settings = dict(row)
            settings['save_trip_history'] = bool(settings.get('save_trip_history', True))
            settings['personalized_recommendations'] = bool(settings.get('personalized_recommendations', True))
            return settings
        finally:
            cursor.close()
            conn.close()

    def update_privacy_settings(self, user_id, save_trip_history, personalized_recommendations):
        conn, cursor = self.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute('''
                    INSERT INTO user_privacy_settings (user_id, save_trip_history, personalized_recommendations)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        save_trip_history = EXCLUDED.save_trip_history,
                        personalized_recommendations = EXCLUDED.personalized_recommendations
                ''', (user_id, bool(save_trip_history), bool(personalized_recommendations)))
            else:
                cursor.execute('''
                    INSERT INTO user_privacy_settings (user_id, save_trip_history, personalized_recommendations)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        save_trip_history = excluded.save_trip_history,
                        personalized_recommendations = excluded.personalized_recommendations
                ''', (user_id, int(bool(save_trip_history)), int(bool(personalized_recommendations))))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def add_trip(self, user_id, origin_name, origin_lat, origin_lon,
                 dest_name, dest_lat, dest_lon, transport, cost, time_min, co2, co2_saved, distance):
        conn, cursor = self.get_connection()

        if USING_POSTGRES:
            cursor.execute('''
                INSERT INTO trips (user_id, origin_name, origin_lat, origin_lon,
                                   destination_name, destination_lat, destination_lon,
                                   chosen_transport, chosen_cost, chosen_time, chosen_co2, co2_saved, distance_km)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (user_id, origin_name, origin_lat, origin_lon, dest_name, dest_lat, dest_lon,
                  transport, cost, time_min, co2, co2_saved, distance))
        else:
            cursor.execute('''
                INSERT INTO trips (user_id, origin_name, origin_lat, origin_lon,
                                   destination_name, destination_lat, destination_lon,
                                   chosen_transport, chosen_cost, chosen_time, chosen_co2, co2_saved, distance_km)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, origin_name, origin_lat, origin_lon, dest_name, dest_lat, dest_lon,
                  transport, cost, time_min, co2, co2_saved, distance))

        # Update monthly stats
        current_month = datetime.now().strftime('%Y-%m')

        if USING_POSTGRES:
            cursor.execute('SELECT * FROM monthly_stats WHERE user_id = %s AND month = %s', (user_id, current_month))
        else:
            cursor.execute('SELECT * FROM monthly_stats WHERE user_id = ? AND month = ?', (user_id, current_month))
        stats = cursor.fetchone()

        mapping = {
            'driving': 'driving_trips', 'car': 'driving_trips',
            'taxi': 'taxi_trips',
            'metro': 'metro_trips',
            'bus': 'bus_trips',
            'walking': 'walking_trips',
            'cycling': 'cycling_trips'
        }
        target_col = mapping.get(transport, 'driving_trips')

        green_points = 0
        if co2_saved > 0:
            green_points = int(co2_saved * 10)

        if stats:
            if USING_POSTGRES:
                cursor.execute(f'''
                    UPDATE monthly_stats
                    SET total_trips = total_trips + 1,
                        total_cost = total_cost + %s,
                        total_co2 = total_co2 + %s,
                        co2_saved = co2_saved + %s,
                        {target_col} = {target_col} + 1,
                        green_points = green_points + %s
                    WHERE stat_id = %s
                ''', (cost, co2, co2_saved, green_points, stats['stat_id']))
            else:
                cursor.execute(f'''
                    UPDATE monthly_stats
                    SET total_trips = total_trips + 1,
                        total_cost = total_cost + ?,
                        total_co2 = total_co2 + ?,
                        co2_saved = co2_saved + ?,
                        {target_col} = {target_col} + 1,
                        green_points = green_points + ?
                    WHERE stat_id = ?
                ''', (cost, co2, co2_saved, green_points, stats['stat_id']))
        else:
            if USING_POSTGRES:
                cursor.execute(f'''
                    INSERT INTO monthly_stats (user_id, month, total_trips, total_cost, total_co2, co2_saved, {target_col}, green_points)
                    VALUES (%s, %s, 1, %s, %s, %s, 1, %s)
                ''', (user_id, current_month, cost, co2, co2_saved, green_points))
            else:
                cursor.execute(f'''
                    INSERT INTO monthly_stats (user_id, month, total_trips, total_cost, total_co2, co2_saved, {target_col}, green_points)
                    VALUES (?, ?, 1, ?, ?, ?, 1, ?)
                ''', (user_id, current_month, cost, co2, co2_saved, green_points))

        conn.commit()
        cursor.close()
        conn.close()

    def get_history(self, user_id):
        conn, cursor = self.get_connection()
        if USING_POSTGRES:
            cursor.execute('SELECT * FROM trips WHERE user_id = %s ORDER BY trip_date DESC, trip_time DESC', (user_id,))
        else:
            cursor.execute('SELECT * FROM trips WHERE user_id = ? ORDER BY trip_date DESC, trip_time DESC', (user_id,))
        trips = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(row) for row in trips]

    def get_monthly_stats(self, user_id, month=None):
        if not month:
            month = datetime.now().strftime('%Y-%m')
        conn, cursor = self.get_connection()
        if USING_POSTGRES:
            cursor.execute('SELECT * FROM monthly_stats WHERE user_id = %s AND month = %s', (user_id, month))
        else:
            cursor.execute('SELECT * FROM monthly_stats WHERE user_id = ? AND month = ?', (user_id, month))
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(stats) if stats else None

    def clear_history(self, user_id):
        """Delete all trips for a user (used by /clear_history endpoint)."""
        conn, cursor = self.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute('DELETE FROM trips WHERE user_id = %s', (user_id,))
                cursor.execute('DELETE FROM monthly_stats WHERE user_id = %s', (user_id,))
            else:
                cursor.execute('DELETE FROM trips WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM monthly_stats WHERE user_id = ?', (user_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"clear_history error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
