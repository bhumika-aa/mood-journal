import re


HIGH_RISK_PATTERNS = [
    r"\bkill myself\b",
    r"\bkilling myself\b",
    r"\bgoing to kill myself\b",
    r"\bend my life\b",
    r"\bending my life\b",
    r"\bwant to die\b",
    r"\bwanting to die\b",
    r"\bwanna die\b",
    r"\bi should die\b",
    r"\bdont want to live\b",
    r"\bdo not want to live\b",
    r"\bsuicidal\b",
    r"\bcommit suicide\b",
    r"\bcommitting suicide\b",
    r"\btake my own life\b",
    r"\btaking my own life\b",
    r"\bhurt myself\b",
    r"\bhurting myself\b",
    r"\bself harm\b",
    r"\bself harming\b",
    r"\bhang myself\b",
    r"\bhanging myself\b",
    r"\bwant to hang myself\b",
    r"\bwant to hang\b",
    r"\bhang on ceiling\b",
    r"\bhang from ceiling\b",
    r"\bhang from the ceiling\b",
    r"\bjump off\b",
    r"\bjump out of the window\b",
    r"\bjump from the window\b",
]

MEDIUM_RISK_PATTERNS = [
    r"\bsuicide\b",
    r"\bdie\b",
    r"\bkill me\b",
    r"\bnot worth living\b",
    r"\bno reason to live\b",
    r"\bdisappear forever\b",
    r"\bwant everything to end\b",
]


def normalize_text(text):
    normalized = text.lower().strip()
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"[^a-z\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def find_matches(text, patterns):
    matches = []

    for pattern in patterns:
        matched = re.search(pattern, text)
        if matched:
            matches.append(matched.group(0))

    return matches


def detect_crisis_language(text):
    normalized_text = normalize_text(text)

    high_matches = find_matches(normalized_text, HIGH_RISK_PATTERNS)
    medium_matches = find_matches(normalized_text, MEDIUM_RISK_PATTERNS)

    if high_matches:
        return {
            "is_crisis": True,
            "risk_level": "high",
            "matched_phrases": high_matches,
        }

    if len(medium_matches) >= 2:
        return {
            "is_crisis": True,
            "risk_level": "medium",
            "matched_phrases": medium_matches,
        }

    return {
        "is_crisis": False,
        "risk_level": None,
        "matched_phrases": [],
    }
