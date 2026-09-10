"""Tests for ml-service — Part 13."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import ClassVar

import pytest

from inference.features import build_features, cyclic_encode, haversine_km


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self):
        # NYC to roughly 1 degree north (~111 km)
        dist = haversine_km(40.0, -74.0, 41.0, -74.0)
        assert 110 < dist < 112

    def test_symmetry(self):
        a = haversine_km(40.0, -74.0, 40.7, -73.9)
        b = haversine_km(40.7, -73.9, 40.0, -74.0)
        assert abs(a - b) < 1e-9


class TestCyclicEncode:
    def test_midnight_and_noon_differ(self):
        s0, c0 = cyclic_encode(0, 24)
        s12, c12 = cyclic_encode(12, 24)
        assert abs(s0) < 1e-9   # sin(0) = 0
        assert abs(s12) < 1e-9  # sin(pi) ≈ 0
        assert c0 == pytest.approx(1.0)
        assert c12 == pytest.approx(-1.0)


class TestBuildFeatures:
    BASE_PAYLOAD: ClassVar[dict] = {
        "pickup_lat": 40.7128,
        "pickup_lon": -74.0060,
        "dropoff_lat": 40.7580,
        "dropoff_lon": -73.9855,
    }

    def test_returns_dataframe_with_one_row(self):
        df = build_features(self.BASE_PAYLOAD)
        assert len(df) == 1

    def test_distance_is_positive(self):
        df = build_features(self.BASE_PAYLOAD)
        assert df["distance_km"].iloc[0] > 0

    def test_demand_ratio_flows_through(self):
        df = build_features(self.BASE_PAYLOAD, demand_ratio=2.5)
        assert df["demand_ratio"].iloc[0] == 2.5

    def test_weather_code_clear(self):
        df = build_features({**self.BASE_PAYLOAD, "weather": "clear"})
        assert df["weather_code"].iloc[0] == 0

    def test_weather_code_rain(self):
        df = build_features({**self.BASE_PAYLOAD, "weather": "rain"})
        assert df["weather_code"].iloc[0] == 1
