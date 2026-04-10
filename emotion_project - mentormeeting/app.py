from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
from typing import Any

import nltk
from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from db import (
    init_db, insert_feedback, db_available, 
    get_activities_by_emotion, get_all_activities,
    get_user_mood_distribution, get_user_mood_history,
    save_trusted_contact, get_trusted_contact, check_negative_streak
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
    username = session.get("username", "there")
    return render_template("index.html", username=username)


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
        # Mock login: accept any email/password
        session["logged_in"] = True
        session["user_id"] = 1 # mocked user_id
        email = request.form.get("email", "")
        # Derive a display name from the email prefix
        session["username"] = email.split("@")[0].capitalize() if email else "there"
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Mock registration: accept any inputs
        session["logged_in"] = True
        session["user_id"] = 1 # mocked user_id
        name = request.form.get("name", "")
        session["username"] = name.strip().split()[0].capitalize() if name.strip() else "there"
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
    # Simplified mapping
    if predicted_emotion in ["Sad", "Disgusted", "Grief"]:
        target_tag = "Sad"
    elif predicted_emotion in ["Angry", "Annoyed", "Frustrated"]:
        target_tag = "Angry"
    elif predicted_emotion in ["Anxious", "Scared", "Panic"]:
        target_tag = "Anxious"
    elif predicted_emotion in ["Happy", "Joyful", "Loved", "Relieved", "Grateful"] or predicted_mood in ["Awesome", "Good"]:
        target_tag = "Happy"
    elif predicted_mood in ["Bad", "Terrible"]:
        target_tag = "Sad" # fallback

    recommendations = []
    if target_tag:
        recommendations = get_activities_by_emotion(target_tag)

    return jsonify(
        {
            "ok": True,
            "analysis": result,
            "isMatch": is_match,
            "confidencePercent": (float(confidence) * 100.0) if confidence is not None else None,
            "meta": {
                "selectedSecondaryEmotion": selected_secondary_emotion,
                "selectedCause": selected_cause,
            },
            "recommendations": recommendations,
        }
    )


@app.post("/api/feedback")
def api_feedback():
    if not db_available():
        return _json_error(
            "MySQL is not configured (set MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE).",
            500,
        )

    payload: dict[str, Any] = request.get_json(silent=True) or {}

    selected_mood = payload.get("selectedMood")
    selected_secondary_emotion = payload.get("selectedSecondaryEmotion")
    selected_cause = payload.get("selectedCause")
    journal_text = payload.get("journalText")
    feedback = payload.get("feedback")  # "Yes" | "No"

    if feedback not in ("Yes", "No"):
        return _json_error("feedback must be 'Yes' or 'No'")
    if not selected_mood:
        return _json_error("selectedMood is required")
    if not journal_text or not str(journal_text).strip():
        return _json_error("journalText is required")

    # Re-analyze to keep DB consistent with the algorithm output.
    result = ANALYZE_JOURNAL(str(journal_text), str(selected_mood))

    predicted_mood = result.get("predicted_mood")
    predicted_emotion = result.get("predicted_emotion")
    predicted_secondary_emotion = result.get("secondary_emotion")
    confidence = result.get("confidence")
    POSITIVE_MOODS = {"Awesome", "Good"}
    NEUTRAL_MOODS = {"Fine"}
    NEGATIVE_MOODS = {"Bad", "Terrible"}

    is_match = (
        predicted_mood == selected_mood
        or (predicted_mood in POSITIVE_MOODS and selected_mood in POSITIVE_MOODS)
        or (predicted_mood in NEUTRAL_MOODS and selected_mood in NEUTRAL_MOODS)
        or (predicted_mood in NEGATIVE_MOODS and selected_mood in NEGATIVE_MOODS)
    )

    insert_feedback(
        user_id=session.get("user_id", 1), # mock user id
        selected_mood=str(selected_mood),
        selected_secondary_emotion=(
            str(selected_secondary_emotion) if selected_secondary_emotion else None
        ),
        selected_cause=str(selected_cause) if selected_cause else None,
        journal_text=str(journal_text),
        predicted_mood=str(predicted_mood) if predicted_mood else None,
        predicted_emotion=str(predicted_emotion) if predicted_emotion else None,
        predicted_secondary_emotion=(
            str(predicted_secondary_emotion) if predicted_secondary_emotion else None
        ),
        confidence=float(confidence) if confidence is not None else None,
        is_match=is_match,
        feedback=feedback,
        risk_level=result.get("risk_level"),
        matched_phrases=result.get("matched_phrases") or [],
    )
    
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
    # Default to 30 days visualization
    days_filter = int(request.args.get("days", 30))
    
    distribution = get_user_mood_distribution(user_id, days_filter)
    history = get_user_mood_history(user_id, days_filter)
    trusted_contact = get_trusted_contact(user_id)
    
    # Pass data directly as JSON to be embedded in template
    return render_template(
        "reports.html", 
        distribution=distribution, 
        history=history, 
        trusted_contact=trusted_contact,
        current_days=days_filter
    )


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

