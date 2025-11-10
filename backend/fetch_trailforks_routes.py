"""
Utility script to pull trail metadata from the Trailforks v1 API and
convert it into the seed structure consumed by our FastAPI service.

Usage:
    python fetch_trailforks_routes.py --region-id 12345 --limit 25
Requires the environment variable TRAILFORKS_API_KEY to be set.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = DATA_DIR / "trailforks_routes.json"
TRAILFORKS_API = "https://www.trailforks.com/api/1/trails"

DIFFICULTY_MAP = {
    "1": "easy",
    "2": "moderate",
    "3": "hard",
    "4": "hard",
    "5": "hard",
}


def fetch_trails(api_key: str, region_id: int, limit: int) -> List[Dict[str, Any]]:
    params = {
        "api_key": api_key,
        "scope": "region",
        "id": region_id,
        "rows": limit,
        "order": "score",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(TRAILFORKS_API, params=params)
        response.raise_for_status()
        payload = response.json()
    trails = payload.get("data", {}).get("trails")
    if trails is None and "trails" in payload:
        trails = payload["trails"]
    if not trails:
        raise RuntimeError("Trailforks response did not include any trails.")
    return trails


def _bool_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return False


def normalize_trail(trail: Dict[str, Any], default_drive_time: int) -> Dict[str, Any]:
    distance_km = float(trail.get("distance") or 0)
    if not distance_km and trail.get("distance_miles"):
        distance_km = float(trail["distance_miles"]) * 1.60934

    elevation_gain = int(
        trail.get("elevation_gain")
        or trail.get("uphill")
        or trail.get("climb")
        or 0
    )

    difficulty_code = str(trail.get("difficulty") or trail.get("difficulty_rating") or "")
    difficulty = DIFFICULTY_MAP.get(difficulty_code, "moderate")

    tags: List[str] = []
    if _bool_flag(trail.get("dogs_allowed")):
        tags.append("dog_friendly")
    if _bool_flag(trail.get("camping")):
        tags.append("camping")
    if _bool_flag(trail.get("water")) or _bool_flag(trail.get("water_source")):
        tags.append("water_source")
    if _bool_flag(trail.get("loop")):
        tags.append("loop")
    if _bool_flag(trail.get("summit")):
        tags.append("summit")

    lat_raw = trail.get("lat") or trail.get("latitude")
    lon_raw = trail.get("lon") or trail.get("lng") or trail.get("longitude")
    latitude = float(lat_raw) if lat_raw not in (None, "") else None
    longitude = float(lon_raw) if lon_raw not in (None, "") else None

    return {
        "id": str(trail.get("trailid") or trail.get("id")),
        "name": trail.get("title") or trail.get("name") or "Unnamed Trail",
        "location": trail.get("region") or trail.get("city") or "Unknown",
        "distance_km": round(distance_km, 2),
        "elevation_gain_m": elevation_gain,
        "difficulty": difficulty,
        "drive_time_min": int(trail.get("drive_time_min") or default_drive_time),
        "tags": tags,
        "gpx_url": trail.get("gpx_url") or trail.get("url") or "",
        "summary": trail.get("desc") or trail.get("summary") or "",
        "latitude": latitude,
        "longitude": longitude,
    }


def write_routes(routes: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(routes, indent=2))
    print(f"Wrote {len(routes)} routes to {OUTPUT_FILE}")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch routes from Trailforks.")
    parser.add_argument("--region-id", type=int, required=True, help="Trailforks region id.")
    parser.add_argument("--limit", type=int, default=25, help="How many records to fetch.")
    parser.add_argument(
        "--default-drive-time",
        type=int,
        default=90,
        help="Fallback drive time (minutes) when API omits the value.",
    )
    args = parser.parse_args()

    api_key = os.getenv("TRAILFORKS_API_KEY")
    if not api_key:
        raise RuntimeError("TRAILFORKS_API_KEY is not set in the environment.")

    raw_trails = fetch_trails(api_key, args.region_id, args.limit)
    normalized = [
        normalize_trail(trail, args.default_drive_time) for trail in raw_trails
    ]
    write_routes(normalized)


if __name__ == "__main__":
    main()
