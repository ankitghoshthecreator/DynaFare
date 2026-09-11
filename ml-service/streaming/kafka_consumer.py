"""
Kafka consumer — Part 4.
Consumes driver-location-events and demand-events; aggregates per zone into Redis.
"""

import json
import logging
import os
import threading
import time
from collections import defaultdict

import redis
from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger(__name__)

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

DEMAND_TOPIC = "demand-events"
LOCATION_TOPIC = "driver-location-events"
PRICE_UPDATES_TOPIC = "price-updates"


class ZoneAggregator:
    """In-memory sliding window aggregator for demand and driver counts per zone."""

    def __init__(self):
        self._drivers: dict[str, set] = defaultdict(set)   # zone_id -> {driver_ids}
        self._riders: dict[str, int] = defaultdict(int)    # zone_id -> pending count
        self._lock = threading.Lock()

    def update_driver(self, zone_id: str, driver_id: str):
        with self._lock:
            self._drivers[zone_id].add(driver_id)

    def update_demand(self, zone_id: str, delta: int = 1):
        with self._lock:
            self._riders[zone_id] = max(0, self._riders[zone_id] + delta)

    def get_ratio(self, zone_id: str) -> float:
        with self._lock:
            drivers = len(self._drivers.get(zone_id, set()))
            riders = self._riders.get(zone_id, 0)
            if drivers == 0:
                return 3.0  # no drivers = maximum surge
            return round(riders / drivers, 2)

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {
                zone: {
                    "active_drivers": len(self._drivers[zone]),
                    "pending_riders": self._riders[zone],
                    "demand_ratio": self.get_ratio(zone),
                }
                for zone in set(list(self._drivers.keys()) + list(self._riders.keys()))
            }


_aggregator = ZoneAggregator()


def _flush_to_redis(r: redis.Redis, producer: KafkaProducer, last_surge: dict):
    """Push the aggregated zone stats into Redis and publish price updates if surge changes."""
    snapshot = _aggregator.snapshot()
    pipe = r.pipeline()
    for zone_id, stats in snapshot.items():
        pipe.setex(f"zone:{zone_id}:demand_ratio", 30, stats["demand_ratio"])
        pipe.setex(f"zone:{zone_id}:active_drivers", 30, stats["active_drivers"])
        pipe.setex(f"zone:{zone_id}:pending_riders", 30, stats["pending_riders"])
        
        # Calculate surge multiplier based on demand_ratio
        # Simple logic: base 1.0, max 3.0
        ratio = stats["demand_ratio"]
        surge = min(3.0, max(1.0, 1.0 + (ratio - 1.0) * 0.5)) if ratio > 1.0 else 1.0
        surge = round(surge, 2)
        
        # If surge changed by more than 0.1, publish an update
        prev_surge = last_surge.get(zone_id, 1.0)
        if abs(surge - prev_surge) >= 0.1:
            logger.info("Surge changed for %s: %s -> %s", zone_id, prev_surge, surge)
            last_surge[zone_id] = surge
            update_event = {
                "zoneId": zone_id,
                "newSurgeMultiplier": surge,
                "demandRatio": ratio,
                "timestamp": int(time.time() * 1000)
            }
            producer.send(PRICE_UPDATES_TOPIC, key=zone_id.encode('utf-8'), value=update_event)
            
    pipe.execute()
    producer.flush()


def run_consumer():
    """Main consumer loop — blocking, run in a dedicated thread or process."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    consumer = KafkaConsumer(
        DEMAND_TOPIC,
        LOCATION_TOPIC,
        bootstrap_servers=KAFKA_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        group_id="ml-service-consumer",
    )
    
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )
    
    last_surge = {}

    logger.info("Kafka consumer started. Listening on topics: %s, %s", DEMAND_TOPIC, LOCATION_TOPIC)
    flush_counter = 0

    for msg in consumer:
        try:
            topic = msg.topic
            data = msg.value

            if topic == LOCATION_TOPIC:
                _aggregator.update_driver(data.get("zone_id", "unknown"), data["driver_id"])
            elif topic == DEMAND_TOPIC:
                _aggregator.update_demand(data.get("zone_id", "unknown"), data.get("delta", 1))

            flush_counter += 1
            if flush_counter % 10 == 0:   # flush every 10 messages
                _flush_to_redis(r, producer, last_surge)

        except Exception as exc:  # noqa: BLE001
            logger.error("Error processing Kafka message: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_consumer()
