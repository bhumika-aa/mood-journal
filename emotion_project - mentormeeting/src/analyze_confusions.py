import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from model import SoftmaxRegression
from preprocess import preprocess
from tfidf import compute_tfidf


CLASS_NAMES = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "saved_model"
DATA_DIR = BASE_DIR / "data"


def load_saved_model():
    data = np.load(MODEL_DIR / "model_weights.npz")

    with open(MODEL_DIR / "vocab.pkl", "rb") as file:
        vocab = pickle.load(file)

    model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)
    model.W = data["W"]
    model.b = data["b"]

    return model, vocab, data["idf"]


def build_predictions(csv_path):
    model, vocab, idf = load_saved_model()
    dataframe = pd.read_csv(csv_path)

    features = np.array([
        compute_tfidf(preprocess(text), vocab, idf)
        for text in dataframe["text"]
    ])
    predictions, _ = model.predict(features)
    dataframe["pred"] = predictions

    return dataframe


def main():
    dataframe = build_predictions(DATA_DIR / "test.csv")
    wrong = dataframe[dataframe["label"] != dataframe["pred"]].copy()

    pair_counts = (
        wrong.groupby(["label", "pred"])
        .size()
        .sort_values(ascending=False)
        .head(10)
    )

    print("Top confusion pairs on test set:")
    print(pair_counts.to_string())

    for (true_label, pred_label), count in pair_counts.items():
        subset = wrong[
            (wrong["label"] == true_label) & (wrong["pred"] == pred_label)
        ]

        print(
            f"\nTRUE={CLASS_NAMES[true_label]} "
            f"PRED={CLASS_NAMES[pred_label]} "
            f"COUNT={count}"
        )

        for text in subset["text"].head(3):
            print(f"- {text}")


if __name__ == "__main__":
    main()
