from __future__ import annotations
from typing import Any, Optional
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db_manager
from src.inference import MoodAnalyzer


class AuthService:
    """Handles user authentication and session management."""
    
    def __init__(self, db_manager):
        self.db = db_manager

    def login(self, email: str, password: str) -> tuple[bool, Optional[str]]:
        user = self.db.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["name"].split()[0] if user["name"] else "there"
            session["is_admin"] = bool(user.get("is_admin"))
            return True, None
        return False, "Invalid email or password."

    def register(self, first_name: str, last_name: str, email: str, password: str) -> tuple[bool, Optional[str]]:
        if self.db.get_user_by_email(email):
            return False, "Email already registered. Please log in."
        
        full_name = f"{first_name} {last_name}".strip()
        pwd_hash = generate_password_hash(password)
        user_id = self.db.create_user(email, full_name, pwd_hash)
        
        session["logged_in"] = True
        session["user_id"] = user_id
        session["username"] = first_name
        return True, None

    def logout(self):
        session.clear()

    @property
    def current_user_id(self) -> Optional[int]:
        return session.get("user_id")

    @property
    def is_logged_in(self) -> bool:
        return bool(session.get("logged_in"))

    @property
    def is_admin(self) -> bool:
        return bool(session.get("is_admin"))


class JournalService:
    """Handles journal analysis, history, and reporting."""

    def __init__(self, db_manager, analyzer: MoodAnalyzer, email_service=None):
        self.db = db_manager
        self.analyzer = analyzer
        self.email_service = email_service

    def analyze_and_save(self, user_id: Optional[int], payload: dict[str, Any]) -> dict[str, Any]:
        journal_text = payload.get("journalText")
        selected_mood = payload.get("selectedMood")
        
        # 1. Run ML Analysis
        result = self.analyzer.analyze_journal(str(journal_text), str(selected_mood))
        
        # 2. Logic for frontend match & tagging
        is_match = bool(self._check_match(result.get("predicted_mood"), selected_mood))
        target_tag = self._get_target_tag(result.get("predicted_mood"), result.get("predicted_emotion"))
        
        # 3. Get recommendations based on tag
        recommendations = self.db.get_activities_by_emotion(target_tag) if target_tag else []

        # 4. Save to DB
        journal_id = self.db.insert_feedback(
            user_id=user_id,
            selected_mood=str(selected_mood),
            selected_secondary_emotion=payload.get("selectedSecondaryEmotion"),
            selected_cause=payload.get("selectedCause"),
            journal_text=str(journal_text),
            predicted_mood=str(result.get("predicted_mood")),
            predicted_emotion=str(result.get("predicted_emotion")),
            predicted_secondary_emotion=str(result.get("secondary_emotion")),
            confidence=float(result.get("confidence") or 0),
            is_match=is_match,
            risk_level=str(result.get("risk_level") or "Low"),
            matched_phrases=result.get("matched_phrases") or [],
            depression_level=str(result.get("depression_level") or "None"),
            anxiety_level=str(result.get("anxiety_level") or "None"),
            depression_score=int(result.get("depression_score") or 0),
            anxiety_score=int(result.get("anxiety_score") or 0),
            wellness_score=int(result.get("wellness_score") or 100),
            wellness_level=str(result.get("wellness_level") or "Healthy"),
            recommendations=result.get("recommendations") or [],
        )

        # 5. Automated Alert Check
        if user_id and self.email_service:
            negative_days = self.db.check_negative_streak(user_id, days=30)
            if negative_days >= 15:
                contact_email = self.db.get_trusted_contact(user_id)
                if contact_email:
                    # Check if we already alerted recently (optional but good)
                    # For simplicity, we just trigger it
                    user_data = self.db.get_user_by_id(user_id)
                    user_name = user_data["name"] if user_data else "A user"
                    self.email_service.send_trusted_contact_alert(user_name, contact_email)

        return {
            "ok": True,
            "analysis": result,
            "isMatch": is_match,
            "confidencePercent": float(result.get("confidence") * 100.0) if result.get("confidence") else None,
            "meta": {
                "selectedSecondaryEmotion": payload.get("selectedSecondaryEmotion"),
                "selectedCause": payload.get("selectedCause"),
                "journalId": journal_id
            },
            "recommendations": recommendations,
        }

    def _check_match(self, predicted, selected):
        GROUPS = [{"Awesome", "Good"}, {"Fine"}, {"Bad", "Terrible"}]
        for group in GROUPS:
            if predicted in group and selected in group: return True
        return predicted == selected

    def _get_target_tag(self, predicted_mood, predicted_emotion):
        if predicted_emotion in ["Sadness", "Sad", "Disgusted", "Grief"]: return "Sad"
        if predicted_emotion in ["Anger", "Angry", "Annoyed", "Frustrated"]: return "Angry"
        if predicted_emotion in ["Fear", "Anxious", "Scared", "Panic"]: return "Anxious"
        if predicted_emotion in ["Joy", "Happy", "Joyful", "Love", "Relieved", "Grateful", "Surprise"] or predicted_mood in ["Awesome", "Good"]:
            return "Happy"
        if predicted_mood in ["Bad", "Terrible"]: return "Sad"
        return ""

    def get_dashboard_data(self, user_id: int):
        return {
            "username": session.get("username", "there"),
            "today_entry": self.db.get_today_journal(user_id)
        }

    def get_reports_data(self, user_id: int, days: int):
        return {
            "distribution": self.db.get_user_mood_distribution(user_id, days),
            "history": self.db.get_user_mood_history(user_id, days),
            "calendar_history": self.db.get_user_mood_history(user_id, 365),
            "trusted_contact": self.db.get_trusted_contact(user_id),
            "current_days": days
        }


class ActivityService:
    """Handles activity management and CRUD operations."""

    def __init__(self, db_manager):
        self.db = db_manager

    def get_categorized_activities(self):
        activities = self.db.get_all_activities()
        categories = {}
        for act in activities:
            cat = act.get("category", "Other")
            if cat not in categories: categories[cat] = []
            categories[cat].append(act)
        return {"categories": categories}

    def save_log(self, user_id, activity_id, content):
        with self.db.get_cursor() as (cur, _):
            cur.execute("INSERT INTO activity_logs (user_id, activity_id, content) VALUES (%s, %s, %s)", (user_id, activity_id, content))
        return {"ok": True}

    def get_logs(self, user_id):
        return {"ok": True, "logs": self.db.get_activity_logs(user_id)}

class AdminService:
    """Handles admin-only operations."""
    
    def __init__(self, db_manager):
        self.db = db_manager

    def get_stats(self):
        return self.db.get_admin_stats()

    def get_users(self):
        return {"users": self.db.get_all_users()}

    def get_journals(self):
        return {"journals": self.db.get_all_journals_admin()}

    def delete_user(self, current_user_id, target_user_id):
        if current_user_id == target_user_id:
            return False, "You cannot delete your own account."
        # Logic to delete user
        with self.db.get_cursor() as (cur, _):
            cur.execute("DELETE FROM users WHERE id = %s", (target_user_id,))
        return True, None

    def update_user(self, user_id, data):
        with self.db.get_cursor() as (cur, _):
            cur.execute("""
                UPDATE users SET name = %s, email = %s, is_admin = %s WHERE id = %s
            """, (data.get("name"), data.get("email"), 1 if data.get("is_admin") else 0, user_id))
        return {"ok": True}

    def create_activity(self, data):
        title = data.get("title")
        category = data.get("category")
        if not title or not category:
            return False, "Title and Category are required"
        
        with self.db.get_cursor() as (cur, _):
            cur.execute("""
                INSERT INTO activities (title, description, duration, category, icon, image_url, audio_url, target_emotion, action_type, prompt, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                title, data.get("description"), data.get("duration"), category, "sparkles",
                data.get("image_url"), data.get("audio_url"), data.get("target_emotion", "Happy"),
                data.get("action_type", "article"), data.get("prompt"), data.get("content")
            ))
        return True, None
