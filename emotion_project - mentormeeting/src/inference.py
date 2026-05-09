import numpy as np
import pickle
from collections import Counter
from crisis_detector import detect_crisis_language
from preprocess import preprocess
from tfidf import compute_tfidf
from model import SoftmaxRegression, NaiveBayes
from depression_anxiety_detector import (
    detect_depression_anxiety,
    get_severity
)
from wellness_scoring import (
    calculate_wellness_score,
    get_wellness_level,
)
from recommendations import (
    generate_recommendations
)

# CONFIGURATION
EMOTION_NAMES = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]
CONFIDENCE_THRESHOLD = 0.55

from pathlib import Path
# ...
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "saved_model"

# LOAD MODELS
data = np.load(MODEL_DIR / "model_weights.npz")
idf = data["idf"]

with open(MODEL_DIR / "vocab.pkl", "rb") as f:
    vocab = pickle.load(f)

# Softmax
softmax_model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)
softmax_model.W = data["W"]
softmax_model.b = data["b"]

# Naive Bayes
nb_model = NaiveBayes(num_classes=6, alpha=float(data.get("nb_alpha", 0.1)))
nb_model.class_priors = data["nb_priors"]
nb_model.feature_probs = data["nb_probs"]


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


def monthly_mood_percentage(mood_list):
    total = len(mood_list)
    counts = Counter(mood_list)
    moods = ["Awesome", "Good", "Fine", "Bad", "Terrible"]
    percentages = {}
    for mood in moods:
        percentages[mood] = round((counts[mood] / total) * 100, 2) if total > 0 else 0
    return percentages


def analyze_journal(text, user_selected_mood):
    # 🚨 Crisis detection
    crisis_result = detect_crisis_language(text)

    if crisis_result["is_crisis"]:
        return {
            "predicted_emotion": "Crisis",
            "secondary_emotion": None,
            "confidence": 1.0,
            "nb_confidence": 1.0,
            "nb_emotion": "Crisis",
            "predicted_mood": "Terrible",
            "all_probabilities": {e: 0.0 for e in EMOTION_NAMES},
            "show_modal": True,
            "show_alert": True,
            "risk_level": crisis_result["risk_level"],
            "matched_phrases": crisis_result["matched_phrases"],
            "depression_level": "High",
            "anxiety_level": "High",
            "depression_score": 5,
            "anxiety_score": 5,
            "wellness_score": 0,
            "wellness_level": "Critical",
            "recommendations": ["Please seek professional help immediately."],
        }

    # 🧠 Mental Health Detection
    mental_health_result = detect_depression_anxiety(text)

    # PREPROCESS
    tokens = preprocess(text)
    X = np.array([compute_tfidf(tokens, vocab, idf)])

    # SOFTMAX PREDICTION
    _, sm_probs = softmax_model.predict(X)
    sm_probabilities = sm_probs[0]
    sm_sorted_indices = np.argsort(sm_probabilities)[::-1]
    
    sm_top1_idx = sm_sorted_indices[0]
    sm_top2_idx = sm_sorted_indices[1]
    
    predicted_emotion = EMOTION_NAMES[sm_top1_idx]
    confidence = sm_probabilities[sm_top1_idx]
    
    # NAIVE BAYES PREDICTION
    _, nb_probs = nb_model.predict(X)
    nb_probabilities = nb_probs[0]
    
    # 🧪 HEURISTIC BOOST (Sensitivity Improvement)
    # If the text explicitly mentions strong emotional keywords, we give them a slight push.
    # This helps when positive context outweighs a final emotional statement.
    lower_text = text.lower()
    boosts = {
        "Sadness": ["sad", "depressed", "unhappy", "lonely", "crying", "miserable", "heartbroken", "gloomy", "hopeless", "grief", "sorrow"],
        "Anger": ["angry", "frustrated", "annoyed", "pissed", "mad", "hate", "furious", "irritated", "rage", "resent", "bitter"],
        "Fear": ["scared", "anxious", "worried", "panic", "fear", "nervous", "terrified", "frightened", "apprehensive", "dread"],
    }
    
    for emotion, keywords in boosts.items():
        if any(kw in lower_text for kw in keywords):
            idx = EMOTION_NAMES.index(emotion)
            # Boost the probability of the detected emotion
            sm_probabilities[idx] += 0.25
            nb_probabilities[idx] += 0.25
    
    # Re-normalize probabilities
    sm_probabilities = sm_probabilities / np.sum(sm_probabilities)
    nb_probabilities = nb_probabilities / np.sum(nb_probabilities)

    # RE-SORT AFTER BOOST
    sm_sorted_indices = np.argsort(sm_probabilities)[::-1]
    sm_top1_idx = sm_sorted_indices[0]
    sm_top2_idx = sm_sorted_indices[1]
    
    predicted_emotion = EMOTION_NAMES[sm_top1_idx]
    confidence = sm_probabilities[sm_top1_idx]
    
    nb_top_idx = np.argmax(nb_probabilities)
    nb_confidence = nb_probabilities[nb_top_idx]
    nb_emotion = EMOTION_NAMES[nb_top_idx]

    # Secondary emotion logic (Softmax)
    diff = sm_probabilities[sm_top1_idx] - sm_probabilities[sm_top2_idx]
    if confidence < 0.15:
        predicted_emotion = "Mixed/Unclear"
        secondary_emotion = None
    elif diff < 0.10:
        secondary_emotion = EMOTION_NAMES[sm_top2_idx]
    else:
        secondary_emotion = None

    # Hybrid enhancement
    if predicted_emotion == "Sadness":
        mental_health_result["depression_score"] += 1
    if predicted_emotion == "Fear":
        mental_health_result["anxiety_score"] += 1

    # Recalculate levels
    mental_health_result["depression_level"] = get_severity(
        mental_health_result["depression_score"]
    )
    mental_health_result["anxiety_level"] = get_severity(
        mental_health_result["anxiety_score"]
    )

    # Calculate Wellness Score
    wellness_score = calculate_wellness_score(
        predicted_emotion,
        mental_health_result["depression_score"],
        mental_health_result["anxiety_score"],
        crisis_result["is_crisis"],
    )

    # Wellness Level
    wellness_level = get_wellness_level(wellness_score)

    # Generate Recommendations
    recommendations = generate_recommendations(
        mental_health_result["depression_level"],
        mental_health_result["anxiety_level"],
        predicted_emotion,
    )

    predicted_mood = map_emotion_to_mood(predicted_emotion)

    # RESULT OBJECT
    result = {
        "predicted_emotion": predicted_emotion,
        "secondary_emotion": secondary_emotion,
        "confidence": float(confidence),
        "nb_confidence": float(nb_confidence),
        "nb_emotion": nb_emotion,
        "predicted_mood": predicted_mood,
        "all_probabilities": {
            EMOTION_NAMES[i]: float(sm_probabilities[i])
            for i in range(6)
        },
        "show_alert": False,
        "risk_level": None,
        "matched_phrases": [],
        "depression_level": mental_health_result["depression_level"],
        "anxiety_level": mental_health_result["anxiety_level"],
        "depression_score": mental_health_result["depression_score"],
        "anxiety_score": mental_health_result["anxiety_score"],
        "wellness_score": wellness_score,
        "wellness_level": wellness_level,
        "recommendations": recommendations,
    }

    # MODAL LOGIC
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