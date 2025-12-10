# backend/social_router.py

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

# --- Internal Imports ---
from auth_router import get_current_user
from pg_db import fetch_all, fetch_one, fetch_one_returning, execute, get_cursor
from db import get_db  # 需要确保 backend/db.py 存在并提供 get_db 依赖
from models import (
    AuthUser, FriendAddRequest, FriendRequestsResponse, FriendRequestItem, FriendAcceptRequest, FriendSummary,
    GroupCreateRequest, GroupSummary, GroupMemberInfo, GroupMessageModel, MessageCreateRequest,
    DMRequest, InviteRequest, KickRequest, RemoveFriendRequest
)

# --- AI Services ---
import ai_service
from auto_planner_service import AutoPlannerService  # 引入新的自动规划服务

router = APIRouter(prefix="/social", tags=["social"])

# --- Friends ---
@router.get("/friends", response_model=Dict[str, List[FriendSummary]])
def list_friends(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT u.id, u.username, u.user_code FROM friendships f JOIN users u ON f.friend_id = u.id WHERE f.user_id = %(me)s", {"me": u.id})
    return {"friends": [FriendSummary(**row) for row in rows]}

@router.post("/friends/add", response_model=Dict[str, Any])
def add_friend(p: FriendAddRequest, u: AuthUser = Depends(get_current_user)):
    target = fetch_one("SELECT id, username FROM users WHERE user_code = %(code)s", {"code": p.friend_code})
    if not target: raise HTTPException(404, "User not found")
    if target["id"] == u.id: raise HTTPException(400, "Cannot add self")
    existing = fetch_one("SELECT id FROM friend_requests WHERE (from_user_id=%(me)s AND to_user_id=%(t)s) OR (from_user_id=%(t)s AND to_user_id=%(me)s)", {"me": u.id, "t": target["id"]})
    if existing: return {"message": "Exists"}
    execute("INSERT INTO friend_requests (from_user_id, to_user_id, status) VALUES (%(me)s, %(t)s, 'pending')", {"me": u.id, "t": target["id"]})
    return {"message": "Sent", "username": target["username"]}

@router.get("/friends/requests", response_model=Dict[str, List[FriendRequestItem]])
def get_friend_requests(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT r.id, r.from_user_id, u.username as from_username, u.user_code as from_user_code, r.created_at FROM friend_requests r JOIN users u ON r.from_user_id = u.id WHERE r.to_user_id = %(me)s AND r.status = 'pending'", {"me": u.id})
    return {"requests": [FriendRequestItem(**r) for r in rows]}

@router.post("/friends/accept", response_model=Dict[str, Any])
def accept_friend(p: FriendAcceptRequest, u: AuthUser = Depends(get_current_user)):
    rid = int(p.request_id)
    req = fetch_one("SELECT * FROM friend_requests WHERE id=%(rid)s AND to_user_id=%(me)s", {"rid": rid, "me": u.id})
    if not req: raise HTTPException(404, "Not found")
    with get_cursor() as cur:
        cur.execute("UPDATE friend_requests SET status='accepted' WHERE id=%(rid)s", {"rid": rid})
        cur.execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(u)s, %(f)s) ON CONFLICT DO NOTHING", {"u": u.id, "f": req["from_user_id"]})
        cur.execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(f)s, %(u)s) ON CONFLICT DO NOTHING", {"u": u.id, "f": req["from_user_id"]})
    return {"message": "Accepted"}

@router.post("/friends/remove", response_model=Dict[str, Any])
def remove_friend(p: RemoveFriendRequest, u: AuthUser = Depends(get_current_user)):
    execute(
        "DELETE FROM friendships WHERE (user_id=%(u)s AND friend_id=%(f)s) OR (user_id=%(f)s AND friend_id=%(u)s)",
        {"u": u.id, "f": p.friend_id}
    )
    return {"message": "Friend removed"}

@router.post("/friends/dm", response_model=Dict[str, Any])
def get_or_create_dm(p: DMRequest, u: AuthUser = Depends(get_current_user)):
    if p.friend_id == u.id: raise HTTPException(400, "Cannot DM self")
    existing = fetch_one("""SELECT g.id FROM groups g JOIN group_members gm1 ON g.id=gm1.group_id JOIN group_members gm2 ON g.id=gm2.group_id WHERE gm1.user_id=%(me)s AND gm2.user_id=%(f)s AND g.name LIKE 'DM:%%' LIMIT 1""", {"me": u.id, "f": p.friend_id})
    if existing: return {"group_id": existing["id"], "new": False}
    friend = fetch_one("SELECT username FROM users WHERE id=%(id)s", {"id": p.friend_id})
    if not friend: raise HTTPException(404, "Friend not found")
    dm_name = f"DM: {u.username} & {friend['username']}"
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, 'DM', %(u)s) RETURNING id", {"n": dm_name, "u": u.id})["id"]
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": p.friend_id})
    return {"group_id": gid, "new": True}

# --- GROUPS ---
@router.get("/groups", response_model=Dict[str, List[GroupSummary]])
def list_groups(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT g.id, g.name, g.description, g.created_at FROM groups g JOIN group_members gm ON g.id=gm.group_id WHERE gm.user_id=%(u)s ORDER BY g.created_at DESC", {"u": u.id})
    return {"groups": [GroupSummary(**r) for r in rows]}

@router.post("/groups", response_model=Dict[str, Any])
def create_group(p: GroupCreateRequest, u: AuthUser = Depends(get_current_user)):
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, %(d)s, %(u)s) RETURNING id", {"n": p.name, "d": p.description, "u": u.id})["id"]
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    if p.member_codes:
        codes = list(set(p.member_codes))
        plc = ",".join(["%s"]*len(codes))
        users = fetch_all(f"SELECT id FROM users WHERE user_code IN ({plc})", codes)
        for user in users:
            if user["id"] != u.id:
                execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'member') ON CONFLICT DO NOTHING", {"gid": gid, "u": user["id"]})
    return {"message": "Created", "group_id": gid}

@router.get("/groups/{group_id}/members", response_model=Dict[str, List[GroupMemberInfo]])
def get_members(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT u.id as user_id, u.username, u.user_code, gm.role FROM group_members gm JOIN users u ON gm.user_id=u.id WHERE gm.group_id=%(gid)s", {"gid": str(group_id)})
    return {"members": [GroupMemberInfo(**r) for r in rows]}

@router.post("/groups/{group_id}/invite")
def invite_member(group_id: UUID, p: InviteRequest, u: AuthUser = Depends(get_current_user)):
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, (SELECT id FROM users WHERE user_code=%(c)s), 'member') ON CONFLICT DO NOTHING", {"gid": str(group_id), "c": p.friend_code})
    return {"message": "Invited"}

@router.post("/groups/{group_id}/kick")
def kick_member(group_id: UUID, p: KickRequest, u: AuthUser = Depends(get_current_user)):
    me = fetch_one("SELECT role FROM group_members WHERE group_id=%(gid)s AND user_id=%(uid)s", {"gid": str(group_id), "uid": u.id})
    if not me or me["role"] != "admin": raise HTTPException(403, "Admin only")
    if p.user_id == u.id: raise HTTPException(400, "Cannot kick self")
    execute("DELETE FROM group_members WHERE group_id=%(gid)s AND user_id=%(uid)s", {"gid": str(group_id), "uid": p.user_id})
    return {"message": "Kicked"}

@router.post("/groups/{group_id}/leave")
def leave_group(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    execute("DELETE FROM group_members WHERE group_id=%(gid)s AND user_id=%(u)s", {"gid": str(group_id), "u": u.id})
    return {"message": "Left"}

@router.post("/groups/{group_id}/join")
def join_group(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'member') ON CONFLICT DO NOTHING", {"gid": str(group_id), "u": u.id})
    return {"message": "Joined"}

@router.get("/groups/{group_id}/messages", response_model=Dict[str, List[GroupMessageModel]])
def get_msgs(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT id, group_id, sender_display as sender, role, content, created_at FROM group_messages WHERE group_id=%(gid)s ORDER BY created_at ASC LIMIT 100", {"gid": str(group_id)})
    return {"messages": [GroupMessageModel(**r) for r in rows]}

@router.post("/groups/{group_id}/messages", response_model=GroupMessageModel)
def send_msg(
    group_id: UUID, 
    p: MessageCreateRequest, 
    background_tasks: BackgroundTasks,  # <--- 新增：后台任务
    u: AuthUser = Depends(get_current_user),
    db_session: Session = Depends(get_db) # <--- 新增：获取 Session 供 AI Service 使用
):
    # 1. 快速写入数据库 (使用 pg_db raw sql)
    r = fetch_one_returning(
        "INSERT INTO group_messages (group_id, user_id, sender_display, role, content) VALUES (%(gid)s, %(u)s, %(s)s, 'user', %(c)s) RETURNING id, group_id, sender_display as sender, role, content, created_at",
        {"gid": str(group_id), "u": u.id, "s": u.username, "c": p.content}
    )

    # 2. 触发后台 AI 观察者 (Auto Planner)
    # 实例化 AutoPlannerService
    planner = AutoPlannerService(db_session)
    
    # 异步执行 Pipeline：分析意图 -> 模糊匹配 -> 查天气 -> 生成公告
    # 注意：我们传递 str(group_id) 和用户消息内容
    background_tasks.add_task(
        planner.run_pipeline, 
        chat_id=str(group_id), # 传递 String 类型的 UUID
        user_message=p.content
    )

    return GroupMessageModel(**r)

# --- AI (Manual Triggers) ---
@router.post("/groups/{group_id}/ai/recommend_routes")
def ai_recommend(group_id: UUID, u: AuthUser=Depends(get_current_user)):
    return ai_service.generate_route_suggestions(str(group_id))

@router.post("/groups/{group_id}/ai/generate_plan")
def ai_generate_plan(group_id: UUID, u: AuthUser=Depends(get_current_user)):
    return ai_service.generate_trip_plan(str(group_id))