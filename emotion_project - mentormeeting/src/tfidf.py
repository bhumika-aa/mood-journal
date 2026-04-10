# src/tfidf.py

import numpy as np
from collections import Counter


def generate_features(tokens):
    """
    Combine unigrams and bigrams into one feature list.
    WHY bigrams?
    - Capture short emotion phrases like "feel anxious"
    - Reduce ambiguity of single words
    """

    features = list(tokens)

    for index in range(len(tokens) - 1):
        bigram = f"{tokens[index]}__{tokens[index + 1]}"
        features.append(bigram)

    return features


def build_vocab(tokenized_texts, max_features=5000):
    """
    Limit vocabulary size to top frequent words.
    WHY:
    - Prevent huge sparse matrix
    - Improve training stability
    - Reduce noise
    """

    counter = Counter()

    for tokens in tokenized_texts:
        counter.update(generate_features(tokens))

    # Keep only most frequent words
    most_common = counter.most_common(max_features)

    vocab = {}
    for idx, (word, _) in enumerate(most_common):
        vocab[word] = idx

    return vocab


def compute_idf(tokenized_texts, vocab):
    """
    Compute IDF to reduce weight of very common words.
    """

    N = len(tokenized_texts)
    df_counts = np.zeros(len(vocab))

    for tokens in tokenized_texts:
        unique_features = set(generate_features(tokens))
        for feature in unique_features:
            if feature in vocab:
                df_counts[vocab[feature]] += 1

    idf = np.log(N / (df_counts + 1))
    return idf


def compute_tfidf(tokens, vocab, idf):
    """
    Compute normalized TF-IDF vector.
    WHY normalization?
    - Keeps feature scale stable
    - Improves gradient descent performance
    """

    features = generate_features(tokens)
    tf = np.zeros(len(vocab))

    for feature in features:
        if feature in vocab:
            tf[vocab[feature]] += 1

    if len(features) > 0:
        tf = tf / len(features)

    tfidf = tf * idf

    # L2 normalization (critical for stability)
    norm = np.linalg.norm(tfidf)
    if norm > 0:
        tfidf = tfidf / norm

    return tfidf
