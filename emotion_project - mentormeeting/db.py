from __future__ import annotations

import os
from typing import Any, Optional

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val


def get_db_config() -> dict[str, Any]:
    return {
        "host": _env("MYSQL_HOST", "127.0.0.1"),
        "port": int(_env("MYSQL_PORT", "3306")),
        "user": _env("MYSQL_USER"),
        "password": _env("MYSQL_PASSWORD", ""),
        "database": _env("MYSQL_DATABASE"),
    }


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    if not db_available():
        return None
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, email, name, password_hash, is_admin FROM users WHERE email = %s", (email,))
        return cur.fetchone()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def create_user(email: str, name: str, password_hash: str) -> int:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)",
            (email, name, password_hash)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        try:
            conn.close()
        except Exception:
            pass



def db_available() -> bool:
    cfg = get_db_config()
    # Need user and database. Password can be empty in some local setups.
    return bool(cfg["user"] and cfg["database"])


def connect():
    cfg = get_db_config()
    if not db_available():
        raise RuntimeError(
            "MySQL is not configured. Set MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE."
        )
    return mysql.connector.connect(**cfg)


def init_db() -> None:
    if not db_available():
        return
    conn = connect()
    try:
        cur = conn.cursor()
        
        # Create users table if needed
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

        # Ensure is_admin exists
        cur.execute("SHOW COLUMNS FROM users LIKE 'is_admin'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) DEFAULT 0")

        # Ensure password_hash exists (for older database versions)
        cur.execute("SHOW COLUMNS FROM users LIKE 'password_hash'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")

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

        # Ensure is_favourite exists
        cur.execute("SHOW COLUMNS FROM mood_journals LIKE 'is_favourite'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE mood_journals ADD COLUMN is_favourite TINYINT(1) DEFAULT 0")

        # Ensure depression/anxiety/wellness columns exist
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

        # Ensure columns exist if table already existed
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

        # Activity Logs (to save user entries)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                activity_id INT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed Activities
        cur.execute("SELECT COUNT(*) FROM activities")
        cur.fetchone() 
        
        cur.execute("TRUNCATE TABLE activities")

        sample_activities = [
            # Mind & Reflection
            ("Gratitude Journaling", "Shift focus to the positives in your life.", "5 min", "Mind & Reflection", "Happy", "/static/img/gratitude journaling.jpeg", "journal", "List three things you're grateful for today.", ""),
            ("Positive Affirmations", "Rebuild confidence through kind words.", "2 min", "Mind & Reflection", "Happy", "/static/img/positive affrimation.jpeg", "article", "", "<h3>Daily Affirmations</h3><p>I am capable of handling whatever comes my way today.</p><p>I choose to focus on what I can control.</p>"),
            ("Mindful Observation", "Focus on one object for a full minute to center yourself.", "1 min", "Mind & Reflection", "Happy", "/static/img/mindful observation.jpeg", "article", "", "<h3>Mindful Observation</h3><p>Choose an object in your room. Notice its color, texture, and how the light hits it. Stay with it for 60 seconds.</p>"),
            ("Inner Peace Scan", "A mental check-in to find where you feel most calm.", "5 min", "Mind & Reflection", "Happy", "/static/img/inner peace csan.jpeg", "journal", "Where in your body do you feel most at peace right now?", ""),

            # Quick Calm
            ("Deep Breathing Exercise", "Breathe in for 4, hold for 4, exhale for 6.", "2 min", "Quick Calm", "Anxious", "/static/img/deep breathing.jpeg", "breathe", "", ""),
            ("5-4-3-2-1 Grounding", "Focus on your immediate surroundings to calm down.", "3 min", "Quick Calm", "Anxious", "/static/img/5-4-3-2-1.jpeg", "article", "", "<h3>Grounding Technique</h3><p>Name 5 things you can see, 4 things you can touch, 3 things you can hear, 2 things you can smell, and 1 thing you can taste.</p>"),
            ("Box Breathing", "A structured technique to regain emotional control.", "5 min", "Quick Calm", "Angry", "/static/img/Box Breathing.jpeg", "breathe", "", ""),
            ("Muscle Relaxation", "Tense and release muscle groups starting from your toes.", "5 min", "Quick Calm", "Anxious", "/static/img/muscles relaxation.jpeg", "article", "", "<h3>Progressive Muscle Relaxation</h3><p>Tense your toes for 5 seconds, then release. Move up to your calves, thighs, and so on.</p>"),

            # Reflective
            ("Victory Log", "List three small things you accomplished today.", "10 min", "Reflective", "Happy", "/static/img/journaling.jpeg", "journal", "What are your three wins for today?", ""),
            ("Thought Reframing", "Turn a negative thought into a constructive one.", "10 min", "Reflective", "Sad", "/static/img/journalin2.jpeg", "journal", "Write one negative thought and try to rewrite it from a more compassionate perspective.", ""),
            ("Letter to Yourself", "Write a kind letter to your future self.", "15 min", "Reflective", "Sad", "/static/img/Daily Journaling.jpeg", "journal", "What would you like to tell yourself 6 months from now?", ""),

            # Physical Reset
            ("Short Walk Challenge", "Get some fresh air and change your environment.", "10 min", "Physical Reset", "Sad", "/static/img/short walk.jpeg", "article", "", "<h3>Walking Benefits</h3><p>Even a 10-minute walk can significantly boost your mood and energy levels.</p>"),
            ("Stretching Routine", "Release physical tension softly from your body.", "5 min", "Physical Reset", "Angry", "/static/img/stretching.jpeg", "article", "", "<h3>Gentle Stretching</h3><p>Reach for the sky, then slowly touch your toes. Hold each stretch for 15 seconds.</p>"),
            ("Shoulder Rolls", "Release the weight of the day from your shoulders.", "2 min", "Physical Reset", "Anxious", "/static/img/shoulder stretch.jpeg", "article", "", "<h3>Shoulder Rolls</h3><p>Roll your shoulders back in slow circles 10 times, then forward 10 times.</p>"),

            # Exercise
            ("Quick HIIT", "Get your heart rate up with a 5-minute burst.", "5 min", "Exercise", "Angry", "/static/img/quick HIIT.jpeg", "article", "", "<h3>Quick HIIT</h3><p>30 seconds of jumping jacks, 30 seconds of rest. Repeat 5 times.</p>"),
            ("Yoga Flow", "A simple sequence to connect breath and movement.", "15 min", "Exercise", "Sad", "/static/img/yoga flow.jpeg", "article", "", "<h3>Simple Yoga</h3><p>Try the child's pose, then move into downward dog. Breathe deeply.</p>"),
            ("Plank Challenge", "Build core strength and mental resilience.", "2 min", "Exercise", "Angry", "/static/img/plank challenge.jpeg", "article", "", "<h3>Plank</h3><p>Hold a plank position for as long as you can up to 2 minutes.</p>"),

            # Social
            ("Connection Time", "Send a quick message to a friend or loved one.", "5 min", "Social", "Sad", "/static/img/message someone.jpeg", "article", "", "<h3>Social Connection</h3><p>Reaching out to someone you trust can lower stress hormones immediately.</p>"),
            ("Acts of Kindness", "Do one small thing to help someone else today.", "10 min", "Social", "Happy", "/static/img/act of kindness.jpeg", "journal", "What's one kind thing you did or could do today?", ""),
            ("Call a Friend", "A real conversation can change your entire day.", "15 min", "Social", "Sad", "/static/img/call someone.jpeg", "article", "", "<h3>Phone Call</h3><p>Hearing a familiar voice provides comfort that text messages can't match.</p>")
        ]
        cur.executemany("""
            INSERT INTO activities (title, description, duration, category, target_emotion, image_url, action_type, prompt, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, sample_activities)

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def insert_feedback(
    *,
    user_id: Optional[int] = None,
    selected_mood: str,
    selected_secondary_emotion: Optional[str],
    selected_cause: Optional[str],
    journal_text: str,
    predicted_mood: Optional[str],
    predicted_emotion: Optional[str],
    predicted_secondary_emotion: Optional[str],
    confidence: Optional[float],
    is_match: bool,
    feedback: Optional[str],
    risk_level: Optional[str],
    matched_phrases: Optional[list[str]],
    depression_level: Optional[str] = None,
    anxiety_level: Optional[str] = None,
    depression_score: Optional[int] = None,
    anxiety_score: Optional[int] = None,
    wellness_score: Optional[int] = None,
    wellness_level: Optional[str] = None,
    recommendations: Optional[list[str]] = None,
) -> int:
    conn = connect()
    try:
        cur = conn.cursor()
        
        # Nepal Timezone Check (UTC+5:45)
        # We check if an entry exists for the current user on the same calendar day in Nepal.
        cur.execute("""
            SELECT id FROM mood_journals 
            WHERE user_id = %s 
              AND DATE(CONVERT_TZ(created_at, @@session.time_zone, '+05:45')) = DATE(CONVERT_TZ(NOW(), @@session.time_zone, '+05:45'))
            LIMIT 1
        """, (user_id,))
        existing = cur.fetchone()

        if existing:
            # UPDATE existing entry for today
            journal_id = existing[0]
            cur.execute(
                """
                UPDATE mood_journals SET
                  selected_mood = %s,
                  selected_secondary_emotion = %s,
                  selected_cause = %s,
                  journal_text = %s,
                  predicted_mood = %s,
                  predicted_emotion = %s,
                  predicted_secondary_emotion = %s,
                  confidence = %s,
                  is_match = %s,
                  feedback = %s,
                  risk_level = %s,
                  matched_phrases = %s,
                  depression_level = %s,
                  anxiety_level = %s,
                  depression_score = %s,
                  anxiety_score = %s,
                  wellness_score = %s,
                  wellness_level = %s,
                  recommendations = %s
                WHERE id = %s
                """,
                (
                    selected_mood,
                    selected_secondary_emotion,
                    selected_cause,
                    journal_text,
                    predicted_mood,
                    predicted_emotion,
                    predicted_secondary_emotion,
                    confidence,
                    1 if is_match else 0,
                    feedback,
                    risk_level,
                    ",".join(matched_phrases) if matched_phrases else None,
                    depression_level,
                    anxiety_level,
                    depression_score,
                    anxiety_score,
                    wellness_score,
                    wellness_level,
                    "|".join(recommendations) if recommendations else None,
                    journal_id
                )
            )
            conn.commit()
            return journal_id
        else:
            # INSERT new entry
            cur.execute(
                """
                INSERT INTO mood_journals (
                  user_id,
                  selected_mood,
                  selected_secondary_emotion,
                  selected_cause,
                  journal_text,
                  predicted_mood,
                  predicted_emotion,
                  predicted_secondary_emotion,
                  confidence,
                  is_match,
                  feedback,
                  risk_level,
                  matched_phrases,
                  depression_level,
                  anxiety_level,
                  depression_score,
                  anxiety_score,
                  wellness_score,
                  wellness_level,
                  recommendations
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    selected_mood,
                    selected_secondary_emotion,
                    selected_cause,
                    journal_text,
                    predicted_mood,
                    predicted_emotion,
                    predicted_secondary_emotion,
                    confidence,
                    1 if is_match else 0,
                    feedback,
                    risk_level,
                    ",".join(matched_phrases) if matched_phrases else None,
                    depression_level,
                    anxiety_level,
                    depression_score,
                    anxiety_score,
                    wellness_score,
                    wellness_level,
                    "|".join(recommendations) if recommendations else None,
                ),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        try:
            conn.close()
        except Exception:
            pass


def update_feedback(journal_id: int, feedback: str) -> None:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE mood_journals SET feedback = %s WHERE id = %s",
            (feedback, journal_id)
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_activities_by_emotion(target_emotion: str) -> list[dict[str, Any]]:
    if not db_available():
        return []
    
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, title, description, duration, category, icon, image_url, audio_url, action_type, prompt, content FROM activities WHERE target_emotion = %s LIMIT 3",
            (target_emotion,)
        )
        return cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_all_activities() -> list[dict[str, Any]]:
    if not db_available():
        return []
    
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, title, description, duration, category, target_emotion, icon, image_url, audio_url, action_type, prompt, content FROM activities")
        return cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass

def get_activity_by_id(activity_id: int) -> Optional[dict[str, Any]]:
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM activities WHERE id = %s", (activity_id,))
        return cur.fetchone()
    finally:
        conn.close()

def delete_activity(activity_id: int) -> bool:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM activities WHERE id = %s", (activity_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting activity: {e}")
        return False
    finally:
        conn.close()

def update_activity(activity_id: int, data: dict[str, Any]) -> bool:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE activities 
            SET title=%s, description=%s, duration=%s, category=%s, 
                target_emotion=%s, image_url=%s, audio_url=%s, 
                action_type=%s, prompt=%s, content=%s
            WHERE id=%s
        """, (
            data['title'], data['description'], data['duration'], 
            data['category'], data['target_emotion'], data['image_url'], 
            data.get('audio_url'), data['action_type'], data.get('prompt'), 
            data.get('content'), activity_id
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating activity: {e}")
        return False
    finally:
        conn.close()


def get_user_mood_distribution(user_id: int, days: int = 30) -> dict[str, int]:
    if not db_available():
        return {}
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                CASE WHEN predicted_emotion = 'Crisis' THEN 'Crisis' ELSE selected_mood END as mood_key,
                COUNT(*) as count 
            FROM mood_journals 
            WHERE user_id = %s 
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY mood_key
        """, (user_id, days))
        results = cur.fetchall()
        return {r["mood_key"]: r["count"] for r in results}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_user_mood_history(user_id: int, days: int = 30) -> list[dict[str, Any]]:
    if not db_available():
        return []
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, selected_mood, predicted_emotion, journal_text, created_at, is_favourite
            FROM mood_journals 
            WHERE user_id = %s 
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY created_at DESC
        """, (user_id, days))
        # Ensure created_at is converted to string for JSON serialization
        rows = cur.fetchall()
        for r in rows:
            if hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


def toggle_favourite(journal_id: int) -> bool:
    """Toggles the is_favourite status and returns the new status."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_favourite FROM mood_journals WHERE id = %s", (journal_id,))
        row = cur.fetchone()
        if not row:
            return False
        
        new_status = 1 if row[0] == 0 else 0
        cur.execute("UPDATE mood_journals SET is_favourite = %s WHERE id = %s", (new_status, journal_id))
        conn.commit()
        return bool(new_status)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_filtered_history(user_id: int, filter_type: str) -> list[dict[str, Any]]:
    """filter_type: 'today', 'monthly', 'favourites'"""
    if not db_available():
        return []
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        query = "SELECT id, selected_mood, predicted_emotion, journal_text, created_at, is_favourite FROM mood_journals WHERE user_id = %s"
        params = [user_id]
        
        if filter_type == 'today':
            query += " AND DATE(created_at) = CURDATE()"
        elif filter_type == 'monthly':
            query += " AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif filter_type == 'favourites':
            query += " AND is_favourite = 1"
            
        query += " ORDER BY created_at DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        for r in rows:
            if hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass



def get_today_journal(user_id: int) -> Optional[dict[str, Any]]:
    if not db_available():
        return None
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT * FROM mood_journals 
            WHERE user_id = %s 
              AND DATE(CONVERT_TZ(created_at, @@session.time_zone, '+05:45')) = DATE(CONVERT_TZ(NOW(), @@session.time_zone, '+05:45'))
            LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        if row and hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = row["created_at"].isoformat()
        return row
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_trusted_contact(user_id: int) -> Optional[str]:
    if not db_available():
        return None
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT contact_email FROM trusted_contacts WHERE user_id = %s LIMIT 1", (user_id,))
        result = cur.fetchone()
        return result["contact_email"] if result else None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_trusted_contact(user_id: int, email: str) -> None:
    if not db_available():
        return
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trusted_contacts (user_id, contact_email) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE contact_email = %s
        """, (user_id, email, email))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def check_negative_streak(user_id: int, days: int = 30) -> int:
    """Returns number of negative logs in the last X days"""
    if not db_available():
        return 0
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM mood_journals 
            WHERE user_id = %s 
              AND selected_mood IN ('Bad', 'Terrible')
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (user_id, days))
        result = cur.fetchone()
        return result["count"] if result else 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_all_users() -> list[dict[str, Any]]:
    if not db_available():
        return []
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email, password_hash, is_admin, created_at FROM users ORDER BY created_at DESC")
        rows = cur.fetchall()
        for r in rows:
            if hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        conn.close()

def get_all_journals_admin() -> list[dict[str, Any]]:
    if not db_available():
        return []
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT j.*, u.name as user_name, u.email as user_email
            FROM mood_journals j
            JOIN users u ON j.user_id = u.id
            ORDER BY j.created_at DESC
            LIMIT 100
        """)
        rows = cur.fetchall()
        for r in rows:
            if hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        conn.close()

def get_admin_stats() -> dict[str, Any]:
    if not db_available():
        return {}
    conn = connect()
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM mood_journals")
        total_journals = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM mood_journals WHERE risk_level != 'Low'")
        total_risky = cur.fetchone()[0]
        
        return {
            "total_users": total_users,
            "total_journals": total_journals,
            "total_risky": total_risky
        }
    finally:
        conn.close()
