# src/train.py

import pandas as pd
import numpy as np
import random
import pickle
from pathlib import Path
from typing import Optional

from src.preprocess import TextPreprocessor
from src.augment import augment_dataset
from src.tfidf import TFIDFTransformer
from src.model import SoftmaxRegression, NaiveBayes
from src.evaluate import accuracy

class ModelTrainer:
    """
    Encapsulates the training pipeline for the Mood Journal emotion models.
    """

    def __init__(self, data_dir: str = "../data", model_dir: str = "../saved_model"):
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.preprocessor = TextPreprocessor()
        self.tfidf = TFIDFTransformer(max_features=5000)
        
        # Set seeds
        np.random.seed(42)
        random.seed(42)

    def load_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Loads training and validation datasets."""
        train_df = pd.read_csv(self.data_dir / "train.csv")
        val_df = pd.read_csv(self.data_dir / "validation.csv")
        return train_df, val_df

    def prepare_data(self, df: pd.DataFrame, augment: bool = False) -> pd.DataFrame:
        """Preprocesses and optionally augments the dataset."""
        print(f"Preprocessing {'and augmenting ' if augment else ''}text...")
        
        if augment:
            label_counts = df["label"].value_counts()
            target_count = int(label_counts.mean())
            print(f"Target count for augmentation: {target_count}")
            df = augment_dataset(df, target_count=target_count)

        df["tokens"] = df["text"].apply(self.preprocessor.tokenize)
        return df

    def one_hot(self, y: np.ndarray, num_classes: int) -> np.ndarray:
        onehot = np.zeros((len(y), num_classes))
        for i in range(len(y)):
            onehot[i][y[i]] = 1
        return onehot

    def run_pipeline(self):
        """Runs the full training pipeline."""
        # 1. Load
        train_df, val_df = self.load_data()

        # 2. Preprocess & Augment
        train_df = self.prepare_data(train_df, augment=True)
        val_df = self.prepare_data(val_df, augment=False)

        # 3. Shuffle
        train_df = train_df.sample(frac=1, random_state=42).reset_index(drop=True)

        # 4. Feature Extraction
        print("Building vocabulary and computing TF-IDF...")
        self.tfidf.build_vocab(train_df["tokens"])
        self.tfidf.compute_idf(train_df["tokens"])

        X_train = np.array([self.tfidf.transform(t) for t in train_df["tokens"]])
        X_val = np.array([self.tfidf.transform(t) for t in val_df["tokens"]])

        y_train = train_df["label"].values
        y_val = val_df["label"].values
        y_train_onehot = self.one_hot(y_train, 6)

        # 5. Train Softmax Regression
        print("\nTraining Softmax Regression...")
        sm_model = SoftmaxRegression(input_dim=len(self.tfidf.vocab), num_classes=6)
        
        # Bias initialization based on class distribution
        class_counts = train_df["label"].value_counts().sort_index().values
        class_probs = class_counts / class_counts.sum()
        sm_model.b = np.log(class_probs + 1e-9).reshape(1, -1)

        # Class weights for balanced training
        class_weights = len(train_df) / (6 * class_counts)
        sm_model.train(X_train, y_train_onehot, epochs=20, lr=0.5, batch_size=64, class_weights=class_weights)

        # 6. Train Naive Bayes
        print("\nTraining Naive Bayes...")
        nb_model = NaiveBayes(num_classes=6, alpha=0.1)
        nb_model.train(X_train, y_train)

        # 7. Evaluation
        self.evaluate(sm_model, nb_model, X_val, y_val)

        # 8. Save
        self.save_models(sm_model, nb_model)

    def evaluate(self, sm_model, nb_model, X_val, y_val):
        print("\n" + "="*30)
        print("EVALUATION RESULTS")
        print("="*30)
        
        sm_preds, _ = sm_model.predict(X_val)
        nb_preds, _ = nb_model.predict(X_val)

        print(f"Softmax Accuracy:    {accuracy(y_val, sm_preds):.4f}")
        print(f"Naive Bayes Accuracy: {accuracy(y_val, nb_preds):.4f}")

    def save_models(self, sm_model, nb_model):
        print("\nSaving models...")
        self.model_dir.mkdir(exist_ok=True)
        
        np.savez(
            self.model_dir / "model_weights.npz",
            W=sm_model.W,
            b=sm_model.b,
            nb_priors=nb_model.class_priors,
            nb_probs=nb_model.feature_probs,
            nb_alpha=nb_model.alpha,
            idf=self.tfidf.idf
        )

        with open(self.model_dir / "vocab.pkl", "wb") as f:
            pickle.dump(self.tfidf.vocab, f)

        print(f"All models saved successfully to {self.model_dir}")


if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run_pipeline()