"""Route loading helpers that pull from Open-Meteo Hiking Trails (with seed fallback)."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, TypedDict

import seed_routes
from openmeteo_client import fetch_trails

logger = logging.getLogger(__name__)


class RouteRecord(TypedDict, total=False):
    id: str
    name: str
    location: str
    distance_km: float
    elevation_gain_m: int
    difficulty: str
    drive_time_min: int
    tags: List[str]
    gpx_url: str
    summary: str
    latitude: float | None
    longitude: float | None


# Open-Meteo parameters (pull from .env)
TRAIL_LAT = os.getenv("TRAIL_LAT")
TRAIL_LON = os.getenv("TRAIL_LON")
TRAIL_RADIUS_KM = float(os.getenv("TRAIL_RADIUS_KM", "80"))
TRAIL_LIMIT = int(os.getenv("TRAIL_LIMIT", "25"))
# Optional: multiple centers "lat1,lon1;lat2,lon2"
TRAIL_CENTERS = os.getenv("TRAIL_CENTERS")
TRAIL_DIFFICULTY = os.getenv("TRAIL_DIFFICULTY")  # optional filter
OPENMETEO_TRAILS_URL = os.getenv("OPENMETEO_TRAILS_URL", "https://api.open-meteo.com/v1/trails")


def load_routes() -> List[RouteRecord]:
    """Load only built-in seed fixtures (Open-Meteo disabled by request)."""
    logger.info("Using seed routes only (Open-Meteo disabled).")
    return _load_seed_routes()


def _load_openmeteo_routes() -> Optional[List[RouteRecord]]:
    centers: List[tuple[float, float]] = []

    # Preferred: explicit multiple centers
    if TRAIL_CENTERS:
        for chunk in TRAIL_CENTERS.split(";"):
            if not chunk.strip():
                continue
            try:
                lat_str, lon_str = chunk.split(",")
                centers.append((float(lat_str), float(lon_str)))
            except Exception:
                logger.warning("Skipping invalid center '%s' in TRAIL_CENTERS", chunk)

    # Fallback: single center
    if not centers:
        if not TRAIL_LAT or not TRAIL_LON:
            logger.info("Open-Meteo trails not configured (missing TRAIL_LAT/TRAIL_LON).")
            return None
        try:
            centers = [(float(TRAIL_LAT), float(TRAIL_LON))]
        except ValueError:
            logger.warning("Invalid TRAIL_LAT/TRAIL_LON values; cannot query Open-Meteo trails.")
            return None

    aggregated: dict[str, RouteRecord] = {}
    for lat, lon in centers:
        try:
            remote = fetch_trails(
                latitude=lat,
                longitude=lon,
                radius_km=TRAIL_RADIUS_KM,
                limit=TRAIL_LIMIT,
                difficulty=TRAIL_DIFFICULTY,
                base_url=OPENMETEO_TRAILS_URL,
            )
        except Exception as exc:
            logger.warning("Open-Meteo trails unavailable for center (%.4f, %.4f) (%s).", lat, lon, exc)
            continue

        for record in remote or []:
            if not record:
                continue
            aggregated[str(record.get("id"))] = record

    if not aggregated:
        logger.warning("Open-Meteo trails returned no routes.")
        return None

    logger.info("Loaded %s unique routes from Open-Meteo Hiking.", len(aggregated))
    return list(aggregated.values())


def _load_seed_routes() -> List[RouteRecord]:
    payload = seed_routes.get_seed_routes()
    return [RouteRecord(**route) if not isinstance(route, dict) else route for route in payload]
