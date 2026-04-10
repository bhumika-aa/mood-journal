# src/augment.py

import random

# Expanded synonym dictionary
SYNONYMS = {
    "shocked": ["stunned", "amazed", "astonished"],
    "surprised": ["shocked", "amazed"],
    "miss": ["long","yearn","ache","crave"],
    "tired": ["exhausted", "drained"],

    "love": ["adore","cherish","affection","devoted","fond","care"],
    "excited": ["thrilled", "enthusiastic"],
    "romantic": ["passionate","affectionate"],

    "happy": ["glad","pleased","delighted"],
    "sad": ["unhappy","down","upset"],
    "angry": ["mad","furious","annoyed"],

    "fear": ["panic","terror","dread","fright"],
    "scared": ["afraid","terrified","petrified","fearful"],
    "anxious": ["nervous","uneasy","tense","worried"],

    "unexpected": ["unforeseen", "sudden"]
}

INTENSIFIERS = ["very", "really", "extremely", "deeply"]


def synonym_replacement(tokens):
    new_tokens = tokens.copy()
    replaceable = [w for w in tokens if w in SYNONYMS]

    if not replaceable:
        return tokens

    num_replacements = random.choice([1, 2])

    for _ in range(num_replacements):
        word = random.choice(replaceable)
        synonym = random.choice(SYNONYMS[word])
        new_tokens = [synonym if w == word else w for w in new_tokens]

    return new_tokens


def add_intensifier(tokens):
    new_tokens = tokens.copy()

    emotion_words = [w for w in tokens if w in SYNONYMS]

    if emotion_words:
        word = random.choice(emotion_words)
        idx = new_tokens.index(word)
        intensifier = random.choice(INTENSIFIERS)
        new_tokens.insert(idx, intensifier)

    return new_tokens


def augment_sentence(tokens):
    tokens = synonym_replacement(tokens)

    if random.random() > 0.35:
        tokens = add_intensifier(tokens)

    return tokens


def augment_dataset(train_df, target_count):
    import pandas as pd

    augmented_rows = []
    label_counts = train_df["label"].value_counts().to_dict()

    for label, count in label_counts.items():

        if count < target_count:

            needed = target_count - count
            label_rows = train_df[train_df["label"] == label]

            for _ in range(needed):
                row = label_rows.sample(n=1).iloc[0]
                tokens = row["tokens"]

                new_tokens = augment_sentence(tokens)
                new_text = " ".join(new_tokens)

                augmented_rows.append({
                    "text": new_text,
                    "label": label
                })

    augmented_df = pd.DataFrame(augmented_rows)
    return pd.concat([train_df, augmented_df], ignore_index=True)
