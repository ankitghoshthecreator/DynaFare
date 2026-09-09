"""
XGBoost model training script — Part 6 (offline, not part of the runtime image).

Usage:
    python training/train.py --data data/nyc_trips.csv --output model/

The script:
  1. Loads historical trip data.
  2. Engineers features using the shared features.py module.
  3. Trains separate price and ETA regressors.
  4. Saves models to JSON format.
  5. Logs evaluation metrics (MAE, RMSE).
"""

import argparse
import logging
import os
import json

import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from inference.features import build_features, FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

# ─── Default XGBoost hyperparameters ─────────────────────────────────────────
DEFAULT_PARAMS = {
    "objective": "reg:squarederror",
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "tree_method": "hist",
}


def load_and_engineer(csv_path: str) -> pd.DataFrame:
    """Load raw NYC TLC trip CSV and produce a feature-engineered DataFrame."""
    logger.info("Loading data from %s", csv_path)
    df = pd.read_csv(csv_path, parse_dates=["tpep_pickup_datetime"], low_memory=False)
    df = df.dropna(subset=["fare_amount", "trip_distance"])
    df = df[(df["fare_amount"] > 0) & (df["trip_distance"] > 0)]

    rows = []
    for _, row in df.iterrows():
        payload = {
            "pickup_lat": row.get("pickup_latitude", 40.7128),
            "pickup_lon": row.get("pickup_longitude", -74.0060),
            "dropoff_lat": row.get("dropoff_latitude", 40.7580),
            "dropoff_lon": row.get("dropoff_longitude", -73.9855),
            "timestamp": str(row["tpep_pickup_datetime"]),
            "weather": "clear",  # TODO: merge with weather API data
        }
        feat = build_features(payload, demand_ratio=1.0).iloc[0].to_dict()
        feat["fare_amount"] = row["fare_amount"]
        feat["trip_duration_min"] = max(row.get("trip_duration_min", row["trip_distance"] * 3.5), 1)
        rows.append(feat)

    return pd.DataFrame(rows)


def train(csv_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    df = load_and_engineer(csv_path)

    X = df[FEATURE_COLUMNS]
    y_price = df["fare_amount"]
    y_eta = df["trip_duration_min"]

    # Time-based split — always validate on future data
    split = int(len(df) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_price_train, y_price_val = y_price.iloc[:split], y_price.iloc[split:]
    y_eta_train, y_eta_val = y_eta.iloc[:split], y_eta.iloc[split:]

    logger.info("Training price model on %d samples...", len(X_train))
    price_model = xgb.XGBRegressor(**DEFAULT_PARAMS)
    price_model.fit(X_train, y_price_train, eval_set=[(X_val, y_price_val)], verbose=50)

    logger.info("Training ETA model on %d samples...", len(X_train))
    eta_model = xgb.XGBRegressor(**DEFAULT_PARAMS)
    eta_model.fit(X_train, y_eta_train, eval_set=[(X_val, y_eta_val)], verbose=50)

    # ─── Evaluate ───
    price_preds = price_model.predict(X_val)
    eta_preds = eta_model.predict(X_val)

    metrics = {
        "price_mae": round(mean_absolute_error(y_price_val, price_preds), 3),
        "price_rmse": round(root_mean_squared_error(y_price_val, price_preds), 3),
        "eta_mae": round(mean_absolute_error(y_eta_val, eta_preds), 3),
        "eta_rmse": round(root_mean_squared_error(y_eta_val, eta_preds), 3),
    }
    logger.info("Evaluation metrics: %s", metrics)

    # ─── Save ───
    price_path = os.path.join(output_dir, "price_model.json")
    eta_path = os.path.join(output_dir, "eta_model.json")
    price_model.save_model(price_path)
    eta_model.save_model(eta_path)

    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Models saved to %s", output_dir)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train DynaFare XGBoost models.")
    parser.add_argument("--data", required=True, help="Path to NYC TLC trip CSV")
    parser.add_argument("--output", default="model/", help="Output directory for model files")
    args = parser.parse_args()
    train(args.data, args.output)
