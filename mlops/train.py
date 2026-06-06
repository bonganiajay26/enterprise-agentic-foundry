"""
MLOps Training Pipeline — Universal Platform
Supports: scikit-learn, XGBoost, PyTorch, TensorFlow
Integrates with: MLflow, DVC, Weights & Biases
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def load_data(data_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load training data — override for your specific data format."""
    if os.path.exists(data_path):
        df = pd.read_csv(data_path)
    else:
        # Synthetic dataset for CI validation
        rng = np.random.default_rng(42)
        n_samples = 1000
        df = pd.DataFrame({
            "feature_1": rng.normal(0, 1, n_samples),
            "feature_2": rng.normal(0, 1, n_samples),
            "feature_3": rng.uniform(0, 10, n_samples),
            "feature_4": rng.integers(0, 5, n_samples),
            "target": rng.integers(0, 2, n_samples),
        })

    X = df.drop("target", axis=1)
    y = df["target"]
    return X, y


def build_pipeline(params: dict) -> Pipeline:
    """Build the training pipeline with preprocessing + model."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingClassifier(
            n_estimators=params.get("n_estimators", 100),
            learning_rate=params.get("learning_rate", 0.1),
            max_depth=params.get("max_depth", 3),
            subsample=params.get("subsample", 0.8),
            random_state=42,
        )),
    ])


def evaluate_model(pipeline: Pipeline, X_test, y_test) -> dict:
    """Evaluate model and return metrics dict."""
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    return {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4),
    }


def train(
    experiment_name: str,
    run_name: str,
    data_path: str,
    output_dir: str,
    params: dict,
    accuracy_threshold: float = 0.70,
) -> dict:
    """
    Full training pipeline with MLflow experiment tracking.
    Returns metrics dict.
    """
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        # Load and split data
        X, y = load_data(data_path)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")

        # Log params
        mlflow.log_params(params)
        mlflow.log_param("training_samples", len(X_train))
        mlflow.log_param("test_samples", len(X_test))
        mlflow.log_param("feature_count", X.shape[1])

        # Build and train
        pipeline = build_pipeline(params)

        # Cross-validation
        cv_scores = cross_val_score(pipeline, X_train, y_train, cv=StratifiedKFold(n_splits=5))
        mlflow.log_metric("cv_accuracy_mean", float(cv_scores.mean()))
        mlflow.log_metric("cv_accuracy_std", float(cv_scores.std()))
        print(f"CV Accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

        # Final fit
        pipeline.fit(X_train, y_train)

        # Evaluate
        metrics = evaluate_model(pipeline, X_test, y_test)
        mlflow.log_metrics(metrics)
        print("Test Metrics:", json.dumps(metrics, indent=2))

        # Threshold check
        if metrics["accuracy"] < accuracy_threshold:
            raise ValueError(
                f"Model accuracy {metrics['accuracy']} below threshold {accuracy_threshold}. "
                "Training failed quality gate."
            )

        # Log model
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        mlflow.sklearn.log_model(
            pipeline,
            "model",
            registered_model_name=f"{experiment_name}-model",
            signature=mlflow.models.infer_signature(X_train, y_train),
        )

        # Save artifacts
        metrics_path = f"{output_dir}/metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f)
        mlflow.log_artifact(metrics_path)

        print(f"\n✓ Training complete. Run ID: {run.info.run_id}")
        print(f"  Accuracy: {metrics['accuracy']} (threshold: {accuracy_threshold})")
        return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-name", default="default-experiment")
    parser.add_argument("--run-name", default="training-run")
    parser.add_argument("--data-path", default="data/train/train.csv")
    parser.add_argument("--output-dir", default="./artifacts")
    parser.add_argument("--accuracy-threshold", type=float, default=0.70)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--max-depth", type=int, default=3)
    args = parser.parse_args()

    params = {
        "n_estimators": args.n_estimators,
        "learning_rate": args.learning_rate,
        "max_depth": args.max_depth,
    }

    train(
        experiment_name=args.experiment_name,
        run_name=args.run_name,
        data_path=args.data_path,
        output_dir=args.output_dir,
        params=params,
        accuracy_threshold=args.accuracy_threshold,
    )
