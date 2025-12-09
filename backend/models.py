# backend/models.py (请完全覆盖)
from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

# ==========================================
# 1. Core Models
# ==========================================

class AuthUser(BaseModel):
    id: int
    username: str
    user_code: str

class SignupRequest(BaseModel):
    username: str
    password: str
    user_code: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    user: AuthUser
    message: str

class Route(BaseModel):
    id: str | int
    name: str
    location: str
    distance_km: float
    elevation_gain_m: int
    difficulty: str
    drive_time_min: int
    tags: List[str] = []
    summary: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gpx_path: Optional[str] = None 

class RouteListResponse(BaseModel):
    routes: List[Route]

class WeatherRequest(BaseModel):
    route_id: str
    start_iso: datetime

class WeatherSnapshot(BaseModel):
    summary: str
    temp_c: float
    precip_prob: float
    lightning_risk: str
    fire_risk: str

class ChatRequest(BaseModel):
    user_message: str
    filters: Optional[Dict[str, Any]] = None 

class ChatResponse(BaseModel):
    reply: str

class ChatMessage(BaseModel): 
    role: str
    content: str
    timestamp: datetime = datetime.now()
    username: Optional[str] = None
    user_message: Optional[str] = None

class FriendAddRequest(BaseModel):
    friend_code: str

# 🟢 新增：删除好友请求模型
class RemoveFriendRequest(BaseModel):
    friend_id: int

class FriendSummary(BaseModel):
    id: int
    username: str
    user_code: str
    display_name: Optional[str] = None

class FriendRequestItem(BaseModel):
    id: int
    from_user_id: int
    from_username: str
    from_user_code: str
    created_at: datetime

class FriendRequestsResponse(BaseModel):
    requests: List[FriendRequestItem]

class FriendAcceptRequest(BaseModel):
    request_id: int | str

class DMRequest(BaseModel):
    friend_id: int

# --- Groups ---

class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    member_codes: List[str] = []

class GroupSummary(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime

class GroupMemberInfo(BaseModel):
    user_id: int
    username: str
    user_code: str
    role: str

class GroupMessageModel(BaseModel):
    id: int
    group_id: UUID
    sender: str
    role: str
    content: str
    created_at: datetime

class MessageCreateRequest(BaseModel):
    content: str

class InviteRequest(BaseModel):
    friend_code: str

class KickRequest(BaseModel):
    user_id: int

class AnnounceRequest(BaseModel):
    route_id: str

# ==========================================
# 2. Legacy Models (Keep for compatibility)
# ==========================================
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
class TripHistoryEntry(BaseModel):
    trip_name: str
    date: str
    role: str
    status: str
class TripHistoryResponse(BaseModel):
    trips: List[TripHistoryEntry]
class GearRequest(BaseModel):
    season: str
    hours: float = 0
    altitude_band: str = "low"
    terrain: List[str] = []
    distance_km: Optional[float] = None
    elevation_gain_m: Optional[int] = None
    group_size: int = 1
    difficulty: Optional[str] = None 
    has_water: bool = True 
class GearChecklist(BaseModel):
    items: List[str]
    water_liters: float = 0.0
    calories_kcal: int = 0
    notes: Optional[str] = None