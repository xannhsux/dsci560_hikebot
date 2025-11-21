"""Route loading helpers that optionally hit the Waymarked Trails API."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import seed_routes
from models import Route
from waymarked_client import fetch_routes

logger = logging.getLogger(__name__)

WAYMARKED_API_URL = os.getenv("WAYMARKED_API_URL")
WAYMARKED_THEME = os.getenv("WAYMARKED_THEME", "hiking")
WAYMARKED_LIMIT = int(os.getenv("WAYMARKED_LIMIT", "25"))
WAYMARKED_BBOX = os.getenv("WAYMARKED_BBOX")


def load_routes() -> List[Route]:
    """Load routes from Waymarked Trails when configured, otherwise use local seeds."""
    routes = _load_waymarked_routes()
    if routes:
        return routes

    logger.info("Falling back to built-in seed routes.")
    return _load_seed_routes()


def _load_waymarked_routes() -> Optional[List[Route]]:
    if not WAYMARKED_API_URL:
        return None

    bbox = _parse_bbox(WAYMARKED_BBOX) if WAYMARKED_BBOX else None
    try:
        remote = fetch_routes(
            base_url=WAYMARKED_API_URL,
            theme=WAYMARKED_THEME,
            bbox=bbox,
            limit=WAYMARKED_LIMIT,
        )
    except Exception as exc:
        logger.warning("Waymarked Trails API unavailable (%s).", exc)
        return None

    if not remote:
        logger.warning("Waymarked Trails API returned no routes.")
        return None

    logger.info("Loaded %s routes from Waymarked Trails.", len(remote))
    return [Route(**record) for record in remote]


def _load_seed_routes() -> List[Route]:
    payload = seed_routes.get_seed_routes()
    return [Route(**route) if not isinstance(route, Route) else route for route in payload]


def _parse_bbox(raw: str) -> Optional[List[float]]:
    parts = [segment.strip() for segment in raw.split(",") if segment.strip()]
    if len(parts) != 4:
        logger.warning("Invalid WAYMARKED_BBOX value. Expected four comma-separated numbers.")
        return None
    try:
        return [float(segment) for segment in parts]
    except ValueError:
        logger.warning("WAYMARKED_BBOX contains non-numeric values.")
        return None
