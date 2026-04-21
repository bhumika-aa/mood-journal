from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
from typing import Any

import nltk
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    init_db, insert_feedback, db_available, 
    get_activities_by_emotion, get_all_activities,
    get_user_mood_distribution, get_user_mood_history,
    save_trusted_contact, get_trusted_contact, check_negative_streak,
    get_user_by_email, create_user, update_feedback,
    get_filtered_history, toggle_favourite, get_today_journal
)


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"


def _ensure_nltk_stopwords() -> None:
    """
    `src/preprocess.py` loads stopwords at import-time, so we ensure they exist
    before importing anything from `src/`.
    """
    try:
        from nltk.corpus import stopwords  # noqa: WPS433

        stopwords.words("english")
    except LookupError:
        nltk.download("stopwords")


def load_analyze_journal():
    """
    Import `src/inference.py` without changing your ML code.

    Your `src/inference.py` uses relative paths (e.g. "../saved_model/..."),
    so we temporarily set the working directory to `src/` for the import.
    """
    _ensure_nltk_stopwords()

    # Make sure `from crisis_detector import ...` works.
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    old_cwd = os.getcwd()
    try:
        os.chdir(str(SRC_DIR))
        import inference as inference_module  # type: ignore  # noqa: WPS433

        return inference_module.analyze_journal
    finally:
        os.chdir(old_cwd)


ANALYZE_JOURNAL = load_analyze_journal()


app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.secret_key = "super_secret_mock_key"  # For session mocking


@app.get("/")
def landing():
    # If already logged in, maybe redirect to dashboard, but landing is fine to view.
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.get("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    user_id = session.get("user_id")
    username = session.get("username", "there")
    
    # Check if user already journaled today (Nepal Time)
    today_entry = get_today_journal(user_id) if user_id else None
    
    return render_template("index.html", username=username, today_entry=today_entry)


@app.get("/activities")
def activities_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    activities = get_all_activities()
    categories: dict[str, list[dict[str, Any]]] = {}
    for act in activities:
        cat = act.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(act)
        
    return render_template("activities.html", categories=categories)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            flash("Please provide both email and password.", "error")
            return render_template("auth.html", mode="login")
            
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["name"].split()[0] if user["name"] else "there"
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "error")
            
    return render_template("auth.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not (first_name and last_name and email and password):
            flash("All fields are required.", "error")
            return render_template("auth.html", mode="register")
            
        if get_user_by_email(email):
            flash("Email already registered. Please log in.", "error")
            return render_template("auth.html", mode="register")
            
        full_name = f"{first_name} {last_name}".strip()
        pwd_hash = generate_password_hash(password)
        
        user_id = create_user(email, full_name, pwd_hash)
        
        session["logged_in"] = True
        session["user_id"] = user_id
        session["username"] = first_name
        return redirect(url_for("dashboard"))
        
    return render_template("auth.html", mode="register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _json_error(message: str, status_code: int = 400):
    return jsonify({"ok": False, "error": message}), status_code


@app.post("/api/analyze")
def api_analyze():
    payload: dict[str, Any] = request.get_json(silent=True) or {}

    selected_mood = payload.get("selectedMood")
    journal_text = payload.get("journalText")
    selected_secondary_emotion = payload.get("selectedSecondaryEmotion")
    selected_cause = payload.get("selectedCause")

    if not selected_mood:
        return _json_error("selectedMood is required")
    if not journal_text or not str(journal_text).strip():
        return _json_error("journalText is required")

    try:
        result = ANALYZE_JOURNAL(str(journal_text), str(selected_mood))
    except Exception as exc:
        return _json_error(f"Analysis failed: {exc}", 500)

    # Keep frontend logic simple: include match + a friendly confidence percent.
    predicted_mood = result.get("predicted_mood")
    predicted_emotion = result.get("predicted_emotion")
    confidence = result.get("confidence")

    # Define mood groupings for effective matches
    POSITIVE_MOODS = {"Awesome", "Good"}
    NEUTRAL_MOODS = {"Fine"}
    NEGATIVE_MOODS = {"Bad", "Terrible"}

    is_match = (
        predicted_mood == selected_mood
        or (predicted_mood in POSITIVE_MOODS and selected_mood in POSITIVE_MOODS)
        or (predicted_mood in NEUTRAL_MOODS and selected_mood in NEUTRAL_MOODS)
        or (predicted_mood in NEGATIVE_MOODS and selected_mood in NEGATIVE_MOODS)
    )

    # Map general 'predicted_emotion' or 'predicted_mood' to Activity tag (Sad, Angry, Anxious, Happy)
    target_tag = ""
    # Simplified mapping using exact strings from the model's EMOTION_NAMES
    if predicted_emotion in ["Sadness", "Sad", "Disgusted", "Grief"]:
        target_tag = "Sad"
    elif predicted_emotion in ["Anger", "Angry", "Annoyed", "Frustrated"]:
        target_tag = "Angry"
    elif predicted_emotion in ["Fear", "Anxious", "Scared", "Panic"]:
        target_tag = "Anxious"
    elif predicted_emotion in ["Joy", "Happy", "Joyful", "Love", "Loved", "Relieved", "Grateful", "Surprise"] or predicted_mood in ["Awesome", "Good"]:
        target_tag = "Happy"
    elif predicted_mood in ["Bad", "Terrible"]:
        target_tag = "Sad" # fallback


    recommendations = []
    if target_tag:
        recommendations = get_activities_by_emotion(target_tag)

    # Automatically save the journal entry during analysis
    journal_id = None
    if db_available():
        journal_id = insert_feedback(
            user_id=session.get("user_id"),
            selected_mood=str(selected_mood),
            selected_secondary_emotion=str(selected_secondary_emotion) if selected_secondary_emotion else None,
            selected_cause=str(selected_cause) if selected_cause else None,
            journal_text=str(journal_text),
            predicted_mood=str(predicted_mood) if predicted_mood else None,
            predicted_emotion=str(predicted_emotion) if predicted_emotion else None,
            predicted_secondary_emotion=str(result.get("secondary_emotion")) if result.get("secondary_emotion") else None,
            confidence=float(confidence) if confidence is not None else None,
            is_match=is_match,
            feedback=None, # To be updated via feedback API if user clicks
            risk_level=result.get("risk_level"),
            matched_phrases=result.get("matched_phrases") or [],
        )

    return jsonify(
        {
            "ok": True,
            "analysis": result,
            "isMatch": is_match,
            "confidencePercent": (float(confidence) * 100.0) if confidence is not None else None,
            "meta": {
                "selectedSecondaryEmotion": selected_secondary_emotion,
                "selectedCause": selected_cause,
                "journalId": journal_id
            },
            "recommendations": recommendations,
        }
    )


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    journal_id = payload.get("journalId")
    feedback = payload.get("feedback")  # "Yes" | "No"

    if not journal_id:
        return _json_error("journalId is required")
    if feedback not in ("Yes", "No"):
        return _json_error("feedback must be 'Yes' or 'No'")

    if db_available():
        update_feedback(journal_id, feedback)
    
    # Check for negative streak alert
    alert_triggered = False
    if session.get("user_id"):
        negative_count = check_negative_streak(session.get("user_id"), days=30)
        if negative_count >= 15:
            alert_triggered = True

    return jsonify({"ok": True, "alert_triggered": alert_triggered})


@app.get("/reports")
def reports_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    user_id = session.get("user_id", 1)
    # Default to 30 days visualization for charts
    days_filter = int(request.args.get("days", 30))
    
    distribution = get_user_mood_distribution(user_id, days_filter)
    history = get_user_mood_history(user_id, days_filter)
    
    # Fetch a longer history for the calendar view (e.g., last 365 days)
    calendar_history = get_user_mood_history(user_id, 365)
    
    trusted_contact = get_trusted_contact(user_id)
    
    # Pass data directly as JSON to be embedded in template
    return render_template(
        "reports.html", 
        distribution=distribution, 
        history=history, 
        calendar_history=calendar_history,
        trusted_contact=trusted_contact,
        current_days=days_filter
    )


@app.get("/history")
def history_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    user_id = session.get("user_id", 1)
    filter_type = request.args.get("filter", "today") # today, monthly, favourites
    
    entries = get_filtered_history(user_id, filter_type)
    
    return render_template(
        "history.html",
        entries=entries,
        current_filter=filter_type
    )


@app.post("/api/toggle_favourite")
def api_toggle_favourite():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
        
    payload = request.get_json(silent=True) or {}
    journal_id = payload.get("journalId")
    
    if not journal_id:
        return _json_error("journalId is required")
        
    new_status = toggle_favourite(journal_id)
    return jsonify({"ok": True, "is_favourite": new_status})



@app.post("/api/trusted_contact")
def api_trusted_contact():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
        
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    email = payload.get("email")
    if not email:
        return _json_error("Email is required")
        
    user_id = session.get("user_id", 1)
    save_trusted_contact(user_id, email)
    return jsonify({"ok": True, "message": "Trusted contact saved."})


if __name__ == "__main__":
    # Create table once at startup (if MySQL is configured).
    init_db()

    # Debug is convenient for UI development.
    app.run(host="127.0.0.1", port=5000, debug=True)

