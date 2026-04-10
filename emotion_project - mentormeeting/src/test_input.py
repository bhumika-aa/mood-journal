from inference import analyze_journal


def main():
    print("Emotion model tester")
    print("Type 'exit' to stop.\n")

    while True:
        text = input("Enter journal entry: ").strip()

        if text.lower() == "exit":
            print("Exiting tester.")
            break

        if not text:
            print("Please enter some text.\n")
            continue

        user_mood = input(
            "Enter your selected mood (Awesome/Good/Fine/Bad/Terrible): "
        ).strip()

        if not user_mood:
            user_mood = "Fine"

        result = analyze_journal(text, user_mood)

        print("\nResult:")

        # =========================
        # 🔥 SMART OUTPUT
        # =========================

        if result["predicted_emotion"] == "Mixed/Unclear":
            print("We couldn't detect a strong emotion today.")
            print("You might be feeling neutral or balanced.")

        elif result["secondary_emotion"]:
            print(
                f"You are feeling {result['predicted_emotion']} "
                f"(with some {result['secondary_emotion']})"
            )

        else:
            print(f"You are feeling {result['predicted_emotion']}")

        print("Predicted mood:", result["predicted_mood"])
        print("Confidence:", round(result["confidence"], 4))
        print("Show modal:", result["show_modal"])
        print("Show alert:", result["show_alert"])

        if result["risk_level"]:
            print("Risk level:", result["risk_level"])

        if result["matched_phrases"]:
            print("Matched phrases:", ", ".join(result["matched_phrases"]))

        print("\nProbabilities:")
        for emotion, probability in result["all_probabilities"].items():
            print(f"  {emotion}: {probability:.4f}")

        print()


if __name__ == "__main__":
    main()