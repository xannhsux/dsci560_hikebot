"""Domain models and schemas for the hiking chatbot API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Routes & route recommendations
# -------------------------------------------------------------------

Difficulty = Literal["easy", "moderate", "hard"]
RouteTag = Literal["dog_friendly", "camping", "water_source", "loop", "summit"]


class Route(BaseModel):
    id: str
    name: str
    location: str
    distance_km: float = Field(..., description="Total distance in kilometers")
    elevation_gain_m: int = Field(..., description="Total elevation gain in meters")
    difficulty: Difficulty
    drive_time_min: int = Field(..., description="Approximate driving time from home base")
    tags: List[RouteTag] = []
    summary: Optional[str] = None
    gpx_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RouteFilters(BaseModel):
    max_distance_km: Optional[float] = None
    max_elevation_gain_m: Optional[int] = None
    max_drive_time_min: Optional[int] = None
    difficulty: Optional[Difficulty] = None
    need_dog_friendly: bool = False
    need_camping: bool = False
    need_water: bool = False


class RouteRecommendation(BaseModel):
    route: Route
    score: float
    reasons: List[str]


class RouteRecommendationResponse(BaseModel):
    recommendations: List[RouteRecommendation]


class RouteListResponse(BaseModel):
    routes: List[Route]


# -------------------------------------------------------------------
# Gear checklist
# -------------------------------------------------------------------

class GearRequest(BaseModel):
    season: Literal["spring", "summer", "fall", "winter"]
    hours: float = Field(..., gt=0, description="Planned moving time in hours")
    altitude_band: Literal["low", "mid", "high"] = "low"
    terrain: List[Literal["dry", "snow", "mud", "scramble"]] = []
    distance_km: Optional[float] = None
    elevation_gain_m: Optional[int] = None
    group_size: int = 1


class GearChecklist(BaseModel):
    items: List[str]
    water_liters: float
    calories_kcal: int
    notes: Optional[str] = None


# -------------------------------------------------------------------
# Weather
# -------------------------------------------------------------------

class WeatherRequest(BaseModel):
    """Weather request payload used by the /weather/snapshot endpoint.

    Streamlit 前端发送的是：
        {
            "route_id": "<string>",
            "start_iso": "2025-11-15T20:54:00"
        }
    所以这里字段名就叫 start_iso，Pydantic 才能直接解析。
    """
    route_id: str
    start_iso: datetime


class WeatherSnapshot(BaseModel):
    """Compact weather summary returned to the frontend."""
    summary: str
    temp_c: float
    precip_prob: float
    lightning_risk: Literal["low", "moderate", "high"]
    fire_risk: Literal["low", "moderate", "high"]


# -------------------------------------------------------------------
# SOS card
# -------------------------------------------------------------------

class SOSRequest(BaseModel):
    event_id: Optional[str] = None
    route_id: Optional[str] = None
    notes: Optional[str] = None


class SOSCard(BaseModel):
    event_id: Optional[str] = None
    route_name: Optional[str] = None
    ranger_station: Optional[str] = None
    emergency_numbers: List[str] = []
    last_check_in: Optional[datetime] = None
    countdown_minutes: Optional[int] = None


# -------------------------------------------------------------------
# Events / trips (for future carpool / meetup features)
# -------------------------------------------------------------------

class EventRequest(BaseModel):
    username: str
    route_id: str
    start_time: datetime
    meetup_point: str
    seats_needed: int = 1
    driver_flag: bool = False
    vehicle_capacity: Optional[int] = None
    notes: Optional[str] = None


class EventCard(BaseModel):
    id: str
    route: Route
    start_time: datetime
    meetup_point: str
    organizer: str
    difficulty: Difficulty
    gpx_url: Optional[str] = None
    summary: str


# -------------------------------------------------------------------
# Planning chat (LLM)
# -------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_message: str
    filters: Optional[RouteFilters] = None


class ChatResponse(BaseModel):
    reply: str


class ChatMessage(BaseModel):
    username: str
    user_message: str
    timestamp: datetime


# -------------------------------------------------------------------
# Auth & users (Postgres-backed)
# -------------------------------------------------------------------

class SignupRequest(BaseModel):
    username: str
    password: str
    user_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: int
    username: str
    user_code: str


class AuthResponse(BaseModel):
    user: AuthUser
    message: str


# -------------------------------------------------------------------
# Trip history (for UI sidebar)
# -------------------------------------------------------------------

class TripHistoryEntry(BaseModel):
    trip_name: str
    date: str
    role: str
    status: Literal["completed", "planned"]


class TripHistoryResponse(BaseModel):
    trips: List[TripHistoryEntry]


# -------------------------------------------------------------------
# 老版本：按 route_id 的临时群聊（in-memory db.py 用）
# -------------------------------------------------------------------

class GroupJoinRequest(BaseModel):
    route_id: str
    username: str


class GroupMembersResponse(BaseModel):
    route_id: str
    members: List[str]


class GroupMessage(BaseModel):
    sender: str
    content: str
    timestamp: datetime


class GroupChatPost(BaseModel):
    route_id: str
    username: str
    content: str


class GroupChatResponse(BaseModel):
    route_id: str
    messages: List[GroupMessage]


# -------------------------------------------------------------------
# 新版本：社交好友 + UUID 群组（social_router / Postgres）
# -------------------------------------------------------------------

class FriendAddRequest(BaseModel):
    friend_code: str  # 通过这个 user_code 加好友


class FriendSummary(BaseModel):
    id: int
    username: str
    user_code: str
    

class FriendRequestItem(BaseModel):
    id: int
    from_user_id: int
    from_username: str
    from_user_code: str
    created_at: datetime


class FriendRequestsResponse(BaseModel):
    requests: List[FriendRequestItem]


class FriendAcceptRequest(BaseModel):
    request_id: int





class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

    # 前端传过来的成员列表（好友 + 陌生人），用 user_code 标识
    # 例如：["ABCD1234", "FRIEND5678"]
    members: List[str] = Field(
        default_factory=list,
        description="User codes of initial members (friends or strangers)",
    )

    # 为了兼容你前面可能写过的 payload，如果前端用的是 'member_codes'
    member_codes: List[str] = Field(
        default_factory=list,
        description="Alias of members; merged with 'members'",
    )



class GroupSummary(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime


class GroupMemberInfo(BaseModel):
    id: int
    username: str
    user_code: str
    role: str
    joined_at: datetime


class GroupDetailResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    members: List[GroupMemberInfo]


class GroupMessageModel(BaseModel):
    id: int
    group_id: UUID
    sender: str
    role: str
    content: str
    created_at: datetime


class MessageCreateRequest(BaseModel):
    content: str
