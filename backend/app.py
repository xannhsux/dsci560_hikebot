"""FastAPI backend for the HikeBot group chat experience."""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict
import json
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from uuid import UUID

from auth_router import router as auth_router
from social_router import router as social_router

from pg_db import fetch_one, fetch_one_returning
from models import AuthUser

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
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="HikeBot Backend")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


app.include_router(auth_router)
app.include_router(social_router) 



# ==================== 全局聊天室 WebSocket（/ws/chat/{username}） ====================

class ChatConnectionManager:
    """简单的全局聊天室：所有在线用户一个房间"""

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


chat_manager = ChatConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    WebSocket 群聊端点（全局大厅）：
    - 浏览器用 ws://localhost:8000/ws/chat/<username> 连接
    - 任意一个人发消息 -> 群里所有人都能看到
    - 同时调用 handle_chat，让 HikeBot 在群里回复
    """
    await chat_manager.connect(websocket, username)
    try:
        # 告知其他人：某用户加入
        join_msg = {
            "sender": "system",
            "role": "system",
            "content": f"{username} joined the chat.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await chat_manager.broadcast_json(join_msg)

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
            await chat_manager.broadcast_json(user_msg)

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
                await chat_manager.broadcast_json(bot_msg)
            except Exception as exc:
                error_msg = {
                    "sender": "system",
                    "role": "system",
                    "content": f"Error from HikeBot: {exc}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await chat_manager.broadcast_json(error_msg)

    except WebSocketDisconnect:
        chat_manager.disconnect(username)
        leave_msg = {
            "sender": "system",
            "role": "system",
            "content": f"{username} left the chat.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await chat_manager.broadcast_json(leave_msg)


# ==================== Routes & trip history ====================

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


# ==================== Weather ====================

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


# ==================== Demo chat HTML ====================

@app.get("/demo-chat", response_class=HTMLResponse)
async def demo_chat():
    html_path = STATIC_DIR / "chat.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Chat demo asset missing.")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ==================== 群聊 WebSocket（按 group 分房间） ====================

class GroupConnectionManager:
    """按 group_id 管理 WebSocket 连接"""

    def __init__(self) -> None:
        # rooms[group_id][user_id] = websocket
        self.rooms: Dict[str, Dict[int, WebSocket]] = {}

    async def connect(self, group_id: str, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(group_id, {})
        self.rooms[group_id][user_id] = websocket

    def disconnect(self, group_id: str, user_id: int):
        if group_id in self.rooms and user_id in self.rooms[group_id]:
            del self.rooms[group_id][user_id]
            if not self.rooms[group_id]:
                del self.rooms[group_id]

    async def broadcast_json(self, group_id: str, message: dict):
        data = json.dumps(message)
        room = self.rooms.get(group_id)
        if not room:
            return
        dead = []
        for uid, ws in list(room.items()):
            try:
                await ws.send_text(data)
            except RuntimeError:
                dead.append(uid)
        for uid in dead:
            self.disconnect(group_id, uid)


group_manager = GroupConnectionManager()


async def _get_user_for_ws(username: str, user_code: str) -> AuthUser | None:
    """
    WebSocket 无法用 FastAPI 的 Depends，我们手动查用户。
    """
    row = fetch_one(
        "SELECT id, username, user_code FROM users WHERE username = %(u)s AND user_code = %(c)s",
        {"u": username, "c": user_code},
    )
    if not row:
        return None
    return AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])


@app.websocket("/ws/groups/{group_id}")
async def group_ws(
    websocket: WebSocket,
    group_id: str,
    username: str,
    user_code: str,
):
    """
    群聊 WebSocket：
    - 前端连接时传：ws://.../ws/groups/{group_id}?username=xxx&user_code=YYY
    - 只允许 group 成员连接
    """
    # 1) 验证用户
    user = await _get_user_for_ws(username, user_code)
    if not user:
        await websocket.close(code=4401)
        return

    # 2) 确认这个用户是 group 成员
    membership = fetch_one(
        """
        SELECT 1 FROM group_members
        WHERE group_id = %(gid)s AND user_id = %(uid)s
        """,
        {"gid": group_id, "uid": user.id},
    )
    if not membership:
        await websocket.close(code=4403)
        return

    # 3) 正式加入房间
    await group_manager.connect(group_id, user.id, websocket)

    try:
        while True:
            text = await websocket.receive_text()

            # 写入数据库
            row = fetch_one_returning(
                """
                INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
                VALUES (%(gid)s, %(uid)s, %(sender)s, 'user', %(content)s)
                RETURNING id, group_id, sender_display AS sender, role, content, created_at
                """,
                {
                    "gid": group_id,
                    "uid": user.id,
                    "sender": user.username,
                    "content": text,
                },
            )

            msg = {
                "id": row["id"],
                "group_id": str(row["group_id"]),
                "sender": row["sender"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            }

            # 只在当前 group 内广播
            await group_manager.broadcast_json(group_id, msg)

    except WebSocketDisconnect:
        group_manager.disconnect(group_id, user.id)
