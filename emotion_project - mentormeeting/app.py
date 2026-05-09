from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
from typing import Any

import nltk
from flask import Flask, jsonify, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    init_db, insert_feedback, db_available, 
    get_activities_by_emotion, get_all_activities,
    get_user_mood_distribution, get_user_mood_history,
    save_trusted_contact, get_trusted_contact, check_negative_streak,
    get_user_by_email, create_user, update_feedback,
    get_filtered_history, toggle_favourite, get_today_journal,
    get_all_users, get_all_journals_admin, get_admin_stats,
    delete_activity, update_activity, get_activity_by_id
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
        return redirect("/dashboard")
    return app.send_static_file("landing.html")
 
 
@app.get("/api/user_info")
def api_user_info():
    if not session.get("logged_in"):
        return jsonify({"logged_in": False}), 401
    return jsonify({
        "logged_in": True,
        "username": session.get("username", "there"),
        "user_id": session.get("user_id"),
        "is_admin": session.get("is_admin", False)
    })




@app.get("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/login")
    return app.send_static_file("index.html")


@app.get("/api/dashboard_data")
def api_dashboard_data():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
    
    user_id = session.get("user_id")
    username = session.get("username", "there")
    today_entry = get_today_journal(user_id) if user_id else None
    
    return jsonify({
        "username": username,
        "today_entry": today_entry
    })


@app.get("/activities")
def activities_page():
    if not session.get("logged_in"):
        return redirect("/login")
    return app.send_static_file("activities.html")


@app.get("/api/activities_data")
def api_activities_data():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
        
    try:
        activities = get_all_activities()
        categories: dict[str, list[dict[str, Any]]] = {}
        for act in activities:
            cat = act.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(act)
            
        return jsonify({"categories": categories})
    except Exception as e:
        return _json_error(f"Database error: {str(e)}", 500)


@app.post("/api/save_activity_log")
def api_save_activity_log():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
    
    payload = request.json
    activity_id = payload.get("activityId")
    content = payload.get("content")
    user_id = session.get("user_id")

    if not activity_id or not content:
        return _json_error("Missing data")

    from db import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO activity_logs (user_id, activity_id, content) VALUES (%s, %s, %s)",
            (user_id, activity_id, content)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@app.get("/api/get_activity_logs")
def api_get_activity_logs():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
    
    user_id = session.get("user_id")
    from db import connect
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT l.content, l.created_at, a.title as activity_title 
            FROM activity_logs l
            JOIN activities a ON l.activity_id = a.id
            WHERE l.user_id = %s
            ORDER BY l.created_at DESC
        """, (user_id,))
        logs = cur.fetchall()
        return jsonify({"ok": True, "logs": logs})
    finally:
        conn.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            return redirect("/login?error=Please provide both email and password.")
            
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["name"].split()[0] if user["name"] else "there"
            session["is_admin"] = bool(user.get("is_admin"))
            return redirect("/dashboard")
        else:
            return redirect("/login?error=Invalid email or password.")
            
    return app.send_static_file("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not (first_name and last_name and email and password):
            return redirect("/register?error=All fields are required.")
            
        if get_user_by_email(email):
            return redirect("/register?error=Email already registered. Please log in.")
            
        full_name = f"{first_name} {last_name}".strip()
        pwd_hash = generate_password_hash(password)
        
        user_id = create_user(email, full_name, pwd_hash)
        
        session["logged_in"] = True
        session["user_id"] = user_id
        session["username"] = first_name
        return redirect("/dashboard")
        
    return app.send_static_file("register.html")


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
            depression_level=result.get("depression_level"),
            anxiety_level=result.get("anxiety_level"),
            depression_score=result.get("depression_score"),
            anxiety_score=result.get("anxiety_score"),
            wellness_score=result.get("wellness_score"),
            wellness_level=result.get("wellness_level"),
            recommendations=result.get("recommendations"),
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
        return redirect("/login")
    return app.send_static_file("reports.html")


@app.get("/api/reports_data")
def api_reports_data():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
    
    user_id = session.get("user_id", 1)
    days_filter = int(request.args.get("days", 30))
    
    distribution = get_user_mood_distribution(user_id, days_filter)
    history = get_user_mood_history(user_id, days_filter)
    calendar_history = get_user_mood_history(user_id, 365)
    trusted_contact = get_trusted_contact(user_id)
    
    return jsonify({
        "distribution": distribution, 
        "history": history, 
        "calendar_history": calendar_history,
        "trusted_contact": trusted_contact,
        "current_days": days_filter
    })


@app.get("/history")
def history_page():
    if not session.get("logged_in"):
        return redirect("/login")
    return app.send_static_file("history.html")


@app.get("/api/history_data")
def api_history_data():
    if not session.get("logged_in"):
        return _json_error("Not logged in", 401)
        
    user_id = session.get("user_id", 1)
    filter_type = request.args.get("filter", "today") 
    
    entries = get_filtered_history(user_id, filter_type)
    return jsonify({
        "entries": entries,
        "current_filter": filter_type
    })


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


# --- Admin Routes ---

@app.get("/admin")
def admin_page():
    if not session.get("is_admin"):
        return redirect("/")
    return app.send_static_file("admin.html")

@app.get("/api/admin/stats")
def api_admin_stats():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    stats = get_admin_stats()
    return jsonify(stats)

@app.get("/api/admin/users")
def api_admin_users():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    users = get_all_users()
    return jsonify({"users": users})

@app.get("/api/admin/journals")
def api_admin_journals():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    journals = get_all_journals_admin()
    return jsonify({"journals": journals})



@app.post("/api/admin/delete_user")
def api_admin_delete_user():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    data = request.json
    uid = data.get("userId")
    if not uid:
        return _json_error("User ID required")
    if uid == session.get("user_id"):
        return _json_error("You cannot delete your own account.")
    from db import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (uid,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})

@app.post("/api/admin/update_user")
def api_admin_update_user():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    data = request.json
    uid = data.get("userId")
    name = data.get("name")
    email = data.get("email")
    is_admin = data.get("is_admin")
    if not uid:
        return _json_error("User ID required")
    from db import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET name = %s, email = %s, is_admin = %s 
            WHERE id = %s
        """, (name, email, 1 if is_admin else 0, uid))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})

@app.post("/api/admin/delete_activity")
def api_delete_activity():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    data = request.json
    aid = data.get("id")
    if not aid:
        return _json_error("Activity ID required")
    if delete_activity(aid):
        return jsonify({"ok": True})
    return _json_error("Failed to delete activity")

@app.post("/api/admin/update_activity")
def api_update_activity():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    data = request.json
    aid = data.get("id")
    if not aid:
        return _json_error("Activity ID required")
    if update_activity(aid, data):
        return jsonify({"ok": True})
    return _json_error("Failed to update activity")

@app.post("/api/upload_image")
def api_upload_image():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    
    if 'image' not in request.files:
        return _json_error("No file part")
    
    file = request.files['image']
    if file.filename == '':
        return _json_error("No selected file")
    
    if file:
        upload_dir = os.path.join('static', 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Use a safe filename
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return jsonify({"ok": True, "url": f"/static/uploads/{filename}"})

@app.post("/api/admin/create_activity")
def api_admin_create_activity():
    if not session.get("is_admin"):
        return _json_error("Unauthorized", 403)
    data = request.json
    title = data.get("title")
    description = data.get("description")
    duration = data.get("duration")
    category = data.get("category")
    image_url = data.get("image_url")
    audio_url = data.get("audio_url")
    target_emotion = data.get("target_emotion", "Happy")
    action_type = data.get("action_type", "article")
    prompt = data.get("prompt")
    content = data.get("content")
    
    if not title or not category:
        return _json_error("Title and Category are required")
        
    from db import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO activities (title, description, duration, category, icon, image_url, audio_url, target_emotion, action_type, prompt, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (title, description, duration, category, "sparkles", image_url, audio_url, target_emotion, action_type, prompt, content))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Create table once at startup (if MySQL is configured).
    init_db()

    # Debug is convenient for UI development.
    app.run(host="127.0.0.1", port=5000, debug=True)


