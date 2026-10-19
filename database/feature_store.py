"""Feature persistence for saved places and travel gamification.

The core DBManager remains unchanged; this adapter shares its existing
SQLite/PostgreSQL connection path and creates additive tables on startup.
"""

import sqlite3
from datetime import date, timedelta

from database.db_manager import USING_POSTGRES


class FeatureStore:
    MAX_SAVED_DESTINATIONS = 25

    def __init__(self, db_manager):
        self.db = db_manager
        self.init_tables()

    def init_tables(self):
        conn, cursor = self.db.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS saved_destinations (
                        destination_id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        label TEXT NOT NULL,
                        place_name TEXT NOT NULL,
                        latitude DOUBLE PRECISION,
                        longitude DOUBLE PRECISION,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_gamification (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        total_points INTEGER NOT NULL DEFAULT 0,
                        current_streak INTEGER NOT NULL DEFAULT 0,
                        best_streak INTEGER NOT NULL DEFAULT 0,
                        last_trip_date TEXT,
                        last_daily_reward_date TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS weekly_challenge_rewards (
                        reward_id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        week_start TEXT NOT NULL,
                        challenge_key TEXT NOT NULL,
                        points_awarded INTEGER NOT NULL,
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, week_start, challenge_key)
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trip_quote_claims (
                        quote_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS monthly_travel_goals (
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        month TEXT NOT NULL,
                        target_co2_kg DOUBLE PRECISION NOT NULL CHECK (target_co2_kg > 0),
                        goal_metric TEXT NOT NULL DEFAULT 'co2_saved',
                        target_value DOUBLE PRECISION NOT NULL DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, month)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS saved_destinations (
                        destination_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        label TEXT NOT NULL,
                        place_name TEXT NOT NULL,
                        latitude REAL,
                        longitude REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_gamification (
                        user_id INTEGER PRIMARY KEY,
                        total_points INTEGER NOT NULL DEFAULT 0,
                        current_streak INTEGER NOT NULL DEFAULT 0,
                        best_streak INTEGER NOT NULL DEFAULT 0,
                        last_trip_date TEXT,
                        last_daily_reward_date TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS weekly_challenge_rewards (
                        reward_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        week_start TEXT NOT NULL,
                        challenge_key TEXT NOT NULL,
                        points_awarded INTEGER NOT NULL,
                        completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, week_start, challenge_key),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trip_quote_claims (
                        quote_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS monthly_travel_goals (
                        user_id INTEGER NOT NULL,
                        month TEXT NOT NULL,
                        target_co2_kg REAL NOT NULL CHECK (target_co2_kg > 0),
                        goal_metric TEXT NOT NULL DEFAULT 'co2_saved',
                        target_value REAL NOT NULL DEFAULT 0,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, month),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_destinations_user_label "
                "ON saved_destinations(user_id, lower(label))"
            )
            if USING_POSTGRES:
                cursor.execute("ALTER TABLE monthly_travel_goals ADD COLUMN IF NOT EXISTS goal_metric TEXT NOT NULL DEFAULT 'co2_saved'")
                cursor.execute("ALTER TABLE monthly_travel_goals ADD COLUMN IF NOT EXISTS target_value DOUBLE PRECISION NOT NULL DEFAULT 0")
                cursor.execute("UPDATE monthly_travel_goals SET target_value = target_co2_kg WHERE target_value = 0")
                cursor.execute("ALTER TABLE saved_destinations ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION")
                cursor.execute("ALTER TABLE saved_destinations ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION")
            else:
                cursor.execute("PRAGMA table_info(monthly_travel_goals)")
                goal_columns = {row['name'] for row in cursor.fetchall()}
                if 'goal_metric' not in goal_columns:
                    cursor.execute("ALTER TABLE monthly_travel_goals ADD COLUMN goal_metric TEXT NOT NULL DEFAULT 'co2_saved'")
                if 'target_value' not in goal_columns:
                    cursor.execute("ALTER TABLE monthly_travel_goals ADD COLUMN target_value REAL NOT NULL DEFAULT 0")
                cursor.execute("UPDATE monthly_travel_goals SET target_value = target_co2_kg WHERE target_value = 0")
                cursor.execute("PRAGMA table_info(saved_destinations)")
                columns = {row['name'] for row in cursor.fetchall()}
                if 'latitude' not in columns:
                    cursor.execute("ALTER TABLE saved_destinations ADD COLUMN latitude REAL")
                if 'longitude' not in columns:
                    cursor.execute("ALTER TABLE saved_destinations ADD COLUMN longitude REAL")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def get_saved_destinations(self, user_id):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT destination_id, label, place_name, latitude, longitude, created_at FROM saved_destinations "
                f"WHERE user_id = {placeholder} ORDER BY lower(label), destination_id",
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def get_saved_destination(self, user_id, destination_id):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT destination_id, label, place_name, latitude, longitude "
                f"FROM saved_destinations WHERE user_id = {placeholder} AND destination_id = {placeholder}",
                (user_id, destination_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    def claim_trip_quote(self, user_id, quote_id):
        """Atomically consume a signed route quote once for one account."""
        conn, cursor = self.db.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute(
                    "INSERT INTO trip_quote_claims (quote_id,user_id) VALUES (%s,%s) "
                    "ON CONFLICT (quote_id) DO NOTHING RETURNING quote_id",
                    (quote_id, user_id),
                )
                claimed = cursor.fetchone() is not None
            else:
                cursor.execute(
                    "INSERT INTO trip_quote_claims (quote_id,user_id) VALUES (?,?) "
                    "ON CONFLICT(quote_id) DO NOTHING",
                    (quote_id, user_id),
                )
                claimed = cursor.rowcount > 0
            conn.commit()
            return claimed
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def get_monthly_goal(self, user_id, month):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT user_id, month, target_co2_kg, goal_metric, target_value, updated_at FROM monthly_travel_goals "
                f"WHERE user_id = {placeholder} AND month = {placeholder}",
                (user_id, month),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    def save_monthly_goal(self, user_id, month, target_value, goal_metric='co2_saved'):
        """Upsert this user's selected target for one calendar month."""
        conn, cursor = self.db.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute(
                    "INSERT INTO monthly_travel_goals (user_id, month, target_co2_kg, goal_metric, target_value) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id, month) DO UPDATE "
                    "SET target_co2_kg = EXCLUDED.target_co2_kg, goal_metric = EXCLUDED.goal_metric, "
                    "target_value = EXCLUDED.target_value, updated_at = CURRENT_TIMESTAMP",
                    (user_id, month, target_value, goal_metric, target_value),
                )
            else:
                cursor.execute(
                    "INSERT INTO monthly_travel_goals (user_id, month, target_co2_kg, goal_metric, target_value) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, month) DO UPDATE "
                    "SET target_co2_kg = excluded.target_co2_kg, goal_metric = excluded.goal_metric, "
                    "target_value = excluded.target_value, updated_at = CURRENT_TIMESTAMP",
                    (user_id, month, target_value, goal_metric, target_value),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def remove_monthly_goal(self, user_id, month):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"DELETE FROM monthly_travel_goals WHERE user_id = {placeholder} AND month = {placeholder}",
                (user_id, month),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def add_saved_destination(self, user_id, label, place_name, latitude=None, longitude=None):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM saved_destinations WHERE user_id = {placeholder}",
                (user_id,),
            )
            if int(cursor.fetchone()["total"]) >= self.MAX_SAVED_DESTINATIONS:
                return False, "You can save up to 25 favourite places."
            cursor.execute(
                f"SELECT destination_id FROM saved_destinations WHERE user_id = {placeholder} "
                f"AND lower(label) = lower({placeholder})",
                (user_id, label),
            )
            if cursor.fetchone():
                return False, "You already use that name for a saved place."
            if USING_POSTGRES:
                cursor.execute(
                    "INSERT INTO saved_destinations (user_id, label, place_name, latitude, longitude) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING destination_id",
                    (user_id, label, place_name, latitude, longitude),
                )
                destination_id = cursor.fetchone()["destination_id"]
            else:
                cursor.execute(
                    "INSERT INTO saved_destinations (user_id, label, place_name, latitude, longitude) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, label, place_name, latitude, longitude),
                )
                destination_id = cursor.lastrowid
            conn.commit()
            return True, {
                "destination_id": destination_id,
                "label": label,
                "place_name": place_name,
                "latitude": latitude,
                "longitude": longitude,
            }
        except Exception as error:
            conn.rollback()
            message = str(error).lower()
            if "unique" in message or "duplicate" in message:
                return False, "You already use that name for a saved place."
            print(f"add_saved_destination error: {error}")
            return False, "Could not save that place. Please try again."
        finally:
            cursor.close()
            conn.close()

    def delete_saved_destination(self, user_id, destination_id):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"DELETE FROM saved_destinations WHERE user_id = {placeholder} "
                f"AND destination_id = {placeholder}",
                (user_id, destination_id),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        except Exception as error:
            conn.rollback()
            print(f"delete_saved_destination error: {error}")
            return False
        finally:
            cursor.close()
            conn.close()

    def _ensure_gamification_row(self, cursor, user_id):
        if USING_POSTGRES:
            cursor.execute(
                "INSERT INTO user_gamification (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
                (user_id,),
            )
        else:
            cursor.execute(
                "INSERT INTO user_gamification (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING",
                (user_id,),
            )

    def get_gamification(self, user_id):
        conn, cursor = self.db.get_connection()
        try:
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT * FROM user_gamification WHERE user_id = {placeholder}",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "total_points": 0,
                    "current_streak": 0,
                    "best_streak": 0,
                    "last_trip_date": None,
                    "last_daily_reward_date": None,
                }
            return dict(row)
        finally:
            cursor.close()
            conn.close()

    def award_trip_points(self, user_id, trip_date, transport, co2_saved):
        today = trip_date if isinstance(trip_date, date) else date.fromisoformat(str(trip_date)[:10])
        today_text = today.isoformat()
        yesterday_text = (today - timedelta(days=1)).isoformat()
        sustainable = str(transport).lower() in {"metro", "bus", "walking", "cycling"}
        trip_xp = (10 if sustainable else 3) + min(25, max(0, int(round(float(co2_saved or 0) * 10))))

        conn, cursor = self.db.get_connection()
        try:
            self._ensure_gamification_row(cursor, user_id)
            placeholder = "%s" if USING_POSTGRES else "?"
            cursor.execute(
                f"SELECT * FROM user_gamification WHERE user_id = {placeholder}",
                (user_id,),
            )
            state = dict(cursor.fetchone())
            previous_date = str(state.get("last_trip_date") or "")[:10]
            last_daily = str(state.get("last_daily_reward_date") or "")[:10]
            current_streak = int(state.get("current_streak") or 0)
            if previous_date == today_text:
                next_streak = current_streak
            elif previous_date == yesterday_text:
                next_streak = current_streak + 1
            else:
                next_streak = 1
            daily_bonus = 5 if last_daily != today_text else 0
            total_points = int(state.get("total_points") or 0) + trip_xp + daily_bonus
            best_streak = max(int(state.get("best_streak") or 0), next_streak)
            if USING_POSTGRES:
                cursor.execute(
                    "UPDATE user_gamification SET total_points=%s,current_streak=%s,best_streak=%s,"
                    "last_trip_date=%s,last_daily_reward_date=%s,updated_at=CURRENT_TIMESTAMP WHERE user_id=%s",
                    (total_points, next_streak, best_streak, today_text,
                     today_text if daily_bonus else state.get("last_daily_reward_date"), user_id),
                )
            else:
                cursor.execute(
                    "UPDATE user_gamification SET total_points=?,current_streak=?,best_streak=?,"
                    "last_trip_date=?,last_daily_reward_date=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                    (total_points, next_streak, best_streak, today_text,
                     today_text if daily_bonus else state.get("last_daily_reward_date"), user_id),
                )
            conn.commit()
            return {
                "trip_xp": trip_xp,
                "daily_bonus": daily_bonus,
                "xp_awarded": trip_xp + daily_bonus,
                "current_streak": next_streak,
                "best_streak": best_streak,
                "total_points": total_points,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def award_weekly_challenge(self, user_id, week_start, challenge_key, points):
        conn, cursor = self.db.get_connection()
        try:
            if USING_POSTGRES:
                cursor.execute(
                    "INSERT INTO weekly_challenge_rewards (user_id,week_start,challenge_key,points_awarded) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (user_id,week_start,challenge_key) DO NOTHING",
                    (user_id, str(week_start), challenge_key, int(points)),
                )
            else:
                cursor.execute(
                    "INSERT INTO weekly_challenge_rewards (user_id,week_start,challenge_key,points_awarded) "
                    "VALUES (?,?,?,?) ON CONFLICT(user_id,week_start,challenge_key) DO NOTHING",
                    (user_id, str(week_start), challenge_key, int(points)),
                )
            awarded = cursor.rowcount > 0
            if awarded:
                self._ensure_gamification_row(cursor, user_id)
                placeholder = "%s" if USING_POSTGRES else "?"
                cursor.execute(
                    f"UPDATE user_gamification SET total_points=total_points+{placeholder}, "
                    f"updated_at=CURRENT_TIMESTAMP WHERE user_id={placeholder}",
                    (int(points), user_id),
                )
            conn.commit()
            return awarded
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
