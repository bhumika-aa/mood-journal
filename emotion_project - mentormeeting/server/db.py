from __future__ import annotations

import os
from typing import Any, Optional
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class DatabaseManager:
    """
    Manages all database operations for the Mood Journal application.
    Encapsulates connectivity and query logic into an Object-Oriented structure.
    """

    def __init__(self):
        self.config = {
            "host": self._env("MYSQL_HOST", "127.0.0.1"),
            "port": int(self._env("MYSQL_PORT", "3306")),
            "user": self._env("MYSQL_USER"),
            "password": self._env("MYSQL_PASSWORD", ""),
            "database": self._env("MYSQL_DATABASE"),
        }

    @staticmethod
    def _env(name: str, default: Optional[str] = None) -> Optional[str]:
        val = os.getenv(name)
        if val is None or val == "":
            return default
        return val

    def is_available(self) -> bool:
        return bool(self.config["user"] and self.config["database"])

    def connect(self):
        if not self.is_available():
            raise RuntimeError(
                "MySQL is not configured. Set MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE."
            )
        return mysql.connector.connect(**self.config)

    @contextmanager
    def get_cursor(self, dictionary: bool = False):
        conn = self.connect()
        try:
            cur = conn.cursor(dictionary=dictionary)
            yield cur, conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def init_db(self) -> None:
        if not self.is_available():
            return
        
        with self.get_cursor() as (cur, _):
            # Create users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    name VARCHAR(255),
                    password_hash VARCHAR(255),
                    is_admin TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrations / Column checks
            for col, spec in [("is_admin", "TINYINT(1) DEFAULT 0"), ("password_hash", "VARCHAR(255)")]:
                cur.execute(f"SHOW COLUMNS FROM users LIKE '{col}'")
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col} {spec}")

            # Mood Journals table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mood_journals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    selected_mood VARCHAR(50),
                    selected_secondary_emotion VARCHAR(100),
                    selected_cause VARCHAR(100),
                    journal_text TEXT,
                    predicted_mood VARCHAR(50),
                    predicted_emotion VARCHAR(50),
                    predicted_secondary_emotion VARCHAR(100),
                    confidence FLOAT,
                    is_match TINYINT(1),
                    feedback VARCHAR(10),
                    risk_level VARCHAR(50),
                    matched_phrases TEXT,
                    is_favourite TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrations for mood_journals
            cur.execute("SHOW COLUMNS FROM mood_journals LIKE 'is_favourite'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE mood_journals ADD COLUMN is_favourite TINYINT(1) DEFAULT 0")

            cols = {
                "depression_level": "VARCHAR(50)",
                "anxiety_level": "VARCHAR(50)",
                "depression_score": "INT",
                "anxiety_score": "INT",
                "wellness_score": "INT",
                "wellness_level": "VARCHAR(50)",
                "recommendations": "TEXT"
            }
            for col, col_type in cols.items():
                cur.execute(f"SHOW COLUMNS FROM mood_journals LIKE '{col}'")
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE mood_journals ADD COLUMN {col} {col_type}")

            # Trusted Contacts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trusted_contacts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT UNIQUE,
                    contact_email VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Activities Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255),
                    description TEXT,
                    duration VARCHAR(50),
                    category VARCHAR(100),
                    target_emotion VARCHAR(50),
                    icon VARCHAR(50),
                    image_url VARCHAR(255),
                    audio_url VARCHAR(255),
                    action_type VARCHAR(50) DEFAULT 'article',
                    prompt TEXT,
                    content TEXT
                )
            """)

            column_checks = {
                "icon": "VARCHAR(50)",
                "image_url": "VARCHAR(255)",
                "audio_url": "VARCHAR(255)",
                "action_type": "VARCHAR(50) DEFAULT 'article'",
                "prompt": "TEXT",
                "content": "TEXT"
            }
            for col, col_type in column_checks.items():
                cur.execute(f"SHOW COLUMNS FROM activities LIKE '{col}'")
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE activities ADD COLUMN {col} {col_type}")

            # System Settings (for editable email templates)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` TEXT
                )
            """)
            
            # Default Email Template
            default_email = """Hello,

This is an automated message from MoodJournal.

Your trusted contact has been experiencing consistently low emotional moods for the past 15 days. This notification is being sent because you were selected as their trusted support contact.

Please consider checking in with them and offering support if appropriate.

This alert is not a medical diagnosis and is only intended as a wellness support feature.

— MoodJournal Support System"""
            
            cur.execute("INSERT IGNORE INTO system_settings (`key`, `value`) VALUES (%s, %s)", ("trusted_contact_email_template", default_email))

            # Activity Logs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    activity_id INT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed Activities (Truncate and reload for consistency)
            cur.execute("TRUNCATE TABLE activities")

            sample_activities = [
                ("Gratitude Journaling", "Shift focus to the positives in your life.", "5 min", "Mind & Reflection", "Happy", "/static/img/gratitude journaling.jpeg", "journal", "List three things you're grateful for today.", ""),
                ("Positive Affirmations", "Rebuild confidence through kind words.", "2 min", "Mind & Reflection", "Happy", "/static/img/positive affrimation.jpeg", "article", "", "<h3>Daily Affirmations</h3><p>I am capable of handling whatever comes my way today.</p><p>I choose to focus on what I can control.</p>"),
                ("Mindful Observation", "Focus on one object for a full minute to center yourself.", "1 min", "Mind & Reflection", "Happy", "/static/img/mindful observation.jpeg", "article", "", "<h3>Mindful Observation</h3><p>Choose an object in your room. Notice its color, texture, and how the light hits it. Stay with it for 60 seconds.</p>"),
                ("Inner Peace Scan", "A mental check-in to find where you feel most calm.", "5 min", "Mind & Reflection", "Happy", "/static/img/inner peace csan.jpeg", "journal", "Where in your body do you feel most at peace right now?", ""),
                ("Deep Breathing Exercise", "Breathe in for 4, hold for 4, exhale for 6.", "2 min", "Quick Calm", "Anxious", "/static/img/deep breathing.jpeg", "breathe", "", ""),
                ("5-4-3-2-1 Grounding", "Focus on your immediate surroundings to calm down.", "3 min", "Quick Calm", "Anxious", "/static/img/5-4-3-2-1.jpeg", "article", "", "<h3>Grounding Technique</h3><p>Name 5 things you can see, 4 things you can touch, 3 things you can hear, 2 things you can smell, and 1 thing you can taste.</p>"),
                ("Box Breathing", "A structured technique to regain emotional control.", "5 min", "Quick Calm", "Angry", "/static/img/Box Breathing.jpeg", "breathe", "", ""),
                ("Muscle Relaxation", "Tense and release muscle groups starting from your toes.", "5 min", "Quick Calm", "Anxious", "/static/img/muscles relaxation.jpeg", "article", "", "<h3>Progressive Muscle Relaxation</h3><p>Tense your toes for 5 seconds, then release. Move up to your calves, thighs, and so on.</p>"),
                ("Victory Log", "List three small things you accomplished today.", "10 min", "Reflective", "Happy", "/static/img/journaling.jpeg", "journal", "What are your three wins for today?", ""),
                ("Thought Reframing", "Turn a negative thought into a constructive one.", "10 min", "Reflective", "Sad", "/static/img/journalin2.jpeg", "journal", "Write one negative thought and try to rewrite it from a more compassionate perspective.", ""),
                ("Letter to Yourself", "Write a kind letter to your future self.", "15 min", "Reflective", "Sad", "/static/img/Daily Journaling.jpeg", "journal", "What would you like to tell yourself 6 months from now?", ""),
                ("Short Walk Challenge", "Get some fresh air and change your environment.", "10 min", "Physical Reset", "Sad", "/static/img/short walk.jpeg", "article", "", "<h3>Walking Benefits</h3><p>Even a 10-minute walk can significantly boost your mood and energy levels.</p>"),
                ("Stretching Routine", "Release physical tension softly from your body.", "5 min", "Physical Reset", "Angry", "/static/img/stretching.jpeg", "article", "", "<h3>Gentle Stretching</h3><p>Reach for the sky, then slowly touch your toes. Hold each stretch for 15 seconds.</p>"),
                ("Shoulder Rolls", "Release the weight of the day from your shoulders.", "2 min", "Physical Reset", "Anxious", "/static/img/shoulder stretch.jpeg", "article", "", "<h3>Shoulder Rolls</h3><p>Roll your shoulders back in slow circles 10 times, then forward 10 times.</p>"),
                ("Quick HIIT", "Get your heart rate up with a 5-minute burst.", "5 min", "Exercise", "Angry", "/static/img/quick HIIT.jpeg", "article", "", "<h3>Quick HIIT</h3><p>30 seconds of jumping jacks, 30 seconds of rest. Repeat 5 times.</p>"),
                ("Yoga Flow", "A simple sequence to connect breath and movement.", "15 min", "Exercise", "Sad", "/static/img/yoga flow.jpeg", "article", "", "<h3>Simple Yoga</h3><p>Try the child's pose, then move into downward dog. Breathe deeply.</p>"),
                ("Plank Challenge", "Build core strength and mental resilience.", "2 min", "Exercise", "Angry", "/static/img/plank challenge.jpeg", "article", "", "<h3>Plank</h3><p>Hold a plank position for as long as you can up to 2 minutes.</p>"),
                ("Connection Time", "Send a quick message to a friend or loved one.", "5 min", "Social", "Sad", "/static/img/message someone.jpeg", "article", "", "<h3>Social Connection</h3><p>Reaching out to someone you trust can lower stress hormones immediately.</p>"),
                ("Acts of Kindness", "Do one small thing to help someone else today.", "10 min", "Social", "Happy", "/static/img/act of kindness.jpeg", "journal", "What's one kind thing you did or could do today?", ""),
                ("Call a Friend", "A real conversation can change your entire day.", "15 min", "Social", "Sad", "/static/img/call someone.jpeg", "article", "", "<h3>Phone Call</h3><p>Hearing a familiar voice provides comfort that text messages can't match.</p>")
            ]
            cur.executemany("""
                INSERT INTO activities (title, description, duration, category, target_emotion, image_url, action_type, prompt, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, sample_activities)

    # --- USER METHODS ---

    def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        if not self.is_available(): return None
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT id, email, name, password_hash, is_admin FROM users WHERE email = %s", (email,))
            return cur.fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        if not self.is_available(): return None
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT id, email, name, is_admin FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()

    def create_user(self, email: str, name: str, password_hash: str) -> int:
        with self.get_cursor() as (cur, _):
            cur.execute("INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)", (email, name, password_hash))
            return cur.lastrowid

    def get_all_users(self) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT u.id, u.name, u.email, u.password_hash, u.is_admin, u.created_at, tc.contact_email as trusted_contact
                FROM users u
                LEFT JOIN trusted_contacts tc ON u.id = tc.user_id
                ORDER BY u.created_at DESC
            """)
            rows = cur.fetchall()
            for r in rows:
                if hasattr(r["created_at"], "isoformat"): r["created_at"] = r["created_at"].isoformat()
            return rows

    # --- JOURNAL METHODS ---

    def insert_feedback(self, **kwargs) -> int:
        user_id = kwargs.get("user_id")
        with self.get_cursor() as (cur, _):
            # Check for existing entry today (Nepal time)
            cur.execute("""
                SELECT id FROM mood_journals 
                WHERE user_id = %s 
                  AND DATE(CONVERT_TZ(created_at, @@session.time_zone, '+05:45')) = DATE(CONVERT_TZ(NOW(), @@session.time_zone, '+05:45'))
                LIMIT 1
            """, (user_id,))
            existing = cur.fetchone()

            matched_phrases_str = ",".join(kwargs.get("matched_phrases")) if kwargs.get("matched_phrases") else None
            recommendations_str = "|".join(kwargs.get("recommendations")) if kwargs.get("recommendations") else None

            if existing:
                journal_id = existing[0]
                cur.execute("""
                    UPDATE mood_journals SET
                      selected_mood = %s, selected_secondary_emotion = %s, selected_cause = %s,
                      journal_text = %s, predicted_mood = %s, predicted_emotion = %s,
                      predicted_secondary_emotion = %s, confidence = %s, is_match = %s,
                      feedback = %s, risk_level = %s, matched_phrases = %s,
                      depression_level = %s, anxiety_level = %s, depression_score = %s,
                      anxiety_score = %s, wellness_score = %s, wellness_level = %s,
                      recommendations = %s
                    WHERE id = %s
                """, (
                    kwargs.get("selected_mood"), kwargs.get("selected_secondary_emotion"), kwargs.get("selected_cause"),
                    kwargs.get("journal_text"), kwargs.get("predicted_mood"), kwargs.get("predicted_emotion"),
                    kwargs.get("predicted_secondary_emotion"), kwargs.get("confidence"), 1 if kwargs.get("is_match") else 0,
                    kwargs.get("feedback"), kwargs.get("risk_level"), matched_phrases_str,
                    kwargs.get("depression_level"), kwargs.get("anxiety_level"), kwargs.get("depression_score"),
                    kwargs.get("anxiety_score"), kwargs.get("wellness_score"), kwargs.get("wellness_level"),
                    recommendations_str, journal_id
                ))
                return journal_id
            else:
                cur.execute("""
                    INSERT INTO mood_journals (
                      user_id, selected_mood, selected_secondary_emotion, selected_cause,
                      journal_text, predicted_mood, predicted_emotion, predicted_secondary_emotion,
                      confidence, is_match, feedback, risk_level, matched_phrases,
                      depression_level, anxiety_level, depression_score, anxiety_score,
                      wellness_score, wellness_level, recommendations
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, kwargs.get("selected_mood"), kwargs.get("selected_secondary_emotion"), kwargs.get("selected_cause"),
                    kwargs.get("journal_text"), kwargs.get("predicted_mood"), kwargs.get("predicted_emotion"),
                    kwargs.get("predicted_secondary_emotion"), kwargs.get("confidence"), 1 if kwargs.get("is_match") else 0,
                    kwargs.get("feedback"), kwargs.get("risk_level"), matched_phrases_str,
                    kwargs.get("depression_level"), kwargs.get("anxiety_level"), kwargs.get("depression_score"),
                    kwargs.get("anxiety_score"), kwargs.get("wellness_score"), kwargs.get("wellness_level"),
                    recommendations_str
                ))
                return cur.lastrowid

    def update_feedback(self, journal_id: int, feedback: str) -> None:
        with self.get_cursor() as (cur, _):
            cur.execute("UPDATE mood_journals SET feedback = %s WHERE id = %s", (feedback, journal_id))

    def get_user_mood_distribution(self, user_id: int, days: int = 30) -> dict[str, int]:
        if not self.is_available(): return {}
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT CASE WHEN predicted_emotion = 'Crisis' THEN 'Crisis' ELSE selected_mood END as mood_key, COUNT(*) as count 
                FROM mood_journals WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) GROUP BY mood_key
            """, (user_id, days))
            return {r["mood_key"]: r["count"] for r in cur.fetchall()}

    def get_user_mood_history(self, user_id: int, days: int = 30) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT id, selected_mood, predicted_emotion, journal_text, created_at, is_favourite
                FROM mood_journals WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) ORDER BY created_at DESC
            """, (user_id, days))
            rows = cur.fetchall()
            for r in rows:
                if hasattr(r["created_at"], "isoformat"): r["created_at"] = r["created_at"].isoformat()
            return rows

    def toggle_favourite(self, journal_id: int) -> bool:
        with self.get_cursor() as (cur, _):
            cur.execute("SELECT is_favourite FROM mood_journals WHERE id = %s", (journal_id,))
            row = cur.fetchone()
            if not row: return False
            new_status = 1 if row[0] == 0 else 0
            cur.execute("UPDATE mood_journals SET is_favourite = %s WHERE id = %s", (new_status, journal_id))
            return bool(new_status)

    def get_filtered_history(self, user_id: int, filter_type: str) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            query = "SELECT id, selected_mood, predicted_emotion, journal_text, created_at, is_favourite FROM mood_journals WHERE user_id = %s"
            if filter_type == 'today': query += " AND DATE(created_at) = CURDATE()"
            elif filter_type == 'monthly': query += " AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            elif filter_type == 'favourites': query += " AND is_favourite = 1"
            query += " ORDER BY created_at DESC"
            cur.execute(query, [user_id])
            rows = cur.fetchall()
            for r in rows:
                if hasattr(r["created_at"], "isoformat"): r["created_at"] = r["created_at"].isoformat()
            return rows

    def get_today_journal(self, user_id: int) -> Optional[dict[str, Any]]:
        if not self.is_available(): return None
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT * FROM mood_journals WHERE user_id = %s 
                AND DATE(CONVERT_TZ(created_at, @@session.time_zone, '+05:45')) = DATE(CONVERT_TZ(NOW(), @@session.time_zone, '+05:45'))
                LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            if row and hasattr(row.get("created_at"), "isoformat"): row["created_at"] = row["created_at"].isoformat()
            return row

    # --- ACTIVITY METHODS ---

    def get_activities_by_emotion(self, target_emotion: str) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT * FROM activities WHERE target_emotion = %s LIMIT 3", (target_emotion,))
            return cur.fetchall()

    def get_all_activities(self) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT * FROM activities")
            return cur.fetchall()

    def get_activity_by_id(self, activity_id: int) -> Optional[dict[str, Any]]:
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT * FROM activities WHERE id = %s", (activity_id,))
            return cur.fetchone()

    def delete_activity(self, activity_id: int) -> bool:
        with self.get_cursor() as (cur, _):
            cur.execute("DELETE FROM activities WHERE id = %s", (activity_id,))
            return True

    def update_activity(self, activity_id: int, data: dict[str, Any]) -> bool:
        with self.get_cursor() as (cur, _):
            cur.execute("""
                UPDATE activities SET title=%s, description=%s, duration=%s, category=%s, 
                target_emotion=%s, image_url=%s, audio_url=%s, action_type=%s, prompt=%s, content=%s
                WHERE id=%s
            """, (data['title'], data['description'], data['duration'], data['category'], 
                  data['target_emotion'], data['image_url'], data.get('audio_url'), 
                  data['action_type'], data.get('prompt'), data.get('content'), activity_id))
            return True

    # --- CONTACT & STATS ---

    def get_trusted_contact(self, user_id: int) -> Optional[str]:
        if not self.is_available(): return None
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT contact_email FROM trusted_contacts WHERE user_id = %s LIMIT 1", (user_id,))
            result = cur.fetchone()
            return result["contact_email"] if result else None

    def save_trusted_contact(self, user_id: int, email: str) -> None:
        if not self.is_available(): return
        with self.get_cursor() as (cur, _):
            cur.execute("INSERT INTO trusted_contacts (user_id, contact_email) VALUES (%s, %s) ON DUPLICATE KEY UPDATE contact_email = %s", (user_id, email, email))

    def check_negative_streak(self, user_id: int, days: int = 30) -> int:
        if not self.is_available(): return 0
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT COUNT(*) as count FROM mood_journals WHERE user_id = %s AND selected_mood IN ('Bad', 'Terrible') AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (user_id, days))
            result = cur.fetchone()
            return result["count"] if result else 0

    def get_admin_stats(self) -> dict[str, Any]:
        if not self.is_available(): return {}
        with self.get_cursor() as (cur, _):
            cur.execute("SELECT COUNT(*) FROM users")
            u = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM mood_journals")
            j = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM mood_journals WHERE risk_level != 'Low'")
            r = cur.fetchone()[0]
            return {"total_users": u, "total_journals": j, "total_risky": r}

    def get_all_journals_admin(self) -> list[dict[str, Any]]:
        if not self.is_available(): return []
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT j.*, u.name as user_name, u.email as user_email
                FROM mood_journals j JOIN users u ON j.user_id = u.id
                ORDER BY j.created_at DESC LIMIT 100
            """)
            rows = cur.fetchall()
            for r in rows:
                if hasattr(r["created_at"], "isoformat"): r["created_at"] = r["created_at"].isoformat()
            return rows


    def get_setting(self, key: str) -> Optional[str]:
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("SELECT `value` FROM system_settings WHERE `key` = %s", (key,))
            res = cur.fetchone()
            return res["value"] if res else None

    def update_setting(self, key: str, value: str) -> None:
        with self.get_cursor() as (cur, _):
            cur.execute("UPDATE system_settings SET `value` = %s WHERE `key` = %s", (value, key))

    def get_activity_logs(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_cursor(dictionary=True) as (cur, _):
            cur.execute("""
                SELECT l.content, l.created_at, a.title as activity_title 
                FROM activity_logs l
                JOIN activities a ON l.activity_id = a.id
                WHERE l.user_id = %s
                ORDER BY l.created_at DESC
            """, (user_id,))
            return cur.fetchall()


# --- SINGLETON INSTANCE ---
_db_manager = DatabaseManager()

def get_db_manager():
    return _db_manager


# --- BACKWARD COMPATIBILITY WRAPPERS ---
# These ensure app.py continues to work while we refactor its routes.

def db_available(): return _db_manager.is_available()
def connect(): return _db_manager.connect()
def init_db(): return _db_manager.init_db()

def get_user_by_email(email): return _db_manager.get_user_by_email(email)
def create_user(e, n, p): return _db_manager.create_user(e, n, p)
def get_all_users(): return _db_manager.get_all_users()

def insert_feedback(**kwargs): return _db_manager.insert_feedback(**kwargs)
def update_feedback(jid, f): return _db_manager.update_feedback(jid, f)
def get_user_mood_distribution(uid, d=30): return _db_manager.get_user_mood_distribution(uid, d)
def get_user_mood_history(uid, d=30): return _db_manager.get_user_mood_history(uid, d)
def toggle_favourite(jid): return _db_manager.toggle_favourite(jid)
def get_filtered_history(uid, f): return _db_manager.get_filtered_history(uid, f)
def get_today_journal(uid): return _db_manager.get_today_journal(uid)

def get_activities_by_emotion(e): return _db_manager.get_activities_by_emotion(e)
def get_all_activities(): return _db_manager.get_all_activities()
def get_activity_by_id(aid): return _db_manager.get_activity_by_id(aid)
def delete_activity(aid): return _db_manager.delete_activity(aid)
def update_activity(aid, d): return _db_manager.update_activity(aid, d)

def get_activity_logs(uid): return _db_manager.get_activity_logs(uid)

def get_trusted_contact(uid): return _db_manager.get_trusted_contact(uid)
def save_trusted_contact(uid, e): return _db_manager.save_trusted_contact(uid, e)
def check_negative_streak(uid, d=30): return _db_manager.check_negative_streak(uid, d)
def get_admin_stats(): return _db_manager.get_admin_stats()
def get_all_journals_admin(): return _db_manager.get_all_journals_admin()
