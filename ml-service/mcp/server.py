"""
MCP tool definitions — Part 7.
Exposes get_price_prediction, get_live_demand, get_driver_eta as MCP tools.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

mcp_router = APIRouter(tags=["mcp"])


# ─── Request/Response schemas ─────────────────────────────────────────────────

class PricePredictionRequest(BaseModel):
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    rider_id: str | None = None
    zone_id: str | None = None
    weather: str = "clear"


class DemandRequest(BaseModel):
    zone_id: str


class DriverEtaRequest(BaseModel):
    driver_id: str
    dest_lat: float
    dest_lon: float


# ─── MCP Tools ───────────────────────────────────────────────────────────────

@mcp_router.post("/get_price_prediction")
async def get_price_prediction(req: PricePredictionRequest):
    """
    MCP Tool: get_price_prediction
    Returns price, ETA, surge multiplier, and confidence for a trip.
    """
    from inference.model import predict
    payload = req.model_dump()
    result = predict(payload)
    return result


@mcp_router.post("/get_live_demand")
async def get_live_demand(req: DemandRequest):
    """
    MCP Tool: get_live_demand
    Returns current demand/supply ratio and active driver/rider counts for a zone.
    """
    import redis as redis_lib
    import os

    r = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    try:
        demand_ratio = float(r.get(f"zone:{req.zone_id}:demand_ratio") or 1.0)
        active_drivers = int(r.get(f"zone:{req.zone_id}:active_drivers") or 0)
        pending_riders = int(r.get(f"zone:{req.zone_id}:pending_riders") or 0)
    except Exception as exc:
        logger.warning("Redis error in get_live_demand: %s", exc)
        demand_ratio, active_drivers, pending_riders = 1.0, 0, 0

    return {
        "zone_id": req.zone_id,
        "demand_ratio": demand_ratio,
        "active_drivers": active_drivers,
        "pending_riders": pending_riders,
    }


@mcp_router.post("/get_driver_eta")
async def get_driver_eta(req: DriverEtaRequest):
    """
    MCP Tool: get_driver_eta
    Returns predicted arrival time for a driver to a destination.
    Stub implementation — real version uses the ETA model + live driver location.
    """
    import redis as redis_lib
    import os
    from inference.features import haversine_km

    r = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    try:
        loc = r.hgetall(f"driver:{req.driver_id}:location")
        driver_lat = float(loc.get("lat", req.dest_lat))
        driver_lon = float(loc.get("lon", req.dest_lon))
    except Exception:
        driver_lat, driver_lon = req.dest_lat, req.dest_lon

    distance_km = haversine_km(driver_lat, driver_lon, req.dest_lat, req.dest_lon)
    eta_minutes = round(distance_km * 3.5, 1)

    return {
        "driver_id": req.driver_id,
        "eta_minutes": max(eta_minutes, 2.0),
        "distance_km": round(distance_km, 2),
    }
