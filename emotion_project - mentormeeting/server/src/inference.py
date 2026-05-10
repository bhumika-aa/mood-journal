import numpy as np
import pickle
from collections import Counter
from pathlib import Path
from typing import Any, Optional

# Import local modules from src
try:
    from crisis_detector import detect_crisis_language
    from preprocess import preprocess
    from tfidf import compute_tfidf
    from model import SoftmaxRegression, NaiveBayes
    from depression_anxiety_detector import detect_depression_anxiety, get_severity
    from wellness_scoring import calculate_wellness_score, get_wellness_level
    from recommendations import generate_recommendations
except ImportError:
    # Handle cases where src is not in path (like direct script execution)
    from .crisis_detector import detect_crisis_language
    from .preprocess import preprocess
    from .tfidf import compute_tfidf
    from .model import SoftmaxRegression, NaiveBayes
    from .depression_anxiety_detector import detect_depression_anxiety, get_severity
    from .wellness_scoring import calculate_wellness_score, get_wellness_level
    from .recommendations import generate_recommendations


class MoodAnalyzer:
    """
    Handles emotion and mood prediction using trained ML models.
    Encapsulates Softmax Regression and Naive Bayes models.
    """

    EMOTION_NAMES = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]
    CONFIDENCE_THRESHOLD = 0.55

    def __init__(self, model_dir: Optional[Path] = None):
        if model_dir is None:
            # Default path relative to this file
            model_dir = Path(__file__).resolve().parent.parent / "saved_model"
        
        self.model_dir = model_dir
        self._load_models()

    def _load_models(self):
        """Loads weights and vocabulary from disk."""
        data = np.load(self.model_dir / "model_weights.npz")
        self.idf = data["idf"]

        with open(self.model_dir / "vocab.pkl", "rb") as f:
            self.vocab = pickle.load(f)

        # Softmax Regression
        self.softmax_model = SoftmaxRegression(input_dim=len(self.vocab), num_classes=6)
        self.softmax_model.W = data["W"]
        self.softmax_model.b = data["b"]

        # Naive Bayes
        self.nb_model = NaiveBayes(num_classes=6, alpha=float(data.get("nb_alpha", 0.1)))
        self.nb_model.class_priors = data["nb_priors"]
        self.nb_model.feature_probs = data["nb_probs"]

    @staticmethod
    def map_emotion_to_mood(emotion: str) -> str:
        mapping = {
            "Joy": "Awesome", "Love": "Awesome", "Surprise": "Good",
            "Sadness": "Bad", "Anger": "Terrible", "Fear": "Bad"
        }
        return mapping.get(emotion, "Fine")

    def analyze_journal(self, text: str, user_selected_mood: str) -> dict[str, Any]:
        """
        Main entry point for analyzing a journal entry.
        Returns a comprehensive dictionary with predicted emotions, scores, and recommendations.
        """
        # 🚨 Crisis detection
        crisis_result = detect_crisis_language(text)
        if crisis_result["is_crisis"]:
            return self._format_crisis_result(crisis_result)

        # 🧠 Mental Health Detection
        mental_health_result = detect_depression_anxiety(text)

        # PREPROCESS & VECTORIZE
        tokens = preprocess(text)
        X = np.array([compute_tfidf(tokens, self.vocab, self.idf)])

        # PREDICTIONS
        _, sm_probs = self.softmax_model.predict(X)
        sm_probabilities = sm_probs[0].copy()
        
        _, nb_probs = self.nb_model.predict(X)
        nb_probabilities = nb_probs[0].copy()
        
        # 🧪 HEURISTIC BOOST
        sm_probabilities, nb_probabilities = self._apply_heuristic_boost(text, sm_probabilities, nb_probabilities)
        
        # Get Top Predictions
        sm_top_indices = np.argsort(sm_probabilities)[::-1]
        predicted_emotion = self.EMOTION_NAMES[sm_top_indices[0]]
        confidence = sm_probabilities[sm_top_indices[0]]
        
        nb_top_idx = np.argmax(nb_probabilities)
        nb_emotion = self.EMOTION_NAMES[nb_top_idx]
        nb_confidence = nb_probabilities[nb_top_idx]

        # Secondary emotion logic
        diff = sm_probabilities[sm_top_indices[0]] - sm_probabilities[sm_top_indices[1]]
        secondary_emotion = self.EMOTION_NAMES[sm_top_indices[1]] if 0.15 <= confidence and diff < 0.10 else None
        if confidence < 0.15: predicted_emotion = "Mixed/Unclear"

        # Hybrid enhancement
        if predicted_emotion == "Sadness": mental_health_result["depression_score"] += 1
        if predicted_emotion == "Fear": mental_health_result["anxiety_score"] += 1

        # Recalculate levels & scores
        mental_health_result["depression_level"] = get_severity(mental_health_result["depression_score"])
        mental_health_result["anxiety_level"] = get_severity(mental_health_result["anxiety_score"])
        
        wellness_score = calculate_wellness_score(
            predicted_emotion, 
            mental_health_result["depression_score"],
            mental_health_result["anxiety_score"],
            False
        )
        wellness_level = get_wellness_level(wellness_score)
        recommendations = generate_recommendations(
            mental_health_result["depression_level"],
            mental_health_result["anxiety_level"],
            predicted_emotion
        )

        predicted_mood = self.map_emotion_to_mood(predicted_emotion)

        # Final result assembly
        result = {
            "predicted_mood": predicted_mood,
            "predicted_emotion": predicted_emotion,
            "secondary_emotion": secondary_emotion,
            "confidence": float(confidence),
            "nb_confidence": float(nb_confidence),
            "is_match": bool(confidence >= self.CONFIDENCE_THRESHOLD),
            "risk_level": None,
            "matched_phrases": [],
            "depression_level": mental_health_result["depression_level"],
            "anxiety_level": mental_health_result["anxiety_level"],
            "depression_score": int(mental_health_result["depression_score"]),
            "anxiety_score": int(mental_health_result["anxiety_score"]),
            "wellness_score": int(wellness_score),
            "wellness_level": wellness_level,
            "recommendations": recommendations,
            "show_alert": False,
            "all_probabilities": {self.EMOTION_NAMES[i]: float(sm_probabilities[i]) for i in range(6)}
        }

        # Modal logic
        result["show_modal"] = bool(self._should_show_modal(predicted_mood, user_selected_mood, float(confidence)))

        return result

    def _apply_heuristic_boost(self, text: str, sm_probs: np.ndarray, nb_probs: np.ndarray):
        lower_text = text.lower()
        boosts = {
            "Sadness": ["sad", "depressed", "unhappy", "lonely", "crying", "miserable", "heartbroken", "gloomy", "hopeless", "grief", "sorrow"],
            "Anger": ["angry", "frustrated", "annoyed", "pissed", "mad", "hate", "furious", "irritated", "rage", "resent", "bitter"],
            "Fear": ["scared", "anxious", "worried", "panic", "fear", "nervous", "terrified", "frightened", "apprehensive", "dread"],
        }
        for emotion, keywords in boosts.items():
            if any(kw in lower_text for kw in keywords):
                idx = self.EMOTION_NAMES.index(emotion)
                sm_probs[idx] += 0.25
                nb_probs[idx] += 0.25
        
        # Normalize
        return sm_probs / np.sum(sm_probs), nb_probs / np.sum(nb_probs)

    def _should_show_modal(self, predicted: str, selected: str, confidence: float) -> bool:
        POSITIVE = {"Awesome", "Good"}
        NEUTRAL = {"Fine"}
        NEGATIVE = {"Bad", "Terrible"}
        
        match = (predicted == selected or 
                 (predicted in POSITIVE and selected in POSITIVE) or
                 (predicted in NEUTRAL and selected in NEUTRAL) or
                 (predicted in NEGATIVE and selected in NEGATIVE))
        
        return confidence >= self.CONFIDENCE_THRESHOLD and not match

    def _format_crisis_result(self, crisis_result: dict) -> dict:
        return {
            "predicted_emotion": "Crisis", "secondary_emotion": None,
            "confidence": 1.0, "nb_confidence": 1.0, "nb_emotion": "Crisis",
            "predicted_mood": "Terrible", "all_probabilities": {e: 0.0 for e in self.EMOTION_NAMES},
            "show_modal": True, "show_alert": True,
            "risk_level": crisis_result["risk_level"], "matched_phrases": crisis_result["matched_phrases"],
            "depression_level": "High", "anxiety_level": "High", "depression_score": 5, "anxiety_score": 5,
            "wellness_score": 0, "wellness_level": "Critical",
            "recommendations": ["Please seek professional help immediately."],
        }

# --- BACKWARD COMPATIBILITY ---
_analyzer = None

def analyze_journal(text, user_selected_mood):
    global _analyzer
    if _analyzer is None:
        _analyzer = MoodAnalyzer()
    return _analyzer.analyze_journal(text, user_selected_mood)