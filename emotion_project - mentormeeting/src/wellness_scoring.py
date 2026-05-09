def calculate_wellness_score(
    predicted_emotion,
    depression_score,
    anxiety_score,
    crisis_detected,
):
    score = 100

    # Depression penalty
    score -= depression_score * 10

    # Anxiety penalty
    score -= anxiety_score * 8

    # Emotion penalty
    negative_emotions = {
        "Sadness",
        "Fear",
        "Anger"
    }

    if predicted_emotion in negative_emotions:
        score -= 15

    # Crisis penalty
    if crisis_detected:
        score -= 40

    # Clamp
    score = max(0, min(100, score))

    return score

def get_wellness_level(score):
    if score >= 80:
        return "Healthy"
    elif score >= 60:
        return "Mild Distress"
    elif score >= 40:
        return "Moderate Distress"
    elif score >= 20:
        return "High Distress"
    return "Critical"
