# backend/app.py

import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- Routers ---
from auth_router import router as auth_router
from social_router import router as social_router

# --- DB & Models ---
from db import SessionLocal
from pg_db import fetch_one, fetch_one_returning
from models import AuthUser, ChatRequest, ChatResponse

# --- AI Service ---
from auto_planner_service import AutoPlannerService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="HikeBot Backend")

# 挂载静态文件 (用于测试页或图片)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 挂载核心路由
app.include_router(auth_router)
app.include_router(social_router)

# CORS (允许前端跨域)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================
#                 WebSocket Manager (Group Chat)
# ==============================================================

class GroupConnectionManager:
    """Manages WebSocket connections per group_id."""

    def __init__(self) -> None:
        # rooms[group_id][user_id] = websocket
        self.rooms: Dict[str, Dict[int, WebSocket]] = {}

    async def connect(self, group_id: str, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(group_id, {})
        self.rooms[group_id][user_id] = websocket
        logger.info(f"User {user_id} connected to Group {group_id}")

    def disconnect(self, group_id: str, user_id: int):
        if group_id in self.rooms and user_id in self.rooms[group_id]:
            del self.rooms[group_id][user_id]
            if not self.rooms[group_id]:
                del self.rooms[group_id]

    async def broadcast_json(self, group_id: str, message: dict):
        """Push a JSON message to everyone in the group."""
        data = json.dumps(message)
        room = self.rooms.get(group_id)
        if not room:
            return
        
        dead_users = []
        for uid, ws in list(room.items()):
            try:
                await ws.send_text(data)
            except RuntimeError:
                dead_users.append(uid)
        
        for uid in dead_users:
            self.disconnect(group_id, uid)

group_manager = GroupConnectionManager()

# ==============================================================
#                Helper: AI Pipeline Runner
# ==============================================================

async def run_ai_pipeline_for_ws(group_id: str, user_content: str):
    """
    Runs the AI Logic in the background. 
    If AI generates a response, we broadcast it back to the WebSocket immediately.
    """
    # 1. Create a transient DB session
    db = SessionLocal()
    try:
        planner = AutoPlannerService(db)
        
        # 2. Run the logic (Intent -> DB Match -> Weather -> Generate -> Save to DB)
        # Note: run_pipeline saves the message to DB but returns None
        await planner.run_pipeline(chat_id=group_id, user_message=user_content)
        
        # 3. Check if AI posted a message just now (The "Poll" Trick)
        # Since run_pipeline saves to DB, we fetch the latest message from 'HikeBot' 
        # created in the last 2 seconds.
        row = fetch_one(
            """
            SELECT id, group_id, sender_display, role, content, created_at 
            FROM group_messages 
            WHERE group_id = %(gid)s AND role = 'assistant' AND sender_display = 'HikeBot'
            ORDER BY created_at DESC LIMIT 1
            """,
            {"gid": group_id}
        )
        
        if row:
            # Simple heuristic: Only broadcast if it's brand new (created < 3s ago)
            time_diff = (datetime.utcnow() - row["created_at"]).total_seconds()
            if time_diff < 5:
                ai_msg = {
                    "id": row["id"],
                    "group_id": str(row["group_id"]),
                    "sender": row["sender_display"],
                    "role": row["role"],
                    "content": row["content"], # This contains the JSON card
                    "created_at": row["created_at"].isoformat(),
                }
                # 🔥 Push to Frontend!
                await group_manager.broadcast_json(group_id, ai_msg)
                
    except Exception as e:
        logger.error(f"AI WebSocket Error: {e}")
    finally:
        db.close()

# ==============================================================
#                    WebSocket Endpoint
# ==============================================================

async def _get_user_for_ws(username: str, user_code: str) -> Optional[AuthUser]:
    """Validate user credentials for WS connection."""
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
    Real-time Group Chat + AI Observer
    URL: ws://localhost:8000/ws/groups/{uuid}?username=...&user_code=...
    """
    # 1. Auth Check
    user = await _get_user_for_ws(username, user_code)
    if not user:
        await websocket.close(code=4401) # Unauthorized
        return

    # 2. Membership Check
    membership = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": group_id, "uid": user.id},
    )
    if not membership:
        await websocket.close(code=4403) # Forbidden
        return

    # 3. Connect
    await group_manager.connect(group_id, user.id, websocket)

    try:
        while True:
            # Await User Message
            text = await websocket.receive_text()

            # A. Save User Message to DB
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

            # B. Broadcast User Message to Group
            msg_payload = {
                "id": row["id"],
                "group_id": str(row["group_id"]),
                "sender": row["sender"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            }
            await group_manager.broadcast_json(group_id, msg_payload)

            # C. Trigger AI in Background (Non-blocking)
            # This is the magic: user keeps typing, AI thinks in parallel
            asyncio.create_task(run_ai_pipeline_for_ws(group_id, text))

    except WebSocketDisconnect:
        group_manager.disconnect(group_id, user.id)


# ==============================================================
#                  Legacy / Global Chat (Optional)
# ==============================================================
# Kept for backward compatibility if you still use the "Global Hall"
@app.get("/demo-chat", response_class=HTMLResponse)
async def demo_chat():
    html_path = STATIC_DIR / "chat.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Demo Chat File Missing</h1>")