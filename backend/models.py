# backend/models.py

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# 引入我们在 db.py 里定义的 Base
from db import Base

# ==========================================
# 1. SQLAlchemy Models (数据库表定义)
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    user_code = Column(String, unique=True)
    password_hash = Column(String) 

class Trail(Base):
    __tablename__ = "trails"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    length_km = Column(Float)
    elevation_gain_m = Column(Integer)
    difficulty_rating = Column(Float)
    latitude = Column(Float)
    longitude = Column(Float)
    features = Column(String)

class GroupMessage(Base):
    __tablename__ = "group_messages"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, index=True) 
    user_id = Column(Integer, nullable=True)
    sender_display = Column(String)
    role = Column(String, default="user") 
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    forecast_date = Column(DateTime)
    data = Column(Text) # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# 2. Pydantic Models (API 请求/响应 Schema)
# ==========================================

# --- Auth 相关 (匹配 auth_router.py) ---

class AuthUser(BaseModel):
    id: int
    username: str
    user_code: str

class SignupRequest(BaseModel):
    username: str
    password: str
    user_code: str 
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    user: AuthUser
    message: str

# --- Chat 相关 (匹配 app.py) ---

class ChatRequest(BaseModel):
    user_message: str

class ChatResponse(BaseModel):
    response: str

# --- Social & Group 相关 (匹配 social_router.py) ---

class GroupMessageModel(BaseModel):
    id: int
    group_id: str
    sender: str
    role: str
    content: str
    created_at: Optional[datetime] = None

class MessageCreateRequest(BaseModel):
    content: str

class FriendSummary(BaseModel):
    id: int
    username: str
    user_code: str

class FriendAddRequest(BaseModel):
    friend_code: str

class FriendRequestItem(BaseModel):
    id: int
    from_user_id: int
    from_username: str
    from_user_code: str
    created_at: datetime

class FriendRequestsResponse(BaseModel):
    pass 

class FriendAcceptRequest(BaseModel):
    request_id: int

class RemoveFriendRequest(BaseModel):
    friend_id: int

class DMRequest(BaseModel):
    friend_id: int

class GroupSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime

class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    member_codes: List[str] = []

class GroupMemberInfo(BaseModel):
    user_id: int
    username: str
    user_code: str
    role: str

class InviteRequest(BaseModel):
    friend_code: str

class KickRequest(BaseModel):
    user_id: int