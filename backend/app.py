"""FastAPI backend for the HikeBot group chat experience."""

from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect
from typing import Dict
import json
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware  # 👈 加这一行
from pathlib import Path

from models import (
    AuthResponse,
    ChatRequest,
    ChatResponse,
    GroupChatPost,
    GroupChatResponse,
    GroupJoinRequest,
    GroupMembersResponse,
    RouteListResponse,
    TripHistoryResponse,
    UserLogin,
    UserSignup,
    WeatherRequest,
    WeatherSnapshot,
)
import db
from db import (
    authenticate_user,
    get_group_chat,
    get_trip_history_for_user,
    handle_chat,
    join_route_group,
    leave_route_group,
    list_group_members,
    list_routes,
    post_group_chat,
    signup_user,
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="HikeBot Backend")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")



class ConnectionManager:
    def __init__(self) -> None:
        # username -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str) -> None:
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str) -> None:
        self.active_connections.pop(username, None)

    async def broadcast_json(self, message: Dict[str, str]) -> None:
        """广播消息给所有在线连接."""
        data = json.dumps(message)
        for ws in list(self.active_connections.values()):
            try:
                await ws.send_text(data)
            except RuntimeError:
                # 某些连接挂了，简单跳过
                continue


manager = ConnectionManager()


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


@app.websocket("/ws/chat/{username}")
async def websocket_chat(websocket: WebSocket, username: str):
    """
    WebSocket 群聊端点：
    - 浏览器用 ws://localhost:8000/ws/chat/<username> 连接
    - 任意一个人发消息 -> 群里所有人都能看到
    - 同时调用 handle_chat，让 HikeBot 在群里回复
    """
    await manager.connect(websocket, username)
    try:
        # 告知其他人：某用户加入
        join_msg = {
            "sender": "system",
            "role": "system",
            "content": f"{username} joined the chat.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.broadcast_json(join_msg)

        while True:
            # 等待前端发来的文本消息（纯文本）
            text = await websocket.receive_text()

            # 1）先把该用户的消息广播出去
            user_msg = {
                "sender": username,
                "role": "user",
                "content": text,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await manager.broadcast_json(user_msg)

            # 2）调用已有的 handle_chat，让 HikeBot 在群里也回复
            try:
                chat_req = ChatRequest(user_message=text)
                chat_resp: ChatResponse = handle_chat(chat_req)
                bot_msg = {
                    "sender": "HikeBot",
                    "role": "assistant",
                    "content": chat_resp.reply,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await manager.broadcast_json(bot_msg)
            except Exception as exc:
                error_msg = {
                    "sender": "system",
                    "role": "system",
                    "content": f"Error from HikeBot: {exc}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await manager.broadcast_json(error_msg)

    except WebSocketDisconnect:
        manager.disconnect(username)
        leave_msg = {
            "sender": "system",
            "role": "system",
            "content": f"{username} left the chat.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.broadcast_json(leave_msg)



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


@app.post("/groups/join", response_model=GroupMembersResponse)
def join_group(payload: GroupJoinRequest) -> GroupMembersResponse:
    try:
        members = join_route_group(payload.route_id, payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GroupMembersResponse(route_id=payload.route_id, members=members)


@app.post("/groups/leave", response_model=GroupMembersResponse)
def leave_group(payload: GroupJoinRequest) -> GroupMembersResponse:
    try:
        members = leave_route_group(payload.route_id, payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GroupMembersResponse(route_id=payload.route_id, members=members)


@app.get("/groups/{route_id}/members", response_model=GroupMembersResponse)
def group_members(route_id: str) -> GroupMembersResponse:
    try:
        members = list_group_members(route_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return GroupMembersResponse(route_id=route_id, members=members)


@app.get("/groups/{route_id}/messages", response_model=GroupChatResponse)
def group_messages(route_id: str) -> GroupChatResponse:
    try:
        messages = get_group_chat(route_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return GroupChatResponse(route_id=route_id, messages=messages)


@app.post("/groups/message", response_model=GroupChatResponse)
def post_group_message(payload: GroupChatPost) -> GroupChatResponse:
    try:
        messages = post_group_chat(payload.route_id, payload.username, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GroupChatResponse(route_id=payload.route_id, messages=messages)


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
    
@app.get("/demo-chat", response_class=HTMLResponse)
async def demo_chat():
    html_path = STATIC_DIR / "chat.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Chat demo asset missing.")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))
