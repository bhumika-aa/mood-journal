import pandas as pd
import numpy as np
import random
import pickle

np.random.seed(42)
random.seed(42)

from preprocess import preprocess
from augment import augment_dataset
from tfidf import build_vocab, compute_idf, compute_tfidf
from model import SoftmaxRegression, NaiveBayes
from evaluate import accuracy, confusion_matrix, format_classification_report, per_class_metrics


def one_hot(y, num_classes):
    onehot = np.zeros((len(y), num_classes))
    for i in range(len(y)):
        onehot[i][y[i]] = 1
    return onehot

# 1. LOAD DATA
train_df = pd.read_csv("../data/train.csv")
val_df = pd.read_csv("../data/validation.csv")

print("Preprocessing text...")
train_df["tokens"] = train_df["text"].apply(preprocess)
val_df["tokens"] = val_df["text"].apply(preprocess)

# 2. AUGMENTATION
label_counts = train_df["label"].value_counts()
target_count = int(label_counts.mean())
print("Augmenting small classes to target:", target_count)
train_df = augment_dataset(train_df, target_count=target_count)
train_df["tokens"] = train_df["text"].apply(preprocess)

# 3. SHUFFLE
train_df = train_df.sample(frac=1, random_state=42).reset_index(drop=True)

# 4. BUILD VOCAB AND TF-IDF
vocab = build_vocab(train_df["tokens"], max_features=5000)
idf = compute_idf(train_df["tokens"], vocab)

X_train = np.array([compute_tfidf(t, vocab, idf) for t in train_df["tokens"]])
X_val = np.array([compute_tfidf(t, vocab, idf) for t in val_df["tokens"]])

y_train = train_df["label"].values
y_val = val_df["label"].values
y_train_onehot = one_hot(y_train, 6)

# 5. MODEL 1: SOFTMAX REGRESSION
print("\nTraining Softmax Regression...")
sm_model = SoftmaxRegression(input_dim=len(vocab), num_classes=6)

# Bias init
class_counts = train_df["label"].value_counts().sort_index().values
class_probs = class_counts / class_counts.sum()
sm_model.b = np.log(class_probs).reshape(1, -1)

# Class weights
class_weights = len(train_df) / (6 * class_counts)

sm_model.train(X_train, y_train_onehot, epochs=20, lr=0.5, batch_size=64, class_weights=class_weights)

# 6. MODEL 2: NAIVE BAYES
print("\nTraining Naive Bayes (alpha=0.1)...")
nb_model = NaiveBayes(num_classes=6, alpha=0.1)
nb_model.train(X_train, y_train)

# 7. EVALUATION
print("\n" + "="*30)
print("EVALUATION RESULTS")
print("="*30)

sm_preds, _ = sm_model.predict(X_val)
nb_preds, _ = nb_model.predict(X_val)

print(f"Softmax Accuracy:    {accuracy(y_val, sm_preds):.4f}")
print(f"Naive Bayes Accuracy: {accuracy(y_val, nb_preds):.4f}")

# 8. SAVE MODELS
print("\nSaving models...")
np.savez(
    "../saved_model/model_weights.npz",
    W=sm_model.W,
    b=sm_model.b,
    nb_priors=nb_model.class_priors,
    nb_probs=nb_model.feature_probs,
    nb_alpha=nb_model.alpha,
    idf=idf
)

with open("../saved_model/vocab.pkl", "wb") as f:
    pickle.dump(vocab, f)

print("All models saved successfully.")