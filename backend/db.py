"""In-memory data helpers for the hiking group chatbot."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional, Tuple

from models import (
    AuthResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    GearChecklist,
    GearRequest,
    Route,
    TripHistoryEntry,
    TripHistoryResponse,
    RouteListResponse,  # 👈 新增
)

from weather_service import get_weather_snapshot, summarize_weather
import seed_routes  # assume you already have this
from models import WeatherRequest, WeatherSnapshot, Route
import seed_routes
import weather_service

def weather_snapshot(payload: WeatherRequest) -> WeatherSnapshot:
    """Return a WeatherSnapshot for the given route id and start time.

    This is called by the /weather/snapshot endpoint. We look up the route
    from the seed fixtures each time to avoid relying on any global state.
    """
    # Rebuild routes from the seed data
    routes = [Route(**route) for route in seed_routes.get_seed_routes()]
    route = next((r for r in routes if r.id == payload.route_id), None)
    if route is None:
        raise ValueError(f"Route {payload.route_id} not found")

    if route.latitude is None or route.longitude is None:
        raise ValueError(f"Route {payload.route_id} has no latitude/longitude")

    # Delegate to the Open-Meteo helper, which already returns a WeatherSnapshot
    return weather_service.get_weather_snapshot(
        route.latitude,
        route.longitude,
        payload.start_iso,
    )


# ---- User store ----


USER_STORE: Dict[str, str] = {}  # username -> password hash
def list_routes() -> RouteListResponse:
    """
    Return all seed routes as a RouteListResponse.
    This is used by the /routes API to feed the frontend.
    """
    return RouteListResponse(routes=ROUTES)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def signup_user(username: str, password: str) -> AuthResponse:
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Username and password are required.")
    if username in USER_STORE:
        raise ValueError("User already exists.")
    USER_STORE[username] = _hash_password(password)
    return AuthResponse(username=username, message="Signup successful.")


def authenticate_user(username: str, password: str) -> AuthResponse:
    username = username.strip().lower()
    stored = USER_STORE.get(username)
    if not stored or stored != _hash_password(password):
        raise ValueError("Invalid username or password.")
    return AuthResponse(username=username, message="Login successful.")


# ---- Routes ----

ROUTES: List[Route] = seed_routes.get_seed_routes()


def basic_route_recommendation() -> Optional[Route]:
    """Very simple route selector: just pick the first seed route."""
    return ROUTES[0] if ROUTES else None


# ---- Trip & chat state ----

@dataclass
class TripState:
    route: Route
    trip_name: str
    date: Optional[date]
    meet_time: Optional[time]
    meet_point: Optional[str]
    organizer: Optional[str]
    participants: List[str]


CHAT_HISTORY: Dict[str, List[ChatMessage]] = {}       # session_id -> messages
SESSION_TRIP_STATE: Dict[str, TripState] = {}         # session_id -> TripState
TRIP_HISTORY: Dict[str, List[TripHistoryEntry]] = {}  # username -> trips


def record_chat_message(session_id: str, msg: ChatMessage) -> None:
    CHAT_HISTORY.setdefault(session_id, []).append(msg)


def get_recent_human_messages(session_id: str, n: int = 6) -> List[ChatMessage]:
    history = CHAT_HISTORY.get(session_id, [])
    human = [m for m in history if m.role == "user"]
    return human[-n:]


# ---- Gear logic (simple rule-based) ----

def build_gear_checklist(req: GearRequest) -> GearChecklist:
    items: List[str] = [
        "Backpack",
        "Water (at least 1.5–2L per person)",
        "Snacks / light lunch",
        "Phone with charged battery",
        "Basic first-aid kit",
    ]

    season = (req.season or "").lower()
    difficulty = req.difficulty

    if "summer" in season or "hot" in season:
        items.extend(["Hat", "Sunscreen", "Sunglasses"])
    if "winter" in season or "cold" in season:
        items.extend(["Insulated jacket", "Warm base layer", "Gloves", "Beanie"])

    if difficulty == "hard":
        items.extend(["Trekking poles", "Extra water", "Electrolyte tablets"])

    if not req.has_water:
        items.append("Extra water (no water source on the trail)")

    return GearChecklist(items=items)


# ---- Intent and confirmation detection ----

CONFIRM_WORDS = ["let us go with", "let's go with", "we choose", "we will take", "we pick", "we go with"]


def detect_confirmation(last_message: ChatMessage, session_id: str) -> bool:
    """Very simple confirmation detector."""
    text = last_message.content.lower()
    if any(w in text for w in CONFIRM_WORDS):
        return True

    # also accept short messages like "ok second one", "let's do it"
    if "second one" in text or "that one" in text or "let's do it" in text:
        return True

    return False


# ---- Announcement generation ----

def generate_announcement_text(session_id: str, username: str) -> str:
    state = SESSION_TRIP_STATE.get(session_id)
    if not state:
        route = basic_route_recommendation()
        if not route:
            return "I tried to generate a trip announcement, but I do not have a selected route yet."
        state = TripState(
            route=route,
            trip_name=f"Hike to {route.name}",
            date=None,
            meet_time=None,
            meet_point=None,
            organizer=username,
            participants=[username],
        )
        SESSION_TRIP_STATE[session_id] = state

    route = state.route
    weather_record = get_weather_snapshot(route.lat, route.lon, route.name)
    weather_summary = summarize_weather(weather_record) if weather_record else None

    trip_date_str = state.date.isoformat() if state.date else "[Date not set]"
    meet_time_str = state.meet_time.isoformat() if state.meet_time else "[Time not set]"
    meet_point_str = state.meet_point or "[Meeting point not set]"

    announcement = f"""📢 Trip Announcement

Group: {session_id}
Destination: **{route.name}**
Date: {trip_date_str}
Meet time: {meet_time_str}
Meeting point: {meet_point_str}
Organizer: {state.organizer or username}
Participants (so far): {", ".join(state.participants) if state.participants else username}

---

### 🏞 Route overview

- Distance: {route.distance_km:.1f} km
- Elevation gain: {route.elevation_gain_m} m
- Estimated hiking time: {route.drive_time_min // 30 * 1.5:.1f} hours (rough guess)
- Driving time (one way): {route.drive_time_min} minutes
- Difficulty: {route.difficulty}

Short description:
> {route.description or "No detailed description available yet."}
"""

    if weather_summary:
        announcement += f"""

---

### 🌤 Weather (NOAA-based snapshot)

- Temperature: {weather_summary.temp_c:.1f}°C
- Precipitation probability: {weather_summary.precip_probability * 100:.0f}%
- Lightning risk: {weather_summary.lightning_risk}
- Fire risk: {weather_summary.fire_risk}
- Advisory: {weather_summary.advisory}
"""

    if weather_record:
        clothing = weather_record.get("clothing_recommendation", "")
        hiking_conditions = weather_record.get("hiking_conditions", "")
        safety_notes = weather_record.get("safety_notes", "")

        announcement += f"""

---

### 🎒 Clothing recommendation

{clothing or "No specific clothing recommendation extracted."}

---

### 🚶 Hiking conditions

{hiking_conditions or "No specific hiking conditions extracted."}

---

### ⚠️ Safety notes

{safety_notes or "No specific warnings."}
"""

    announcement += """

Please update the group and @HikeBot if the plan changes or if you need to cancel the trip.
"""

    # log into trip history for the organizer
    TRIP_HISTORY.setdefault(username, []).append(
        TripHistoryEntry(
            trip_name=state.trip_name,
            date=trip_date_str,
            role="organizer",
            status="planned",
        )
    )

    return announcement


# ---- Core chat handler ----

# ---- Core chat handler ----

def handle_chat(req: ChatRequest) -> ChatResponse:
    """Simple chat handler that works with the current ChatRequest(user_message, filters)."""

    text = (req.user_message or "").strip()
    lower = text.lower()

    if not text:
        return ChatResponse(reply="I didn't catch that. Try asking about trails, weather, or gear 🙂")

    # 1) 路线相关问题
    if any(word in lower for word in ["trail", "route", "hike", "where should we go", "去哪", "路线", "哪条"]):
        route = basic_route_recommendation()
        if not route:
            return ChatResponse(
                reply="I tried to find a route but I don't have any routes in my database yet."
            )

        reply = (
            "It sounds like you're deciding where to hike.\n\n"
            f"I recommend **{route.name}** near {route.location}.\n\n"
            f"- Distance: {route.distance_km:.1f} km\n"
            f"- Elevation gain: {route.elevation_gain_m} m\n"
            f"- Driving time: ~{route.drive_time_min} minutes\n"
            f"- Difficulty: {route.difficulty}\n\n"
            "You can also use the **Weather Snapshot** panel on the right to get a detailed forecast "
            "for this trail at your planned start time."
        )
        return ChatResponse(reply=reply)

    # 2) 装备 / 打包相关
    if any(word in lower for word in ["gear", "pack", "bring", "背什么", "带什么", "装备"]):
        # 简单假设是夏季 5 小时中等难度日间徒步
        gear_req = GearRequest(
            season="summer",
            hours=5,
            altitude_band="mid",
            terrain=["dry"],
            distance_km=10.0,
            elevation_gain_m=600,
            group_size=3,
        )
        checklist = build_gear_checklist(gear_req)
        lines = "\n".join(f"- {item}" for item in checklist.items)

        reply = (
            "Here's a basic packing checklist for a typical day hike:\n\n"
            f"{lines}\n\n"
            "Always adjust for your specific route, weather, and group experience."
        )
        return ChatResponse(reply=reply)

    # 3) 天气相关
    if any(word in lower for word in ["weather", "forecast", "下雨", "雷电", "风大"]):
        reply = (
            "For detailed weather, use the **Weather Snapshot** panel on the right:\n"
            "1. Pick a route.\n"
            "2. Choose your start date & time.\n"
            "3. Click *Get forecast* to see temperature, rain probability, and safety notes.\n"
        )
        return ChatResponse(reply=reply)

    # 4) 默认兜底介绍
    reply = (
        "I'm HikeBot 🥾. I can help your group with:\n"
        "- Suggesting a trail (try: *Where should we hike this weekend?*)\n"
        "- Packing lists (try: *What gear do we need?*)\n"
        "- Weather safety (try: *How's the weather for hiking?*)\n"
    )
    return ChatResponse(reply=reply)

    

def get_trip_history_for_user(username: str) -> TripHistoryResponse:
    records = TRIP_HISTORY.get(username.lower(), [])
    return TripHistoryResponse(trips=records)
