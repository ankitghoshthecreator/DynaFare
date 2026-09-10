"""
XGBoost model loader and inference logic.
The model artifact is loaded once at startup (singleton pattern).
"""

import logging
import os

import redis
import xgboost as xgb

from inference.features import build_features

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "model/price_model.json")
ETA_MODEL_PATH = os.getenv("ETA_MODEL_PATH", "model/eta_model.json")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# ─── Singletons ──────────────────────────────────────────────────────────────
_price_model: xgb.Booster | None = None
_eta_model: xgb.Booster | None = None
_redis: redis.Redis | None = None


def get_predictor() -> tuple[xgb.Booster, xgb.Booster]:
    """Load models once; return the (price, eta) Booster pair."""
    global _price_model, _eta_model
    if _price_model is None:
        if os.path.exists(MODEL_PATH):
            _price_model = xgb.Booster()
            _price_model.load_model(MODEL_PATH)
            logger.info("Price model loaded from %s", MODEL_PATH)
        else:
            logger.warning("Model file not found at %s — returning stub predictor.", MODEL_PATH)
            _price_model = None  # will fall back to rule-based below
    if _eta_model is None:
        if os.path.exists(ETA_MODEL_PATH):
            _eta_model = xgb.Booster()
            _eta_model.load_model(ETA_MODEL_PATH)
            logger.info("ETA model loaded from %s", ETA_MODEL_PATH)
        else:
            _eta_model = None
    return _price_model, _eta_model


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis


def _get_demand_ratio(zone_id: str | None) -> float:
    """Read the pre-computed demand/supply ratio from Redis."""
    if not zone_id:
        return 1.0
    try:
        r = _get_redis()
        value = r.get(f"zone:{zone_id}:demand_ratio")
        return float(value) if value else 1.0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis read failed (%s) — using demand_ratio=1.0", exc)
        return 1.0


# ─── Flat-rate fallback ───────────────────────────────────────────────────────
BASE_RATE_PER_KM = 12.0   # ₹ per km base
BASE_MINUTES_PER_KM = 3.5  # minutes per km baseline


def _flat_rate(distance_km: float, demand_ratio: float) -> tuple[float, float]:
    """Deterministic fallback price + ETA when the ML model is unavailable."""
    price = round(BASE_RATE_PER_KM * distance_km * demand_ratio, 2)
    eta = round(BASE_MINUTES_PER_KM * distance_km, 1)
    return max(price, 30.0), max(eta, 5.0)


# ─── Main inference function ──────────────────────────────────────────────────

def predict(payload: dict) -> dict:
    """
    Run price + ETA prediction for a single trip request.

    Returns:
        dict with keys: price, eta_minutes, surge_multiplier, confidence, source
    """
    zone_id = payload.get("zone_id")
    demand_ratio = _get_demand_ratio(zone_id)

    features_df = build_features(payload, demand_ratio=demand_ratio)
    distance_km = float(features_df["distance_km"].iloc[0])

    price_model, eta_model = get_predictor()

    if price_model is None or eta_model is None:
        price, eta = _flat_rate(distance_km, demand_ratio)
        return {
            "price": price,
            "eta_minutes": eta,
            "surge_multiplier": demand_ratio,
            "confidence": 0.5,
            "source": "flat_rate_fallback",
        }

    dmatrix = xgb.DMatrix(features_df)
    price = float(price_model.predict(dmatrix)[0])
    eta = float(eta_model.predict(dmatrix)[0])

    return {
        "price": round(max(price, 30.0), 2),
        "eta_minutes": round(max(eta, 5.0), 1),
        "surge_multiplier": round(demand_ratio, 2),
        "confidence": 0.85,   # TODO: derive from quantile regression
        "source": "xgboost",
    }
