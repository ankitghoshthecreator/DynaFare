"""
10 Hard-Level Test Cases for DynaFare ML Service
Tests: edge inputs, security, concurrency, model robustness, data pipeline
"""

import os
import sys
import math
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from inference.features import build_features, haversine_km, FEATURE_COLUMNS
from inference.model import predict, _flat_rate


# ─── TC-01: NULL / missing required fields ─────────────────────────────────────
class TestTC01MissingRequiredFields:
    """TC-01: predict() must not crash or return garbage when fields are missing."""

    def test_missing_dropoff_raises(self):
        """Missing dropoff coords should raise a KeyError, not silently return 0."""
        payload = {"pickup_lat": 40.7128, "pickup_lon": -74.006}
        with pytest.raises((KeyError, Exception)):
            build_features(payload)

    def test_empty_payload_raises(self):
        """An empty dict must raise, not return NaN-filled output."""
        with pytest.raises((KeyError, Exception)):
            build_features({})


# ─── TC-02: Boundary coordinate values ─────────────────────────────────────────
class TestTC02BoundaryCoordinates:
    """TC-02: Coordinates at mathematical extremes must not produce NaN or inf."""

    def test_poles_same_point(self):
        """Distance between North Poles = 0."""
        dist = haversine_km(90.0, 0.0, 90.0, 0.0)
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_antipodal_points(self):
        """Antipodal points should be ~20,015 km (half earth circumference)."""
        dist = haversine_km(0.0, 0.0, 0.0, 180.0)
        assert 20010 < dist < 20020

    def test_features_no_nan(self):
        """Extreme coords must not produce NaN features."""
        payload = {
            "pickup_lat": -90.0, "pickup_lon": -180.0,
            "dropoff_lat": 90.0, "dropoff_lon": 180.0,
        }
        df = build_features(payload)
        assert not df.isnull().any().any(), "NaN values detected in feature output"
        for col in FEATURE_COLUMNS:
            val = df[col].iloc[0]
            assert math.isfinite(val), f"Non-finite value in column {col}: {val}"

    def test_features_no_inf(self):
        """Distance of 0 (same coords) must not divide-by-zero."""
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.7128, "dropoff_lon": -74.006,
        }
        df = build_features(payload)
        assert df["distance_km"].iloc[0] == pytest.approx(0.0, abs=1e-6)


# ─── TC-03: Negative and invalid demand_ratio ──────────────────────────────────
class TestTC03InvalidDemandRatio:
    """TC-03: demand_ratio must handle zero, negative, and extreme values."""

    BASE_PAYLOAD = {
        "pickup_lat": 40.7128, "pickup_lon": -74.006,
        "dropoff_lat": 40.7580, "dropoff_lon": -73.9855,
    }

    def test_demand_ratio_zero(self):
        """Zero demand ratio must be clamped to 1.0, so price stays at normal surge level."""
        price, eta = _flat_rate(5.0, 0.0)
        # With clamp: surge becomes 1.0 → price = 12.0 * 5.0 * 1.0 = 60.0 (> floor of 30)
        assert price >= 30.0, f"Price should always be >= 30, got {price}"
        assert price == pytest.approx(60.0)  # clamped surge=1.0, distance=5km

    def test_demand_ratio_negative(self):
        """Negative demand ratio is physically impossible. flat_rate should floor to 30."""
        price, eta = _flat_rate(5.0, -1.0)
        # Negative surge would produce negative price — minimum floor should protect this
        assert price >= 30.0, f"Flat rate should be at least 30, got {price}"

    def test_demand_ratio_extreme(self):
        """Demand ratio of 100 should return a price, not crash."""
        price, eta = _flat_rate(5.0, 100.0)
        assert price > 0
        assert math.isfinite(price)

    def test_demand_ratio_flows_to_features(self):
        df = build_features(self.BASE_PAYLOAD, demand_ratio=0.0)
        assert df["demand_ratio"].iloc[0] == 0.0


# ─── TC-04: Malicious / adversarial input to build_features ───────────────────
class TestTC04AdversarialInput:
    """TC-04: build_features must sanitise or reject injection/overflow attempts."""

    def test_nan_coord_input(self):
        """NaN coordinates must raise ValueError — not silently propagate into features."""
        payload = {
            "pickup_lat": float("nan"), "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
        }
        with pytest.raises(ValueError, match="Non-finite coordinate"):
            build_features(payload)

    def test_inf_coord_input(self):
        """Infinite coordinate must raise ValueError, not silently produce garbage."""
        payload = {
            "pickup_lat": float("inf"), "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
        }
        with pytest.raises(ValueError, match="Non-finite coordinate"):
            build_features(payload)

    def test_unknown_weather_defaults_to_clear(self):
        """Unknown weather string must default to 0 (clear), not crash."""
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
            "weather": "hurricane_category_5_injection; DROP TABLE trips;",
        }
        df = build_features(payload)
        assert df["weather_code"].iloc[0] == 0

    def test_very_long_weather_string(self):
        """Very long weather string must not crash the service."""
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
            "weather": "x" * 100_000,
        }
        df = build_features(payload)
        assert df["weather_code"].iloc[0] == 0


# ─── TC-05: Flat rate fallback price/ETA floor values ─────────────────────────
class TestTC05FlatRateFallback:
    """TC-05: Flat rate fallback must enforce minimum price/ETA floors."""

    def test_zero_distance_price_floor(self):
        """Zero-distance trip still has minimum price of 30."""
        price, eta = _flat_rate(0.0, 1.0)
        assert price == pytest.approx(30.0)

    def test_zero_distance_eta_floor(self):
        """Zero-distance trip still has minimum ETA of 5 minutes."""
        _, eta = _flat_rate(0.0, 1.0)
        assert eta == pytest.approx(5.0)

    def test_normal_trip_above_floor(self):
        """A normal trip (10 km, surge 1.5) should produce price above floor."""
        price, eta = _flat_rate(10.0, 1.5)
        assert price > 30.0
        assert eta > 5.0

    def test_price_scales_linearly_with_distance(self):
        """Doubling distance should double price (above floor)."""
        price_5, _ = _flat_rate(5.0, 1.0)
        price_10, _ = _flat_rate(10.0, 1.0)
        assert price_10 == pytest.approx(price_5 * 2, rel=0.01)


# ─── TC-06: XGBoost model file missing — graceful degradation ─────────────────
class TestTC06ModelFileMissing:
    """TC-06: When model files are absent, predict() must use flat_rate fallback."""

    def test_predict_falls_back_when_model_missing(self):
        """predict() with no model files should return source='flat_rate_fallback'."""
        import inference.model as model_module
        original_price = model_module._price_model
        original_eta = model_module._eta_model

        model_module._price_model = None
        model_module._eta_model = None

        # Also mock the file path to not exist
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
        }

        with patch("os.path.exists", return_value=False):
            result = predict(payload)

        assert result["source"] == "flat_rate_fallback"
        assert result["price"] >= 30.0
        assert result["eta_minutes"] >= 5.0
        assert result["confidence"] == 0.5

        # Restore
        model_module._price_model = original_price
        model_module._eta_model = original_eta


# ─── TC-07: Concurrent inference requests (thread-safety) ─────────────────────
class TestTC07ConcurrentInference:
    """TC-07: Model singleton must be thread-safe under concurrent load."""

    def test_concurrent_build_features(self):
        """100 threads calling build_features simultaneously must all succeed."""
        errors = []
        results = []

        def run():
            try:
                payload = {
                    "pickup_lat": 40.7128, "pickup_lon": -74.006,
                    "dropoff_lat": 40.758, "dropoff_lon": -73.985,
                }
                df = build_features(payload, demand_ratio=1.5)
                results.append(df["distance_km"].iloc[0])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=run) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors in concurrent calls: {errors}"
        assert len(results) == 100
        # All results must be the same
        assert all(abs(r - results[0]) < 1e-9 for r in results)


# ─── TC-08: Invalid timestamp format ──────────────────────────────────────────
class TestTC08InvalidTimestamp:
    """TC-08: Invalid or edge-case timestamps must not crash feature engineering."""

    BASE = {
        "pickup_lat": 40.7128, "pickup_lon": -74.006,
        "dropoff_lat": 40.758, "dropoff_lon": -73.985,
    }

    def test_invalid_timestamp_falls_back_gracefully(self):
        """Garbage timestamp string must fall back to current time, not raise."""
        payload = {**self.BASE, "timestamp": "NOT_A_DATE_AT_ALL"}
        df = build_features(payload)
        assert len(df) == 1
        # hour_sin must still be a valid float
        assert math.isfinite(df["hour_sin"].iloc[0])

    def test_empty_string_timestamp(self):
        payload = {**self.BASE, "timestamp": ""}
        df = build_features(payload)
        assert len(df) == 1

    def test_future_timestamp(self):
        """Far-future timestamp should still produce valid cyclic features."""
        payload = {**self.BASE, "timestamp": "2099-12-31T23:59:59+00:00"}
        df = build_features(payload)
        assert math.isfinite(df["hour_sin"].iloc[0])
        assert math.isfinite(df["hour_cos"].iloc[0])

    def test_epoch_zero_timestamp(self):
        """Unix epoch start (1970-01-01) must be handled correctly."""
        payload = {**self.BASE, "timestamp": "1970-01-01T00:00:00+00:00"}
        df = build_features(payload)
        assert len(df) == 1


# ─── TC-09: Feature column order invariance ────────────────────────────────────
class TestTC09FeatureColumnOrder:
    """TC-09: Output DataFrame must always have features in EXACT FEATURE_COLUMNS order."""

    def test_column_order_matches_spec(self):
        """Column order must exactly match FEATURE_COLUMNS — XGBoost is order-sensitive."""
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
            "weather": "rain",
        }
        df = build_features(payload)
        assert list(df.columns) == FEATURE_COLUMNS, (
            f"Column order mismatch!\n"
            f"Expected: {FEATURE_COLUMNS}\n"
            f"Got:      {list(df.columns)}"
        )

    def test_no_extra_columns(self):
        """build_features must not produce extra columns beyond FEATURE_COLUMNS."""
        payload = {
            "pickup_lat": 40.7128, "pickup_lon": -74.006,
            "dropoff_lat": 40.758, "dropoff_lon": -73.985,
        }
        df = build_features(payload)
        assert set(df.columns) == set(FEATURE_COLUMNS)


# ─── TC-10: Training data integrity check ─────────────────────────────────────
class TestTC10TrainingDataIntegrity:
    """TC-10: Synthetic training CSV must produce valid feature rows for every record."""

    def test_all_training_rows_produce_valid_features(self):
        """Every row in the training CSV must produce a non-NaN feature row."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "nyc_trips.csv")
        if not os.path.exists(csv_path):
            pytest.skip("Training data not available")

        df = pd.read_csv(csv_path, parse_dates=["tpep_pickup_datetime"])
        errors = []
        for idx, row in df.iterrows():
            payload = {
                "pickup_lat": row.get("pickup_latitude", 40.7128),
                "pickup_lon": row.get("pickup_longitude", -74.006),
                "dropoff_lat": row.get("dropoff_latitude", 40.758),
                "dropoff_lon": row.get("dropoff_longitude", -73.985),
                "timestamp": str(row["tpep_pickup_datetime"]),
            }
            feat = build_features(payload)
            if feat.isnull().any().any():
                errors.append(f"Row {idx} produced NaN features")
            for col in FEATURE_COLUMNS:
                val = feat[col].iloc[0]
                if not math.isfinite(val):
                    errors.append(f"Row {idx}, col {col} = {val}")

        assert len(errors) == 0, f"{len(errors)} training rows failed:\n" + "\n".join(errors[:5])

    def test_fare_amounts_all_positive_in_dataset(self):
        """Every fare_amount in the training CSV must be > 0."""
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "nyc_trips.csv")
        if not os.path.exists(csv_path):
            pytest.skip("Training data not available")

        df = pd.read_csv(csv_path)
        assert (df["fare_amount"] > 0).all(), "Some fare_amounts are not positive"
