"""FastAPI backend for the HikeBot group chat experience."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Body

from fastapi.middleware.cors import CORSMiddleware

from models import (
    AuthResponse,
    ChatRequest,
    ChatResponse,
    TripHistoryResponse,
    UserLogin,
    UserSignup,
    RouteListResponse,
    WeatherRequest,
    WeatherSnapshot,
)
import db
from db import (
    authenticate_user,
    get_trip_history_for_user,
    handle_chat,
    signup_user,
    list_routes,
)

app = FastAPI(title="HikeBot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Auth --------

@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: UserSignup) -> AuthResponse:
    try:
        return signup_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin) -> AuthResponse:
    try:
        return authenticate_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


# -------- Chat --------

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Main group-chat endpoint.
    """
    return handle_chat(req)


# -------- Routes & trip history --------

@app.get("/routes", response_model=RouteListResponse)
def get_routes() -> RouteListResponse:
    """
    Used by Streamlit weather tool.
    """
    return list_routes()


# 原来的历史接口
@app.get("/trips/history/{username}", response_model=TripHistoryResponse)
def trip_history(username: str) -> TripHistoryResponse:
    return get_trip_history_for_user(username)


# 兼容前端调用的 /users/{username}/trips
@app.get("/users/{username}/trips", response_model=TripHistoryResponse)
def user_trips(username: str) -> TripHistoryResponse:
    return get_trip_history_for_user(username)


from models import WeatherRequest, WeatherSnapshot
import db

@app.post("/weather/snapshot", response_model=WeatherSnapshot)
def weather_snapshot_endpoint(payload: WeatherRequest) -> WeatherSnapshot:
    """
    Body JSON:
    {
      "route_id": "<string>",
      "start_iso": "2025-11-15T20:54:00"
    }
    """
    try:
        return db.weather_snapshot(payload)
    except ValueError as exc:
        # 找不到路线 / 天气拿不到
        raise HTTPException(status_code=404, detail=str(exc))
