def generate_recommendations(
    depression_level,
    anxiety_level,
    predicted_emotion,
):
    recommendations = []

    # Depression recommendations
    if depression_level == "High":
        recommendations.extend([
            "Talk to a trusted person.",
            "Try to avoid isolation.",
            "Write your thoughts in detail.",
            "Consider professional mental health support.",
        ])
    elif depression_level == "Moderate":
        recommendations.extend([
            "Practice self-care activities.",
            "Go outside for a short walk.",
            "Maintain a healthy sleep schedule.",
        ])

    # Anxiety recommendations
    if anxiety_level == "High":
        recommendations.extend([
            "Try deep breathing exercises.",
            "Practice grounding techniques.",
            "Listen to calming music.",
            "Take short breaks and relax.",
        ])
    elif anxiety_level == "Moderate":
        recommendations.extend([
            "Practice meditation.",
            "Reduce stressful activities.",
            "Try journaling your worries.",
        ])

    # Emotion-based recommendations
    if predicted_emotion == "Anger":
        recommendations.append(
            "Take time before reacting emotionally."
        )
    elif predicted_emotion == "Sadness":
        recommendations.append(
            "Reach out to supportive people."
        )
    elif predicted_emotion == "Fear":
        recommendations.append(
            "Focus on calming and reassurance."
        )

    # Default
    if not recommendations:
        recommendations.append(
            "Keep maintaining your emotional wellness."
        )

    return recommendations
