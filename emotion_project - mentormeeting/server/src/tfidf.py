# src/tfidf.py

import numpy as np
from collections import Counter
from typing import List, Dict, Any

class TFIDFTransformer:
    """
    Handles feature engineering using TF-IDF.
    Supports unigrams and bigrams for better emotional context.
    """

    def __init__(self, max_features: int = 5000):
        self.max_features = max_features
        self.vocab: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([])

    def generate_features(self, tokens: List[str]) -> List[str]:
        """
        Combine unigrams and bigrams into one feature list.
        Bigrams help capture phrases like "feel anxious".
        """
        features = list(tokens)
        for index in range(len(tokens) - 1):
            bigram = f"{tokens[index]}__{tokens[index + 1]}"
            features.append(bigram)
        return features

    def build_vocab(self, tokenized_texts: List[List[str]]) -> Dict[str, int]:
        """Builds vocabulary from the most frequent tokens/bigrams."""
        counter = Counter()
        for tokens in tokenized_texts:
            counter.update(self.generate_features(tokens))

        most_common = counter.most_common(self.max_features)
        self.vocab = {word: idx for idx, (word, _) in enumerate(most_common)}
        return self.vocab

    def compute_idf(self, tokenized_texts: List[List[str]]) -> np.ndarray:
        """Computes Inverse Document Frequency (IDF) for the current vocabulary."""
        if not self.vocab:
            raise ValueError("Vocabulary not built. Call build_vocab first.")

        N = len(tokenized_texts)
        df_counts = np.zeros(len(self.vocab))

        for tokens in tokenized_texts:
            unique_features = set(self.generate_features(tokens))
            for feature in unique_features:
                if feature in self.vocab:
                    df_counts[self.vocab[feature]] += 1

        self.idf = np.log(N / (df_counts + 1))
        return self.idf

    def transform(self, tokens: List[str]) -> np.ndarray:
        """Transforms a single list of tokens into a normalized TF-IDF vector."""
        if not self.vocab or self.idf.size == 0:
            raise ValueError("Transformer not fitted. Build vocab and compute IDF first.")

        features = self.generate_features(tokens)
        tf = np.zeros(len(self.vocab))

        for feature in features:
            if feature in self.vocab:
                tf[self.vocab[feature]] += 1

        if len(features) > 0:
            tf = tf / len(features)

        tfidf = tf * self.idf

        # L2 normalization for stability
        norm = np.linalg.norm(tfidf)
        if norm > 0:
            tfidf = tfidf / norm

        return tfidf


# --- BACKWARD COMPATIBILITY ---

def build_vocab(tokenized_texts, max_features=5000):
    return TFIDFTransformer(max_features=max_features).build_vocab(tokenized_texts)

def compute_idf(tokenized_texts, vocab):
    t = TFIDFTransformer()
    t.vocab = vocab
    return t.compute_idf(tokenized_texts)

def compute_tfidf(tokens, vocab, idf):
    t = TFIDFTransformer()
    t.vocab = vocab
    t.idf = idf
    return t.transform(tokens)
