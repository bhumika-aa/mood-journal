import pandas as pd
import numpy as np
import random
from preprocess import preprocess
from tfidf import build_vocab, compute_idf, compute_tfidf
from model import SoftmaxRegression, NaiveBayes
from evaluate import accuracy, format_classification_report, per_class_metrics

# Set seeds for reproducibility
np.random.seed(42)
random.seed(42)

def one_hot(y, num_classes):
    onehot = np.zeros((len(y), num_classes))
    for i in range(len(y)):
        onehot[i][y[i]] = 1
    return onehot

# 1. LOAD DATA
print("Loading data...")
train_df = pd.read_csv("../data/train.csv")
val_df = pd.read_csv("../data/validation.csv")

# 2. PREPROCESS
print("Preprocessing text...")
train_df["tokens"] = train_df["text"].apply(preprocess)
val_df["tokens"] = val_df["text"].apply(preprocess)

# 3. BUILD VOCAB AND TF-IDF
print("Building vocabulary...")
vocab = build_vocab(train_df["tokens"], max_features=5000)
idf = compute_idf(train_df["tokens"], vocab)

X_train = np.array([compute_tfidf(t, vocab, idf) for t in train_df["tokens"]])
X_val = np.array([compute_tfidf(t, vocab, idf) for t in val_df["tokens"]])

y_train = train_df["label"].values
y_val = val_df["label"].values
num_classes = len(np.unique(y_train))
class_names = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]

# --- MODEL 1: SOFTMAX REGRESSION ---
print("\n" + "="*40)
print("TRAINING SOFTMAX REGRESSION")
print("="*40)

sm_model = SoftmaxRegression(input_dim=len(vocab), num_classes=num_classes)
y_train_onehot = one_hot(y_train, num_classes)

# Compute class weights for Softmax
class_counts = train_df["label"].value_counts().sort_index().values
class_weights = len(train_df) / (num_classes * class_counts)

sm_model.train(X_train, y_train_onehot, epochs=20, lr=0.5, batch_size=64, class_weights=class_weights)

sm_val_preds, _ = sm_model.predict(X_val)
sm_val_acc = accuracy(y_val, sm_val_preds)

# --- MODEL 2: NAIVE BAYES ---
print("\n" + "="*40)
print("TRAINING NAIVE BAYES")
print("="*40)

nb_model = NaiveBayes(num_classes=num_classes)
nb_model.train(X_train, y_train)

nb_val_preds, _ = nb_model.predict(X_val)
nb_val_acc = accuracy(y_val, nb_val_preds)

# --- FINAL COMPARISON ---
print("\n" + "="*40)
print("FINAL RESULTS COMPARISON")
print("="*40)
print(f"Softmax Regression Validation Accuracy: {sm_val_acc:.4f}")
print(f"Naive Bayes Validation Accuracy:        {nb_val_acc:.4f}")

if sm_val_acc > nb_val_acc:
    print("\nWinner: SOFTMAX REGRESSION")
elif nb_val_acc > sm_val_acc:
    print("\nWinner: NAIVE BAYES")
else:
    print("\nIt's a TIE!")

print("\n--- Softmax Classification Report ---")
sm_metrics = per_class_metrics(y_val, sm_val_preds, class_names)
print(format_classification_report(sm_metrics))

print("\n--- Naive Bayes Classification Report ---")
nb_metrics = per_class_metrics(y_val, nb_val_preds, class_names)
print(format_classification_report(nb_metrics))
