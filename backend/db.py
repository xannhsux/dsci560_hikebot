"""Lightweight in-memory data helpers used until we wire up a real database."""

from __future__ import annotations

from typing import List, Tuple

import seed_routes
from models import (
    ChatRequest,
    EventCard,
    EventRequest,
    GearChecklist,
    GearRequest,
    Route,
    RouteFilters,
    RouteRecommendation,
    SOSCard,
    SOSRequest,
    WeatherRequest,
    WeatherSnapshot,
)


def load_routes() -> List[Route]:
    """Convert the seed fixtures into Route models."""
    return [Route(**route) for route in seed_routes.get_seed_routes()]


ROUTE_STORE: List[Route] = load_routes()


def _matches_filters(route: Route, filters: RouteFilters) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if filters.min_distance_km and route.distance_km < filters.min_distance_km:
        return False, []
    if filters.max_distance_km and route.distance_km > filters.max_distance_km:
        return False, []
    if filters.max_elevation_gain_m and route.elevation_gain_m > filters.max_elevation_gain_m:
        return False, []
    if filters.max_drive_time_min and route.drive_time_min > filters.max_drive_time_min:
        return False, []
    if filters.difficulty and route.difficulty != filters.difficulty:
        return False, []
    if filters.need_water and "water_source" not in route.tags:
        return False, []
    if filters.need_camping and "camping" not in route.tags:
        return False, []
    if filters.tags and not set(filters.tags).issubset(route.tags):
        return False, []

    if filters.max_distance_km:
        reasons.append(f"Distance {route.distance_km:.1f} km within limit.")
    if filters.max_elevation_gain_m:
        reasons.append(f"Gain {route.elevation_gain_m} m fits climbing cap.")
    if filters.max_drive_time_min:
        reasons.append(f"Drive {route.drive_time_min} min keeps travel manageable.")
    if filters.tags:
        reasons.append(f"Matches tags: {', '.join(filters.tags)}.")
    if filters.need_water and "water_source" in route.tags:
        reasons.append("Reliable water source on route.")
    if filters.need_camping and "camping" in route.tags:
        reasons.append("Camping spots available.")

    if not reasons:
        reasons.append("Good all-around match for unspecified filters.")
    return True, reasons


def recommend_routes(filters: RouteFilters, limit: int = 3) -> List[RouteRecommendation]:
    candidates: List[RouteRecommendation] = []
    for route in ROUTE_STORE:
        ok, reasons = _matches_filters(route, filters)
        if ok:
            candidates.append(RouteRecommendation(route=route, match_reasons=reasons))
    return candidates[:limit]


def generate_event_card(payload: EventRequest) -> EventCard:
    route = next((r for r in ROUTE_STORE if r.id == payload.route_id), None)
    if not route:
        raise ValueError(f"Route {payload.route_id} not found")

    difficulty = payload.difficulty_override or route.difficulty
    required_equipment = ["10 essentials", "map+compass", "charged phone"]
    if route.elevation_gain_m > 800:
        required_equipment.append("trekking poles")
    if "camping" in route.tags:
        required_equipment.append("overnight kit")

    schedule = payload.start_iso.strftime("%a %b %d • %I:%M %p")
    rsvp = (
        f"RSVP to {payload.organizer}. Need {payload.seats_needed} seats;"
        f" driver seats available: {payload.driver_capacity}."
    )

    return EventCard(
        title=f"{route.name} Group Hike",
        schedule=schedule,
        meetup_point=payload.meetup_point,
        difficulty=difficulty,
        gpx_url=route.gpx_url,
        required_equipment=required_equipment,
        seats_needed=payload.seats_needed,
        driver_capacity=payload.driver_capacity,
        rsvp_instructions=rsvp,
    )


def mock_weather_snapshot(payload: WeatherRequest) -> WeatherSnapshot:
    route = next((r for r in ROUTE_STORE if r.id == payload.route_id), None)
    if not route:
        raise ValueError(f"Route {payload.route_id} not found")

    hour = payload.start_iso.hour
    temp = 5 + (hour * 0.5) + (route.elevation_gain_m / 400)
    return WeatherSnapshot(
        temp_c=round(temp, 1),
        precip_probability=0.2,
        lightning_risk="low",
        fire_risk="moderate" if "summer" in route.summary.lower() else "low",
        advisory="Carry layers; expect cooler temps near the summit.",
    )


def build_gear_checklist(request: GearRequest) -> GearChecklist:
    checklist = ["base layers", "insulating mid-layer", "wind shell", "10 essentials"]
    if request.season == "winter" or request.snowpack:
        checklist.append("microspikes")
    if request.altitude_m > 2500:
        checklist.append("extra warm layer")

    calories = int(request.trip_hours * 250)
    water = round(max(2.0, request.trip_hours * 0.5), 1)

    return GearChecklist(checklist=checklist, calories_kcal=calories, water_liters=water)


def build_sos_card(request: SOSRequest) -> SOSCard:
    return SOSCard(
        ranger_station_phone="+1-555-867-5309",
        emergency_contact=request.emergency_contact,
        meetup_point=request.meetup_point,
        countdown_minutes=request.countdown_minutes,
        coordinates_hint="34.35°N, 117.76°W",
    )


def craft_chat_reply(request: ChatRequest) -> str:
    greeting = "Hey trail crew! "
    if request.filters:
        recs = recommend_routes(request.filters)
        if not recs:
            return greeting + "I couldn't find routes that match those filters yet, try loosening one constraint."
        details = ", ".join(r.route.name for r in recs)
        return (
            f"{greeting}Based on what you asked, consider {details}. "
            "Ping /routes/recommendations for the structured card."
        )
    return greeting + "I'm standing by—ask for routes, weather, gear, or safety info to get started."
