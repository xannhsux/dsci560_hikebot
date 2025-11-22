# backend/social_router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID


from pg_db import fetch_one, fetch_all, execute, fetch_one_returning
from models import (
    AuthUser,
    FriendAddRequest,
    FriendSummary,
    GroupCreateRequest,
    GroupSummary,
    GroupDetailResponse,
    GroupMemberInfo,
    GroupMessageModel,
    MessageCreateRequest,
)
from auth_router import get_current_user
import os
import requests

router = APIRouter(prefix="/social", tags=["social"])
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ---------- 好友 ----------

@router.post("/friends/add", response_model=FriendSummary)
def add_friend(payload: FriendAddRequest, current: AuthUser = Depends(get_current_user)) -> FriendSummary:
    # 找到这个 friend_code 对应的用户
    friend = fetch_one(
        "SELECT id, username, user_code FROM users WHERE user_code = %(code)s",
        {"code": payload.friend_code},
    )
    if not friend:
        raise HTTPException(404, "User not found")
    if friend["id"] == current.id:
        raise HTTPException(400, "Cannot add yourself")

    # 双向好友关系（插入前检查）
    for (u, f) in [(current.id, friend["id"]), (friend["id"], current.id)]:
        exists = fetch_one(
            "SELECT id FROM friendships WHERE user_id = %(u)s AND friend_id = %(f)s",
            {"u": u, "f": f},
        )
        if not exists:
            execute(
                """
                INSERT INTO friendships (user_id, friend_id)
                VALUES (%(u)s, %(f)s)
                """,
                {"u": u, "f": f},
            )

    return FriendSummary(id=friend["id"], username=friend["username"], user_code=friend["user_code"])


@router.get("/friends", response_model=List[FriendSummary])
def list_friends(current: AuthUser = Depends(get_current_user)) -> List[FriendSummary]:
    rows = fetch_all(
        """
        SELECT u.id, u.username, u.user_code
        FROM friendships fs
        JOIN users u ON u.id = fs.friend_id
        WHERE fs.user_id = %(uid)s
        ORDER BY u.username
        """,
        {"uid": current.id},
    )
    return [FriendSummary(**r) for r in rows]


# ---------- Groups ----------

@router.post("/groups", response_model=GroupSummary)
def create_group(payload: GroupCreateRequest, current: AuthUser = Depends(get_current_user)) -> GroupSummary:
    row = fetch_one_returning(
        """
        INSERT INTO groups (name, description, created_by)
        VALUES (%(name)s, %(desc)s, %(uid)s)
        RETURNING id, name, description, created_at
        """,
        {"name": payload.name, "desc": payload.description, "uid": current.id},
    )

    # 创建者自动成为 owner
    execute(
        """
        INSERT INTO group_members (group_id, user_id, role)
        VALUES (%(gid)s, %(uid)s, 'owner')
        """,
        {"gid": row["id"], "uid": current.id},
    )

    return GroupSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
    )


@router.get("/groups", response_model=List[GroupSummary])
def list_my_groups(current: AuthUser = Depends(get_current_user)) -> List[GroupSummary]:
    rows = fetch_all(
        """
        SELECT g.id, g.name, g.description, g.created_at
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = %(uid)s
        ORDER BY g.created_at DESC
        """,
        {"uid": current.id},
    )
    return [GroupSummary(**r) for r in rows]


@router.get("/groups/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(group_id: UUID, current: AuthUser = Depends(get_current_user)) -> GroupDetailResponse:
    group = fetch_one(
        "SELECT id, name, description, created_at FROM groups WHERE id = %(gid)s",
        {"gid": str(group_id)},
    )
    if not group:
        raise HTTPException(404, "Group not found")

    # 必须是成员才能看详情
    member = fetch_one(
        "SELECT role FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    members = fetch_all(
        """
        SELECT gm.user_id AS id, u.username, u.user_code, gm.role, gm.joined_at
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %(gid)s
        ORDER BY gm.joined_at
        """,
        {"gid": str(group_id)},
    )

    return GroupDetailResponse(
        id=group["id"],
        name=group["name"],
        description=group["description"],
        created_at=group["created_at"],
        members=[GroupMemberInfo(**m) for m in members],
    )


# 通过好友 ID 把好友拉入 group
@router.post("/groups/{group_id}/add_friend", response_model=GroupDetailResponse)
def add_friend_to_group(
    group_id: UUID,
    payload: FriendAddRequest,
    current: AuthUser = Depends(get_current_user),
) -> GroupDetailResponse:
    # 1) 当前用户必须是这个 group 的 owner
    gm = fetch_one(
        """
        SELECT role FROM group_members
        WHERE group_id = %(gid)s AND user_id = %(uid)s
        """,
        {"gid": str(group_id), "uid": current.id},
    )
    if not gm or gm["role"] != "owner":
        raise HTTPException(403, "Only owner can invite to this group")

    # 2) 通过 friend_code 找到用户 & 确认真的是好友
    friend = fetch_one(
        "SELECT id, username, user_code FROM users WHERE user_code = %(code)s",
        {"code": payload.friend_code},
    )
    if not friend:
        raise HTTPException(404, "User not found")

    rel = fetch_one(
        """
        SELECT 1 FROM friendships
        WHERE user_id = %(u)s AND friend_id = %(f)s
        """,
        {"u": current.id, "f": friend["id"]},
    )
    if not rel:
        raise HTTPException(400, "You can only invite your friends")

    # 3) 加入 group_members（如果不在的话）
    exists = fetch_one(
        """
        SELECT 1 FROM group_members
        WHERE group_id = %(gid)s AND user_id = %(uid)s
        """,
        {"gid": str(group_id), "uid": friend["id"]},
    )
    if not exists:
        execute(
            """
            INSERT INTO group_members (group_id, user_id, role)
            VALUES (%(gid)s, %(uid)s, 'member')
            """,
            {"gid": str(group_id), "uid": friend["id"]},
        )

    # 返回最新 group 详情
    return get_group_detail(group_id, current)


# ---------- Group 消息（HTTP 版群聊） ----------

@router.get("/groups/{group_id}/messages", response_model=List[GroupMessageModel])
def list_group_messages(
    group_id: UUID,
    limit: int = 50,
    current: AuthUser = Depends(get_current_user),
) -> List[GroupMessageModel]:
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    rows = fetch_all(
        """
        SELECT id, group_id, sender_display AS sender, role, content, created_at
        FROM group_messages
        WHERE group_id = %(gid)s
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """,
        {"gid": str(group_id), "limit": limit},
    )
    rows.reverse()
    return [GroupMessageModel(**r) for r in rows]


@router.post("/groups/{group_id}/messages", response_model=GroupMessageModel)
def create_group_message(
    group_id: UUID,
    payload: MessageCreateRequest,
    current: AuthUser = Depends(get_current_user),
) -> GroupMessageModel:
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    row = fetch_one_returning(
        """
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
        VALUES (%(gid)s, %(uid)s, %(sender)s, 'user', %(content)s)
        RETURNING id, group_id, sender_display AS sender, role, content, created_at
        """,
        {
            "gid": str(group_id),
            "uid": current.id,
            "sender": current.username,
            "content": payload.content,
        },
    )
    return GroupMessageModel(**row)

# ---------- 群内 AI：自动推荐路线 ----------

def _infer_simple_filters_from_group(group_id: UUID) -> dict:
    """
    临时简单版：从 group 里取一点信息，先返回一个固定过滤条件。
    之后你可以根据 group_members / 历史消息做更智能的规则或 LLM 推理。
    """
    # TODO: 这里可以改成根据 group_members 表里的数据来算
    # 比如：max_distance = 所有成员 max_distance_km 的中位数
    # 现在先用一个安全的默认值，方便你先跑通：
    return {
        "max_distance_km": 15,
        "max_drive_time_min": 120,
        "need_water": True,
    }


@router.post("/groups/{group_id}/ai/recommend_routes", response_model=GroupMessageModel)
def ai_recommend_routes(
    group_id: UUID,
    current: AuthUser = Depends(get_current_user),
) -> GroupMessageModel:
    # 1) 确认当前用户是这个 group 的成员
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    # 2) 简单从 group 推断过滤条件（之后可以升级成真正 "看聊天 + 经验"）
    filters = _infer_simple_filters_from_group(group_id)

    # 3) 调用你原来的 /routes/recommendations 接口
    try:
        resp = requests.post(
            f"{BACKEND_URL}/routes/recommendations",
            json=filters,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        # 如果路由接口挂了，我们在群里发一个错误提示
        error_text = f"⚠️ HikeBot AI 调路线推荐失败：{exc}"
        row = fetch_one_returning(
            """
            INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
            VALUES (%(gid)s, NULL, 'HikeBot AI', 'assistant', %(content)s)
            RETURNING id, group_id, sender_display AS sender, role, content, created_at
            """,
            {
                "gid": str(group_id),
                "content": error_text,
            },
        )
        return GroupMessageModel(**row)

    routes = data.get("routes") or []

    if not routes:
        ai_text = "🤖 我没有找到特别合适的路线，可能是过滤条件太严格了，可以试试放宽一点距离或爬升。"
    else:
        # 4) 把推荐的 routes 转成一段人类可读的文案
        lines = ["🤖 根据大家的偏好，我推荐几条路线给你们讨论：", ""]
        for idx, r in enumerate(routes[:3], start=1):
            name = r.get("name", "某条路线")
            dist = r.get("distance_km")
            gain = r.get("elevation_gain_m")
            diff = r.get("difficulty", "unknown")
            # 组一行简介
            parts = [f"{idx}. {name}"]
            if dist is not None:
                parts.append(f"{dist:.1f} km")
            if gain is not None:
                parts.append(f"爬升 {int(gain)} m")
            parts.append(f"难度 {diff}")
            lines.append(" - " + " · ".join(parts))
        lines.append("")
        lines.append("你们可以在群里聊聊更偏向哪一条，如果需要我也可以帮你们再缩小范围～")
        ai_text = "\n".join(lines)

    # 5) 把 AI 的结果写成一条群消息（assistant）
    row = fetch_one_returning(
        """
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
        VALUES (%(gid)s, NULL, 'HikeBot AI', 'assistant', %(content)s)
        RETURNING id, group_id, sender_display AS sender, role, content, created_at
        """,
        {
            "gid": str(group_id),
            "content": ai_text,
        },
    )

    # （可选）如果你想让 AI 消息通过 WebSocket 实时推送，
    # 可以在这里调用 manager.broadcast_json，但 manager 定义在 app.py 里，
    # 我们之后可以再加一个小 hook 把它暴露出来。

    return GroupMessageModel(**row)

# ---------- List members (simple string list) ----------

@router.get("/groups/{group_id}/members", response_model=List[str])
def list_group_members(
    group_id: UUID,
    current: AuthUser = Depends(get_current_user),
) -> List[str]:
    # Check membership first
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    rows = fetch_all(
        """
        SELECT u.username
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %(gid)s
        ORDER BY u.username
        """,
        {"gid": str(group_id)},
    )
    return [r["username"] for r in rows]  # → ["alice", "bob"]


# ---------- Join group ----------

@router.post("/groups/{group_id}/join", response_model=List[str])
def join_group(
    group_id: UUID,
    current: AuthUser = Depends(get_current_user),
) -> List[str]:

    # Check if already joined
    exists = fetch_one(
        """
        SELECT 1 FROM group_members
        WHERE group_id = %(gid)s AND user_id = %(uid)s
        """,
        {"gid": str(group_id), "uid": current.id},
    )
    if not exists:
        execute(
            """
            INSERT INTO group_members (group_id, user_id, role)
            VALUES (%(gid)s, %(uid)s, 'member')
            """,
            {"gid": str(group_id), "uid": current.id},
        )

    # Return updated member list
    rows = fetch_all(
        """
        SELECT u.username
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %(gid)s
        ORDER BY u.username
        """,
        {"gid": str(group_id)},
    )
    return [r["username"] for r in rows]


# ---------- Leave group ----------

@router.post("/groups/{group_id}/leave", response_model=List[str])
def leave_group(
    group_id: UUID,
    current: AuthUser = Depends(get_current_user),
) -> List[str]:

    # Remove from group_members
    execute(
        """
        DELETE FROM group_members
        WHERE group_id = %(gid)s AND user_id = %(uid)s
        """,
        {"gid": str(group_id), "uid": current.id},
    )

    # Return updated list
    rows = fetch_all(
        """
        SELECT u.username
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %(gid)s
        ORDER BY u.username
        """,
        {"gid": str(group_id)},
    )
    return [r["username"] for r in rows]


