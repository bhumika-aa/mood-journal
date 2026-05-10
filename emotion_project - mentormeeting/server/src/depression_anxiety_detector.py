import re

DEPRESSION_PATTERNS = [
    r"\bhopeless\b",
    r"\bworthless\b",
    r"\bempty\b",
    r"\bexhausted\b",
    r"\bno motivation\b",
    r"\bfeel numb\b",
    r"\blost interest\b",
    r"\bfeel alone\b",
    r"\bdo not care anymore\b",
    r"\bcrying all the time\b",
    r"\btired all the time\b",
]

ANXIETY_PATTERNS = [
    r"\banxious\b",
    r"\bnervous\b",
    r"\bpanic\b",
    r"\boverwhelmed\b",
    r"\bworried\b",
    r"\bcan't relax\b",
    r"\bheart racing\b",
    r"\bscared\b",
    r"\btense\b",
    r"\brestless\b",
    r"\bstressed\b",
]

def normalize_text(text):
    text = text.lower().strip()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text

def find_matches(text, patterns):
    matches = []
    for pattern in patterns:
        matched = re.search(pattern, text)
        if matched:
            matches.append(matched.group(0))
    return matches

def get_severity(score):
    if score >= 5:
        return "High"
    elif score >= 3:
        return "Moderate"
    elif score >= 1:
        return "Low"
    return "None"

def detect_depression_anxiety(text):
    normalized = normalize_text(text)
    depression_matches = find_matches(
        normalized,
        DEPRESSION_PATTERNS
    )
    anxiety_matches = find_matches(
        normalized,
        ANXIETY_PATTERNS
    )
    depression_score = len(depression_matches)
    anxiety_score = len(anxiety_matches)
    return {
        "depression_score": depression_score,
        "depression_level": get_severity(
            depression_score
        ),
        "anxiety_score": anxiety_score,
        "anxiety_level": get_severity(
            anxiety_score
        ),
        "depression_matches": depression_matches,
        "anxiety_matches": anxiety_matches,
    }
