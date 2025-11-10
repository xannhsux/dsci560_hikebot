"""
Seed data for early development and manual testing.

These records stand in for a real routes table until we connect a database
and GPX catalog. Each entry keeps the metadata our hiking chatbot needs for
filtering and reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, NotRequired, TypedDict

Tag = Literal["dog_friendly", "camping", "water_source", "loop", "summit"]


class SeedRoute(TypedDict):
    id: str
    name: str
    location: str
    distance_km: float
    elevation_gain_m: int
    difficulty: Literal["easy", "moderate", "hard"]
    drive_time_min: int
    tags: List[Tag]
    gpx_url: str
    summary: str
    latitude: NotRequired[float | None]
    longitude: NotRequired[float | None]


DATA_DIR = Path(__file__).resolve().parent / "data"
TRAILFORKS_EXPORT = DATA_DIR / "trailforks_routes.json"


FALLBACK_ROUTES: List[SeedRoute] = [
    {
        "id": "mt-baden-powell",
        "name": "Mount Baden-Powell",
        "location": "Angeles National Forest, CA",
        "distance_km": 15.3,
        "elevation_gain_m": 915,
        "difficulty": "hard",
        "drive_time_min": 110,
        "tags": ["summit", "water_source"],
        "gpx_url": "https://example.com/gpx/baden-powell.gpx",
        "summary": "Switchback-heavy climb to a 9,400 ft summit with sweeping desert views.",
        "latitude": 34.3509,
        "longitude": -117.7603,
    },
    {
        "id": "echo-mountain-loop",
        "name": "Echo Mountain Loop",
        "location": "San Gabriel Mountains, CA",
        "distance_km": 10.1,
        "elevation_gain_m": 550,
        "difficulty": "moderate",
        "drive_time_min": 45,
        "tags": ["loop", "dog_friendly"],
        "gpx_url": "https://example.com/gpx/echo-loop.gpx",
        "summary": "Well-shaded loop with canyon overlooks and mellow grades.",
        "latitude": 34.2043,
        "longitude": -118.1048,
    },
    {
        "id": "san-gorgonio-south-fork",
        "name": "San Gorgonio via South Fork",
        "location": "San Bernardino National Forest, CA",
        "distance_km": 30.0,
        "elevation_gain_m": 1500,
        "difficulty": "hard",
        "drive_time_min": 140,
        "tags": ["camping", "water_source", "summit"],
        "gpx_url": "https://example.com/gpx/san-gorgonio.gpx",
        "summary": "Backpacking classic with reliable creek water and alpine meadows.",
        "latitude": 34.0981,
        "longitude": -116.8256,
    },
    {
        "id": "muir-woods-coastal",
        "name": "Muir Woods Coastal Route",
        "location": "Marin County, CA",
        "distance_km": 12.5,
        "elevation_gain_m": 430,
        "difficulty": "easy",
        "drive_time_min": 35,
        "tags": ["loop", "dog_friendly"],
        "gpx_url": "https://example.com/gpx/muir-coastal.gpx",
        "summary": "Redwood stroll that pops out to ocean cliffs before looping back.",
        "latitude": 37.9026,
        "longitude": -122.5720,
    },
    {
        "id": "donner-ridge-traverse",
        "name": "Donner Ridge Traverse",
        "location": "Lake Tahoe, CA",
        "distance_km": 18.7,
        "elevation_gain_m": 760,
        "difficulty": "moderate",
        "drive_time_min": 210,
        "tags": ["camping", "loop"],
        "gpx_url": "https://example.com/gpx/donner-ridge.gpx",
        "summary": "Roller-coaster ridgeline with granite benches perfect for an overnight.",
        "latitude": 39.3280,
        "longitude": -120.3010,
    },
]


def get_seed_routes() -> List[SeedRoute]:
    """Prefer Trailforks export if present, otherwise ship with fallback fixtures."""
    if TRAILFORKS_EXPORT.exists():
        try:
            payload = json.loads(TRAILFORKS_EXPORT.read_text())
            return list(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Invalid Trailforks export: {TRAILFORKS_EXPORT}") from exc
    return list(FALLBACK_ROUTES)
