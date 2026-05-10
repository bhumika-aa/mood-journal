# src/evaluate.py

import numpy as np


def accuracy(y_true, y_pred):
    return np.mean(y_true == y_pred)


def confusion_matrix(y_true, y_pred, num_classes):
    matrix = np.zeros((num_classes, num_classes), dtype=int)

    for true, pred in zip(y_true, y_pred):
        matrix[true][pred] += 1

    return matrix


def per_class_metrics(y_true, y_pred, class_names):
    matrix = confusion_matrix(y_true, y_pred, len(class_names))
    metrics = []

    for idx, class_name in enumerate(class_names):
        tp = matrix[idx, idx]
        fp = np.sum(matrix[:, idx]) - tp
        fn = np.sum(matrix[idx, :]) - tp
        support = np.sum(matrix[idx, :])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )

        metrics.append({
            "class_name": class_name,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "support": int(support),
        })

    return metrics


def macro_average(metrics):
    if not metrics:
        return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    return {
        "precision": np.mean([item["precision"] for item in metrics]),
        "recall": np.mean([item["recall"] for item in metrics]),
        "f1_score": np.mean([item["f1_score"] for item in metrics]),
    }


def weighted_average(metrics):
    total_support = sum(item["support"] for item in metrics)

    if total_support == 0:
        return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    return {
        "precision": sum(item["precision"] * item["support"] for item in metrics) / total_support,
        "recall": sum(item["recall"] * item["support"] for item in metrics) / total_support,
        "f1_score": sum(item["f1_score"] * item["support"] for item in metrics) / total_support,
    }


def format_classification_report(metrics):
    lines = []
    header = f"{'Class':<12}{'Precision':>12}{'Recall':>10}{'F1-Score':>12}{'Support':>10}"
    lines.append(header)
    lines.append("-" * len(header))

    for item in metrics:
        lines.append(
            f"{item['class_name']:<12}"
            f"{item['precision']:>12.2f}"
            f"{item['recall']:>10.2f}"
            f"{item['f1_score']:>12.2f}"
            f"{item['support']:>10}"
        )

    macro = macro_average(metrics)
    weighted = weighted_average(metrics)
    total_support = sum(item["support"] for item in metrics)

    lines.append("-" * len(header))
    lines.append(
        f"{'Macro Avg':<12}{macro['precision']:>12.2f}{macro['recall']:>10.2f}"
        f"{macro['f1_score']:>12.2f}{total_support:>10}"
    )
    lines.append(
        f"{'Weighted Avg':<12}{weighted['precision']:>12.2f}{weighted['recall']:>10.2f}"
        f"{weighted['f1_score']:>12.2f}{total_support:>10}"
    )

    return "\n".join(lines)
