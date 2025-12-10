"""Lightweight client for the Open-Meteo Hiking Trails API."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx


logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.open-meteo.com/v1/trails"


def fetch_trails(
    *,
    latitude: float,
    longitude: float,
    radius_km: float = 80.0,
    limit: int = 25,
    difficulty: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 20.0,
) -> List[Dict[str, Any]]:
    """
    Fetch hiking trails near a coordinate using Open-Meteo's trails endpoint.

    The API is tolerant to missing fields; we normalize results into a common shape.
    """
    params: Dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "distance": radius_km,
        "count": limit,
    }
    if difficulty:
        params["difficulty"] = difficulty

    with httpx.Client(timeout=timeout) as client:
        response = client.get(base_url.rstrip("/"), params=params)
        response.raise_for_status()
        payload = response.json()

    records = _extract_records(payload)
    normalized = [_normalize_trail(record) for record in records]
    return [trail for trail in normalized if trail is not None]


def _extract_records(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("trails"), list):
            return payload["trails"]
        if isinstance(payload.get("results"), list):
            return payload["results"]
    if isinstance(payload, list):
        return payload
    return []


def _normalize_trail(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trail_id = raw.get("id") or raw.get("identifier") or raw.get("osm_id") or raw.get("uuid")
    name = raw.get("name") or raw.get("title")
    if not name:
        return None

    distance_km = _extract_distance_km(raw)
    elevation_gain_m = _extract_elevation_gain_m(raw)
    difficulty = _map_difficulty(raw.get("difficulty") or raw.get("grade"))
    location = raw.get("region") or raw.get("area") or raw.get("country") or "Unknown"
    summary = raw.get("description") or raw.get("summary") or ""
    latitude, longitude = _extract_coordinates(raw)
    tags = _extract_tags(raw.get("tags"))

    return {
        "id": str(trail_id or name),
        "name": str(name),
        "location": str(location),
        "distance_km": distance_km,
        "elevation_gain_m": elevation_gain_m,
        "difficulty": difficulty,
        "drive_time_min": raw.get("drive_time_min") or 0,
        "tags": tags,
        "gpx_url": raw.get("gpx_url") or raw.get("url") or "",
        "summary": summary,
        "latitude": latitude,
        "longitude": longitude,
    }


def _extract_distance_km(raw: Dict[str, Any]) -> float:
    for key in ("distance_km", "length_km", "distance", "length"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    meters = raw.get("distance_m") or raw.get("length_m")
    if meters is not None:
        try:
            return float(meters) / 1000.0
        except (TypeError, ValueError):
            pass
    return 0.0


def _extract_elevation_gain_m(raw: Dict[str, Any]) -> int:
    for key in ("elevation_gain_m", "ascent", "climb", "elevation_gain"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def _map_difficulty(value: Any) -> str:
    val = str(value or "").lower()
    if not val:
        return "moderate"
    if val in {"easy", "grade1", "t1"}:
        return "easy"
    if val in {"hard", "difficult", "grade5", "t4", "t5", "t6"}:
        return "hard"
    return "moderate"


def _extract_tags(raw_tags: Any) -> List[str]:
    if not raw_tags:
        return []
    if isinstance(raw_tags, dict):
        raw_iter: Iterable[Any] = raw_tags.keys()
    elif isinstance(raw_tags, list):
        raw_iter = raw_tags
    else:
        raw_iter = []

    tags: List[str] = []
    for tag in raw_iter:
        t = str(tag).lower()
        if "dog" in t:
            tags.append("dog_friendly")
        elif "camp" in t or "tent" in t:
            tags.append("camping")
        elif "water" in t:
            tags.append("water_source")
        elif "loop" in t or "circuit" in t:
            tags.append("loop")
        elif "summit" in t or "peak" in t:
            tags.append("summit")
    return list(dict.fromkeys(tags))


def _extract_coordinates(raw: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    lat = raw.get("latitude") or raw.get("lat")
    lon = raw.get("longitude") or raw.get("lon")
    if _is_number(lat) and _is_number(lon):
        return float(lat), float(lon)

    center = raw.get("center") or raw.get("coordinate") or raw.get("coords")
    if isinstance(center, Sequence) and len(center) >= 2 and _is_number(center[1]) and _is_number(center[0]):
        return float(center[1]), float(center[0])

    return None, None


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
