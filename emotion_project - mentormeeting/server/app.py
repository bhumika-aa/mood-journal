from __future__ import annotations
import os
import sys
from dotenv import load_dotenv

# LOAD ENV FIRST
load_dotenv()

from pathlib import Path
from typing import Any
import nltk
from flask import Flask, jsonify, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

# Import our components
from db import get_db_manager
from src.inference import MoodAnalyzer
from src.services import AuthService, JournalService, ActivityService, AdminService
from src.email_service import EmailService

# Initialize Singleton Managers and Services
db_manager = get_db_manager()
mood_analyzer = MoodAnalyzer()
email_service = EmailService(db_manager)

auth_service = AuthService(db_manager)
journal_service = JournalService(db_manager, mood_analyzer, email_service)
activity_service = ActivityService(db_manager)
admin_service = AdminService(db_manager)

# Path to the frontend directory
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='/static')
app.config["JSON_SORT_KEYS"] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-change-me")

# --- ROUTES ---

@app.route("/")
def home():
    if auth_service.is_logged_in:
        return redirect("/dashboard")
    return app.send_static_file("landing.html")

@app.route("/dashboard")
def dashboard():
    if not auth_service.is_logged_in:
        return redirect("/")
    return app.send_static_file("index.html")

@app.get("/api/user_info")
def api_user_info():
    if not auth_service.is_logged_in:
        return jsonify({"logged_in": False}), 401
    user = db_manager.get_user_by_id(auth_service.current_user_id)
    return jsonify({
        "logged_in": True,
        "user_id": auth_service.current_user_id,
        "username": user["name"] if user else "User",
        "is_admin": user.get("is_admin", False) if user else False
    })

@app.post("/api/login")
def api_login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    
    success, user_or_err = auth_service.login(email, password)
    if success:
        return jsonify({"ok": True, "user": user_or_err})
    return jsonify({"ok": False, "error": user_or_err}), 401

@app.post("/api/logout")
def api_logout():
    auth_service.logout()
    return jsonify({"ok": True})

@app.get("/api/dashboard_data")
def api_dashboard_data():
    if not auth_service.is_logged_in:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(journal_service.get_dashboard_data(auth_service.current_user_id))

@app.post("/api/analyze")
def api_analyze():
    if not auth_service.is_logged_in:
        return jsonify({"error": "Not logged in"}), 401
        
    payload = request.get_json(silent=True) or {}
    
    try:
        result = journal_service.analyze_and_save(auth_service.current_user_id, payload)
        return jsonify(result)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return jsonify({"error": str(exc)}), 500

@app.get("/api/activities_data")
def api_activities_data():
    if not auth_service.is_logged_in:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(activity_service.get_categorized_activities())

@app.get("/admin")
def admin_panel():
    user = db_manager.get_user_by_id(auth_service.current_user_id)
    if not user or not user.get("is_admin"):
        return redirect("/")
    return app.send_static_file("admin.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
