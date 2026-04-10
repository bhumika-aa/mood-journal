import pandas as pd
import numpy as np
import random

np.random.seed(42)
random.seed(42)

from preprocess import preprocess
from augment import augment_dataset
from tfidf import build_vocab, compute_idf, compute_tfidf
from model import SoftmaxRegression
from evaluate import accuracy, confusion_matrix, format_classification_report, per_class_metrics


def one_hot(y, num_classes):
    onehot = np.zeros((len(y), num_classes))
    for i in range(len(y)):
        onehot[i][y[i]] = 1
    return onehot


# =========================
# LOAD DATA
# =========================

train_df = pd.read_csv("../data/train.csv")
val_df = pd.read_csv("../data/validation.csv")

print("Before balancing:")
print(train_df["label"].value_counts())


# =========================
# PREPROCESS TEXT
# =========================

train_df["tokens"] = train_df["text"].apply(preprocess)
val_df["tokens"] = val_df["text"].apply(preprocess)


# =========================
# 🔥 ADAPTIVE BALANCING (TUNED)
# =========================

# Step 1: Get class distribution
label_counts = train_df["label"].value_counts()
mean_count = int(label_counts.mean())

# Step 2: Set safer augmentation target (mean instead of 80% max)
# This prevents overfitting on overly synthetic synonym-replaced phrases for tiny classes!
target_count = mean_count

print("Adaptive augmentation target:", target_count)


# =========================
# 🔥 AUGMENT SMALL CLASSES
# =========================

train_df = augment_dataset(train_df, target_count=target_count)

# Reprocess after augmentation
train_df["tokens"] = train_df["text"].apply(preprocess)


# =========================
# 🔥 SKIP DOWNSAMPLING
# =========================

# We NO longer downsample large real datasets! 
# Real journaling data is too valuable. The new mathematical 'class_weights' 
# system will completely handle the dataset imbalance cleanly without discarding any data.


# =========================
# 🔥 FINAL SHUFFLE
# =========================

train_df = train_df.sample(frac=1, random_state=42).reset_index(drop=True)

print("After balancing:")
print(train_df["label"].value_counts())


# =========================
# BUILD VOCAB
# =========================

vocab = build_vocab(train_df["tokens"], max_features=5000)
print("Vocabulary size:", len(vocab))


# =========================
# COMPUTE IDF
# =========================

idf = compute_idf(train_df["tokens"], vocab)


# =========================
# TF-IDF FEATURES
# =========================

X_train = np.array([
    compute_tfidf(tokens, vocab, idf)
    for tokens in train_df["tokens"]
])

X_val = np.array([
    compute_tfidf(tokens, vocab, idf)
    for tokens in val_df["tokens"]
])


# =========================
# LABELS
# =========================

y_train = train_df["label"].values
y_val = val_df["label"].values

y_train_onehot = one_hot(y_train, 6)


# =========================
# MODEL
# =========================

model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)


# 🔥 SMART BIAS INITIALIZATION
class_counts = train_df["label"].value_counts().sort_index().values
class_probs = class_counts / class_counts.sum()
model.b = np.log(class_probs).reshape(1, -1)


# =========================
# 🔥 COMPUTE CLASS WEIGHTS (FROM SCRATCH)
# =========================

n_samples = len(train_df)
num_classes = 6
# Count how many of each class exist currently (ordered 0 to 5)
class_counts = train_df["label"].value_counts().sort_index().values
# Pure mathematical balance: Weight for class i = Total Samples / (Number of Classes * Count of Class i)
class_weights = n_samples / (num_classes * class_counts)


# =========================
# TRAIN
# =========================

model.train(X_train, y_train_onehot, epochs=20, lr=0.5, batch_size=64, class_weights=class_weights)


# =========================
# EVALUATION
# =========================

train_preds, _ = model.predict(X_train)
train_acc = accuracy(y_train, train_preds)

val_preds, _ = model.predict(X_val)
val_acc = accuracy(y_val, val_preds)

print("\nTraining Accuracy:", train_acc)
print("Validation Accuracy:", val_acc)

print("\nConfusion Matrix:")
print(confusion_matrix(y_val, val_preds, 6))

print("\nClassification Report:")
class_names = ["Sadness", "Joy", "Love", "Anger", "Fear", "Surprise"]
metrics = per_class_metrics(y_val, val_preds, class_names)
print(format_classification_report(metrics))


# =========================
# SAVE MODEL
# =========================

import pickle

np.savez(
    "../saved_model/model_weights.npz",
    W=model.W,
    b=model.b,
    idf=idf
)

with open("../saved_model/vocab.pkl", "wb") as f:
    pickle.dump(vocab, f)

print("\nModel saved successfully.")