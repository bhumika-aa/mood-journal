from __future__ import annotations

import os
from typing import Any, Optional

import mysql.connector
from mysql.connector import Error
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
        cur.execute("SELECT id, email, name, password_hash FROM users WHERE email = %s", (email,))
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
                icon VARCHAR(50)
            )
        """)

        # Seed Activities (Wiping and re-seeding with the EXACT ones from activities.html)
        cur.execute("SELECT COUNT(*) FROM activities")
        cur.fetchone() # Clear the result buffer
        
        cur.execute("TRUNCATE TABLE activities")

        sample_activities = [
            # Happy / Positive
            ("Gratitude Journaling", "Shift focus to the positives in your life.", "5 min", "Mind & Reflection", "Happy", ""),
            ("Positive Affirmations", "Rebuild confidence through kind words.", "2 min", "Mind & Reflection", "Happy", ""),
            ("Victory Log", "List three small things you accomplished today.", "10 min", "Reflective", "Happy", ""),
            
            # Anxious / Stress
            ("Deep Breathing Exercise", "Breathe in for 4, hold for 4, exhale for 6.", "2 min", "Quick Calm", "Anxious", ""),
            ("5-4-3-2-1 Grounding", "Focus on your immediate surroundings to calm down.", "3 min", "Quick Calm", "Anxious", ""),
            ("Close Your Eyes", "Rest your eyes and relax your facial muscles.", "1 min", "Quick Calm", "Anxious", ""),
            ("How To Deal With Stress", "Read actionable tips for managing daily life stress.", "Article", "Learn & Heal", "Anxious", ""),
            
            # Sad / Low
            ("Write Your Feelings", "A safe space to untangle your heavy thoughts.", "5 min", "Mind & Reflection", "Sad", ""),
            ("Short Walk Challenge", "Get some fresh air and change your environment.", "10 min", "Physical Reset", "Sad", ""),
            ("Nature Walk", "A short walk outside to refresh your perspective.", "15 min", "Exercise", "Sad", ""),
            ("Connection Time", "Send a quick message to a friend or loved one.", "5 min", "Social", "Sad", ""),
            
            # Angry / Frustrated
            ("Stretching Routine", "Release physical tension softly from your body.", "5 min", "Physical Reset", "Angry", ""),
            ("Box Breathing", "A structured technique to regain emotional control.", "5 min", "Mindfulness", "Angry", ""),
            ("Stress Release", "Try a quick physical activity to release heat.", "10 min", "Physical", "Angry", "")
        ]
        cur.executemany("""
            INSERT INTO activities (title, description, duration, category, target_emotion, icon)
            VALUES (%s, %s, %s, %s, %s, %s)
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
                  matched_phrases = %s
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
                  matched_phrases
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            "SELECT id, title, description, duration, category, icon FROM activities WHERE target_emotion = %s LIMIT 3",
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
        cur.execute("SELECT id, title, description, duration, category, target_emotion, icon FROM activities")
        return cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_user_mood_distribution(user_id: int, days: int = 30) -> dict[str, int]:
    if not db_available():
        return {}
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT selected_mood, COUNT(*) as count 
            FROM mood_journals 
            WHERE user_id = %s 
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY selected_mood
        """, (user_id, days))
        results = cur.fetchall()
        return {r["selected_mood"]: r["count"] for r in results}
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
        return cur.fetchone()
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
