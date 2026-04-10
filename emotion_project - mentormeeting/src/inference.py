import numpy as np
import pickle

from crisis_detector import detect_crisis_language
from preprocess import preprocess
from tfidf import compute_tfidf
from model import SoftmaxRegression


# =========================
# CONFIGURATION
# =========================

EMOTION_NAMES = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]

CONFIDENCE_THRESHOLD = 0.55


# =========================
# LOAD MODEL
# =========================

data = np.load("../saved_model/model_weights.npz")
W = data["W"]
b = data["b"]
idf = data["idf"]

with open("../saved_model/vocab.pkl", "rb") as f:
    vocab = pickle.load(f)

model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)
model.W = W
model.b = b


# =========================
# EMOTION → MOOD MAPPING
# =========================

def map_emotion_to_mood(emotion):
    mapping = {
        "Joy": "Awesome",
        "Love": "Awesome",
        "Surprise": "Good",
        "Sadness": "Bad",
        "Anger": "Terrible",
        "Fear": "Bad"
    }
    return mapping.get(emotion, "Fine")


# =========================
# MONTHLY STATS
# =========================

from collections import Counter

def monthly_mood_percentage(mood_list):
    total = len(mood_list)
    counts = Counter(mood_list)

    moods = ["Awesome", "Good", "Fine", "Bad", "Terrible"]

    percentages = {}

    for mood in moods:
        percentages[mood] = round((counts[mood] / total) * 100, 2) if total > 0 else 0

    return percentages


# =========================
# MAIN ANALYSIS FUNCTION
# =========================

def analyze_journal(text, user_selected_mood):

    # 🚨 Crisis detection
    crisis_result = detect_crisis_language(text)

    if crisis_result["is_crisis"]:
        return {
            "predicted_emotion": "Crisis",
            "secondary_emotion": None,
            "confidence": 1.0,
            "predicted_mood": "Terrible",
            "all_probabilities": {
                emotion: 0.0 for emotion in EMOTION_NAMES
            },
            "show_modal": True,
            "show_alert": True,
            "risk_level": crisis_result["risk_level"],
            "matched_phrases": crisis_result["matched_phrases"],
        }

    # =========================
    # PREPROCESS
    # =========================
    tokens = preprocess(text)

    # =========================
    # TF-IDF
    # =========================
    X = np.array([compute_tfidf(tokens, vocab, idf)])

    # =========================
    # PREDICTION
    # =========================
    _, probs = model.predict(X)
    probabilities = probs[0]

    # =========================
    # 🔥 SMART EMOTION LOGIC
    # =========================

    sorted_indices = np.argsort(probabilities)[::-1]

    top1_idx = sorted_indices[0]
    top2_idx = sorted_indices[1]

    predicted_emotion = EMOTION_NAMES[top1_idx]
    confidence = probabilities[top1_idx]

    diff = probabilities[top1_idx] - probabilities[top2_idx]

    # 🔥 Decision rules
    if confidence < 0.15:
        predicted_emotion = "Mixed/Unclear"
        secondary_emotion = None

    elif diff < 0.10:
        secondary_emotion = EMOTION_NAMES[top2_idx]

    else:
        secondary_emotion = None

    predicted_mood = map_emotion_to_mood(predicted_emotion)

    # =========================
    # RESULT OBJECT
    # =========================
    result = {
        "predicted_emotion": predicted_emotion,
        "secondary_emotion": secondary_emotion,
        "confidence": float(confidence),
        "predicted_mood": predicted_mood,
        "all_probabilities": {
            EMOTION_NAMES[i]: float(probabilities[i])
            for i in range(6)
        },
        "show_alert": False,
        "risk_level": None,
        "matched_phrases": [],
    }

    # =========================
    # MODAL LOGIC
    # =========================

    POSITIVE_MOODS = {"Awesome", "Good"}
    NEUTRAL_MOODS = {"Fine"}
    NEGATIVE_MOODS = {"Bad", "Terrible"}
    
    moods_effectively_match = (
        predicted_mood == user_selected_mood
        or (predicted_mood in POSITIVE_MOODS and user_selected_mood in POSITIVE_MOODS)
        or (predicted_mood in NEUTRAL_MOODS and user_selected_mood in NEUTRAL_MOODS)
        or (predicted_mood in NEGATIVE_MOODS and user_selected_mood in NEGATIVE_MOODS)
    )

    if confidence >= CONFIDENCE_THRESHOLD and not moods_effectively_match:
        result["show_modal"] = True
    else:
        result["show_modal"] = False

    return result