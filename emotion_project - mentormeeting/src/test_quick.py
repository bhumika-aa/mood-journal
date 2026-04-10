from inference import analyze_journal

texts = [
    "I had an awful sleep last night and I feel drained.", 
    "My partner surprised me with a lovely gift today!", 
    "I am terrified of the upcoming exam results."
]

for t in texts:
    res = analyze_journal(t, "Fine")
    print(f"TEXT: {t}\nMOOD: {res['predicted_emotion']} (Confidence: {res['confidence']:.2f})\n")
