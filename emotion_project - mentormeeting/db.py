from __future__ import annotations

import os
from typing import Any, Optional

import mysql.connector
from mysql.connector import Error


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
        "password": _env("MYSQL_PASSWORD"),
        "database": _env("MYSQL_DATABASE"),
    }


def db_available() -> bool:
    cfg = get_db_config()
    # Need user/password/database to store feedback
    return bool(cfg["user"] and cfg["password"] and cfg["database"])


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
        
        # Create users table if needed, though mostly using hardcoded session right now
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trusted Contacts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trusted_contacts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNIQUE,
                contact_email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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
) -> None:
    conn = connect()
    try:
        cur = conn.cursor()
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
            SELECT id, selected_mood, predicted_emotion, journal_text, created_at 
            FROM mood_journals 
            WHERE user_id = %s 
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY created_at ASC
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

