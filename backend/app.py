"""FastAPI entrypoint exposing the hiking chatbot scaffolding."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

import db
from models import (
    AuthResponse,
    ChatRequest,
    ChatResponse,
    EventCard,
    EventRequest,
    GearChecklist,
    GearRequest,
    RouteRecommendationResponse,
    RouteFilters,
    SOSCard,
    SOSRequest,
    TripHistoryResponse,
    UserLogin,
    UserSignup,
    WeatherRequest,
    WeatherSnapshot,
)

app = FastAPI(title="HikeBot API", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    reply = db.craft_chat_reply(payload)
    return ChatResponse(reply=reply)


@app.post("/routes/recommendations", response_model=RouteRecommendationResponse)
def route_recommendations(filters: RouteFilters) -> RouteRecommendationResponse:
    recs = db.recommend_routes(filters)
    return RouteRecommendationResponse(recommendations=recs)


@app.post("/events/card", response_model=EventCard)
def create_event_card(payload: EventRequest) -> EventCard:
    try:
        return db.generate_event_card(payload)
    except ValueError as exc:  # pragma: no cover - simple 404 mapping
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/weather/snapshot", response_model=WeatherSnapshot)
def weather_snapshot(payload: WeatherRequest) -> WeatherSnapshot:
    try:
        return db.mock_weather_snapshot(payload)
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/gear/checklist", response_model=GearChecklist)
def gear_checklist(payload: GearRequest) -> GearChecklist:
    return db.build_gear_checklist(payload)


@app.post("/safety/sos-card", response_model=SOSCard)
def sos_card(payload: SOSRequest) -> SOSCard:
    return db.build_sos_card(payload)


@app.post("/auth/signup", response_model=AuthResponse, status_code=201)
def signup(payload: UserSignup) -> AuthResponse:
    try:
        return db.create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin) -> AuthResponse:
    try:
        return db.authenticate_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/users/{username}/trips", response_model=TripHistoryResponse)
def trip_history(username: str) -> TripHistoryResponse:
    return db.get_trip_history(username)
