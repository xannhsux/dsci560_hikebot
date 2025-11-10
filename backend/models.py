"""Domain models and schemas for the hiking chatbot API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Difficulty = Literal["easy", "moderate", "hard"]
RouteTag = Literal["dog_friendly", "camping", "water_source", "loop", "summit"]


class Route(BaseModel):
    id: str
    name: str
    location: str
    distance_km: float = Field(gt=0)
    elevation_gain_m: int = Field(ge=0)
    difficulty: Difficulty
    drive_time_min: int = Field(ge=0)
    tags: List[RouteTag]
    gpx_url: str
    summary: str


class RouteFilters(BaseModel):
    min_distance_km: Optional[float] = Field(default=None, ge=0)
    max_distance_km: Optional[float] = Field(default=None, ge=0)
    max_elevation_gain_m: Optional[int] = Field(default=None, ge=0)
    difficulty: Optional[Difficulty] = None
    max_drive_time_min: Optional[int] = Field(default=None, ge=0)
    tags: List[RouteTag] = Field(default_factory=list)
    need_water: bool = False
    need_camping: bool = False


class RouteRecommendation(BaseModel):
    route: Route
    match_reasons: List[str]


class RouteRecommendationResponse(BaseModel):
    recommendations: List[RouteRecommendation]


class EventRequest(BaseModel):
    route_id: str
    start_iso: datetime
    meetup_point: str
    organizer: str
    seats_needed: int = Field(ge=0)
    driver_capacity: int = Field(default=0, ge=0)
    difficulty_override: Optional[Difficulty] = None


class EventCard(BaseModel):
    title: str
    schedule: str
    meetup_point: str
    difficulty: Difficulty
    gpx_url: str
    required_equipment: List[str]
    seats_needed: int
    driver_capacity: int
    rsvp_instructions: str


class GearRequest(BaseModel):
    season: Literal["winter", "spring", "summer", "fall"]
    altitude_m: int = Field(ge=0)
    snowpack: bool = False
    trip_hours: int = Field(ge=1)


class GearChecklist(BaseModel):
    checklist: List[str]
    calories_kcal: int
    water_liters: float


class WeatherRequest(BaseModel):
    route_id: str
    start_iso: datetime


class WeatherSnapshot(BaseModel):
    temp_c: float
    precip_probability: float
    lightning_risk: Literal["low", "moderate", "high"]
    fire_risk: Literal["low", "moderate", "high"]
    advisory: str


class SOSRequest(BaseModel):
    route_id: str
    meetup_point: str
    emergency_contact: str
    countdown_minutes: int = Field(gt=0)


class SOSCard(BaseModel):
    ranger_station_phone: str
    emergency_contact: str
    meetup_point: str
    countdown_minutes: int
    coordinates_hint: str


class ChatRequest(BaseModel):
    user_message: str
    filters: Optional[RouteFilters] = None


class ChatResponse(BaseModel):
    reply: str


class UserSignup(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    username: str
    message: str


class TripHistoryEntry(BaseModel):
    trip_name: str
    date: str
    role: str
    status: Literal["completed", "planned"]


class TripHistoryResponse(BaseModel):
    trips: List[TripHistoryEntry]
