import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import (
    accuracy,
    confusion_matrix,
    format_classification_report,
    per_class_metrics,
)
from model import SoftmaxRegression
from preprocess import preprocess
from tfidf import compute_tfidf


CLASS_NAMES = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "saved_model"
DATA_DIR = BASE_DIR / "data"


def load_saved_model():
    data = np.load(MODEL_DIR / "model_weights.npz")
    weights = data["W"]
    bias = data["b"]
    idf = data["idf"]

    with open(MODEL_DIR / "vocab.pkl", "rb") as file:
        vocab = pickle.load(file)

    model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)
    model.W = weights
    model.b = bias

    return model, vocab, idf


def evaluate_dataset(csv_path, label):
    model, vocab, idf = load_saved_model()
    dataframe = pd.read_csv(csv_path)

    features = np.array([
        compute_tfidf(preprocess(text), vocab, idf)
        for text in dataframe["text"]
    ])
    y_true = dataframe["label"].values
    y_pred, _ = model.predict(features)

    metrics = per_class_metrics(y_true, y_pred, CLASS_NAMES)
    matrix = confusion_matrix(y_true, y_pred, len(CLASS_NAMES))

    print(f"\n{label} Accuracy: {accuracy(y_true, y_pred):.4f}")
    print(f"\n{label} Confusion Matrix:")
    print(matrix)
    print(f"\n{label} Classification Report:")
    print(format_classification_report(metrics))


def main():
    evaluate_dataset(DATA_DIR / "validation.csv", "Validation")
    evaluate_dataset(DATA_DIR / "test.csv", "Test")


if __name__ == "__main__":
    main()
