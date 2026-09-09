"""
Feature engineering shared between training and serving.
All feature transformations MUST be identical here to avoid train/serve skew.
"""

import math
import pandas as pd
from datetime import datetime


# ─── Haversine distance ──────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─── Cyclic time encoding ────────────────────────────────────────────────────

def cyclic_encode(value: int, max_value: int):
    """Encode an integer cyclically as (sin, cos) to preserve periodicity."""
    angle = 2 * math.pi * value / max_value
    return math.sin(angle), math.cos(angle)


# ─── Build feature vector ────────────────────────────────────────────────────

def build_features(payload: dict, demand_ratio: float = 1.0) -> pd.DataFrame:
    """
    Convert a raw request payload into the feature DataFrame expected by the model.

    Args:
        payload: dict with keys: pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                 weather (optional, default 'clear'), timestamp (optional ISO string).
        demand_ratio: current demand/supply ratio read from Redis (default 1.0 = neutral).

    Returns:
        Single-row DataFrame with all model features.
    """
    now = datetime.utcnow()
    ts_str = payload.get("timestamp")
    if ts_str:
        try:
            now = datetime.fromisoformat(ts_str)
        except ValueError:
            pass

    hour_sin, hour_cos = cyclic_encode(now.hour, 24)
    dow_sin, dow_cos = cyclic_encode(now.weekday(), 7)

    distance_km = haversine_km(
        payload["pickup_lat"], payload["pickup_lon"],
        payload["dropoff_lat"], payload["dropoff_lon"],
    )

    weather_map = {"clear": 0, "rain": 1, "snow": 2, "fog": 3}
    weather_code = weather_map.get(payload.get("weather", "clear"), 0)

    return pd.DataFrame([{
        "distance_km": distance_km,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "demand_ratio": demand_ratio,
        "weather_code": weather_code,
    }])


FEATURE_COLUMNS = [
    "distance_km",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "demand_ratio",
    "weather_code",
]
