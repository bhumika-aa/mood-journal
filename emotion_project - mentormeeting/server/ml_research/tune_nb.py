import pandas as pd
import numpy as np
import random
from preprocess import preprocess
from tfidf import build_vocab, compute_idf, compute_tfidf
from model import SoftmaxRegression, NaiveBayes
from evaluate import accuracy

# Set seeds
np.random.seed(42)
random.seed(42)

# LOAD DATA
print("Loading data...")
train_df = pd.read_csv("../data/train.csv")
val_df = pd.read_csv("../data/validation.csv")

# PREPROCESS
print("Preprocessing text...")
train_df["tokens"] = train_df["text"].apply(preprocess)
val_df["tokens"] = val_df["text"].apply(preprocess)

# BUILD VOCAB AND TF-IDF
print("Building vocabulary...")
vocab = build_vocab(train_df["tokens"], max_features=5000)
idf = compute_idf(train_df["tokens"], vocab)

X_train = np.array([compute_tfidf(t, vocab, idf) for t in train_df["tokens"]])
X_val = np.array([compute_tfidf(t, vocab, idf) for t in val_df["tokens"]])

y_train = train_df["label"].values
y_val = val_df["label"].values
num_classes = len(np.unique(y_train))

# --- TUNING NAIVE BAYES ---
alphas = [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
best_alpha = 1.0
best_acc = 0.0
results = []

print("\n" + "="*40)
print("TUNING NAIVE BAYES (ALPHA)")
print("="*40)

for alpha in alphas:
    model = NaiveBayes(num_classes=num_classes, alpha=alpha)
    model.train(X_train, y_train)
    
    val_preds, _ = model.predict(X_val)
    acc = accuracy(y_val, val_preds)
    results.append((alpha, acc))
    print(f"Alpha: {alpha:<6} | Validation Accuracy: {acc:.4f}")
    
    if acc > best_acc:
        best_acc = acc
        best_alpha = alpha

print("\n" + "="*40)
print(f"BEST NB RESULT: Alpha={best_alpha}, Accuracy={best_acc:.4f}")
print("="*40)

# --- COMPARE WITH SOFTMAX ---
print("\nTraining Softmax for comparison...")
sm_model = SoftmaxRegression(input_dim=len(vocab), num_classes=num_classes)
y_train_onehot = np.zeros((len(y_train), num_classes))
for i in range(len(y_train)):
    y_train_onehot[i][y_train[i]] = 1

class_counts = train_df["label"].value_counts().sort_index().values
class_weights = len(train_df) / (num_classes * class_counts)

sm_model.train(X_train, y_train_onehot, epochs=20, lr=0.5, batch_size=64, class_weights=class_weights)
sm_preds, _ = sm_model.predict(X_val)
sm_acc = accuracy(y_val, sm_preds)

print(f"\nFinal Comparison:")
print(f"Tuned Naive Bayes: {best_acc:.4f}")
print(f"Softmax Regression: {sm_acc:.4f}")

gap = sm_acc - best_acc
if gap > 0:
    print(f"Gap: {gap:.4f} (Softmax is still better)")
else:
    print(f"Gap: {gap:.4f} (Naive Bayes is now equal or better!)")
