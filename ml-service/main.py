"""
DynaFare ML Service — Part 7 entry point.

Mounts:
  - REST API: /predict, /health, /metrics
  - MCP tools: /mcp/...
"""

import logging

from fastapi import FastAPI

from inference.model import get_predictor
from mcp.server import mcp_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DynaFare ML Service",
    description="XGBoost inference + MCP tools for real-time dynamic pricing and ETA prediction.",
    version="0.1.0",
)

# ─── Include MCP router ───────────────────────────────────────────────────────
app.include_router(mcp_router, prefix="/mcp")


@app.on_event("startup")
async def startup_event():
    """Pre-load the model at startup so the first request isn't slow."""
    logger.info("Loading XGBoost model...")
    get_predictor()  # warms up the singleton
    logger.info("Model loaded. ML service is ready.")


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok"}


@app.post("/predict", tags=["inference"])
async def predict(payload: dict):
    """
    Raw inference endpoint (called by Spring Boot API service).
    Expected keys: pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                   rider_id (optional), zone_id (optional).
    """
    from inference.model import predict as run_predict
    result = run_predict(payload)
    return result
