# src/model.py

import numpy as np

class SoftmaxRegression:

    def __init__(self, input_dim, num_classes):
        # Small random weights
        self.W = np.random.randn(input_dim, num_classes) * 0.01
        
        # Bias initialized later using class priors
        self.b = np.zeros((1, num_classes))

    def softmax(self, z):
        """
        Numerically stable softmax.
        """
        exp_z = np.exp(z - np.max(z, axis=1, keepdims=True))
        return exp_z / np.sum(exp_z, axis=1, keepdims=True)

    def compute_loss(self, y_true, y_pred, lambda_reg, class_weights=None):
        """
        Cross entropy + L2 regularization.
        WHY regularization?
        - Prevent weight explosion
        - Improve generalization
        """

        m = y_true.shape[0]

        if class_weights is not None:
            sample_weights = np.sum(y_true * class_weights, axis=1, keepdims=True)
            cross_entropy = -np.sum(sample_weights * y_true * np.log(y_pred + 1e-9)) / m
        else:
            cross_entropy = -np.sum(y_true * np.log(y_pred + 1e-9)) / m

        l2_penalty = (lambda_reg / 2) * np.sum(self.W ** 2)

        return cross_entropy + l2_penalty

    def train(self, X, y_onehot, epochs=20, lr=0.5, lambda_reg=0.001, batch_size=64, class_weights=None):

        n_samples = X.shape[0]

        for epoch in range(epochs):

            # Shuffle every epoch
            indices = np.random.permutation(n_samples)
            X_shuffled = X[indices]
            y_shuffled = y_onehot[indices]

            for start in range(0, n_samples, batch_size):
                end = start + batch_size

                X_batch = X_shuffled[start:end]
                y_batch = y_shuffled[start:end]

                m = X_batch.shape[0]

                # Forward
                z = np.dot(X_batch, self.W) + self.b
                y_pred = self.softmax(z)

                # Backprop
                dz = y_pred - y_batch
                
                if class_weights is not None:
                    sample_weights = np.sum(y_batch * class_weights, axis=1, keepdims=True)
                    dz = dz * sample_weights

                dW = (np.dot(X_batch.T, dz) / m) + lambda_reg * self.W
                db = np.sum(dz, axis=0, keepdims=True) / m

                # Update
                self.W -= lr * dW
                self.b -= lr * db

            # Compute loss on full dataset for monitoring
            z_full = np.dot(X, self.W) + self.b
            y_full = self.softmax(z_full)
            loss = self.compute_loss(y_onehot, y_full, lambda_reg, class_weights)

            print(f"Epoch {epoch}, Loss: {loss:.4f}")

    def predict(self, X):
        z = np.dot(X, self.W) + self.b
        probs = self.softmax(z)
        preds = np.argmax(probs, axis=1)
        return preds, probs