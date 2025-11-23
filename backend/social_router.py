# backend/social_router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from uuid import UUID


from pg_db import fetch_one, fetch_all, execute, fetch_one_returning
from models import (
    AuthUser,
    FriendAddRequest,
    FriendSummary,
    FriendRequestsResponse,
    FriendAcceptRequest,
    GroupCreateRequest,
    GroupSummary,
    GroupDetailResponse,
    GroupMemberInfo,
    GroupMessageModel,
    MessageCreateRequest,
)
from auth_router import get_current_user
from db import list_routes
import os
import requests

router = APIRouter(prefix="/social", tags=["social"])
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ---------- 好友 ----------

@router.get("/friends", response_model=List[FriendSummary])
def list_friends(current: AuthUser = Depends(get_current_user)) -> List[FriendSummary]:
    """
    返回当前用户的好友列表。
    """
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



def _ensure_friendship_pair(user_id: int, friend_id: int) -> None:
    """
    确保 user_id 和 friend_id 之间在 friendships 表中是双向关系。
    已存在就跳过，不存在就插入。
    """
    for (u, f) in [(user_id, friend_id), (friend_id, user_id)]:
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

@router.post("/friends/add", response_model=FriendSummary)
def add_friend(payload: FriendAddRequest, current: AuthUser = Depends(get_current_user)) -> FriendSummary:
    """
    发送好友请求：
    - 如果对方不存在：404
    - 如果是自己：400
    - 如果已经是好友：400
    - 如果对方已经向你发过 pending 请求：自动接受（直接变好友）
    - 否则：插入一条新的 pending friend_requests 记录
    """
    # 通过 friend_code 找到对方
    friend = fetch_one(
        "SELECT id, username, user_code FROM users WHERE user_code = %(code)s",
        {"code": payload.friend_code},
    )
    if not friend:
        raise HTTPException(404, "User not found")

    if friend["id"] == current.id:
        raise HTTPException(400, "Cannot add yourself")

    # 已经是好友？
    existing_friendship = fetch_one(
        """
        SELECT id FROM friendships
        WHERE user_id = %(u)s AND friend_id = %(f)s
        """,
        {"u": current.id, "f": friend["id"]},
    )
    if existing_friendship:
        raise HTTPException(400, "You are already friends")

    # 是否已经存在 pending 请求（包括两种方向）
    existing_req = fetch_one(
        """
        SELECT id, from_user_id, to_user_id, status
        FROM friend_requests
        WHERE
          (
            (from_user_id = %(u)s AND to_user_id = %(f)s)
            OR
            (from_user_id = %(f)s AND to_user_id = %(u)s)
          )
          AND status = 'pending'
        """,
        {"u": current.id, "f": friend["id"]},
    )

    # 对方已经发给你 pending 请求：那这次 add 直接视为 "接受"
    if existing_req and existing_req["from_user_id"] == friend["id"] and existing_req["to_user_id"] == current.id:
        _ensure_friendship_pair(current.id, friend["id"])
        execute(
            """
            UPDATE friend_requests
            SET status = 'accepted', responded_at = NOW()
            WHERE
              (
                (from_user_id = %(u)s AND to_user_id = %(f)s)
                OR
                (from_user_id = %(f)s AND to_user_id = %(u)s)
              )
              AND status = 'pending'
            """,
            {"u": current.id, "f": friend["id"]},
        )
        return FriendSummary(id=friend["id"], username=friend["username"], user_code=friend["user_code"])

    # 已经有 pending 请求（自己已经发过或者两边奇怪状态）
    if existing_req:
        raise HTTPException(400, "Friend request already pending")

    # 插入新的 pending 请求
    execute(
        """
        INSERT INTO friend_requests (from_user_id, to_user_id, status)
        VALUES (%(from_id)s, %(to_id)s, 'pending')
        """,
        {"from_id": current.id, "to_id": friend["id"]},
    )

    # 前端已经有 UI 展示 pending，所以直接返回对方的基本信息就好
    return FriendSummary(
        id=friend["id"],
        username=friend["username"],
        user_code=friend["user_code"],
    )


@router.get("/friends/requests", response_model=FriendRequestsResponse)
def get_friend_requests(
    current: AuthUser = Depends(get_current_user),
    username: str | None = None,  # 为了兼容前端传 ?username=xxx，但实际不用
) -> FriendRequestsResponse:
    """
    返回当前用户收到的所有 pending 好友请求。
    """
    rows = fetch_all(
        """
        SELECT
            fr.id,
            fr.from_user_id,
            u.username AS from_username,
            u.user_code AS from_user_code,
            fr.created_at
        FROM friend_requests fr
        JOIN users u ON u.id = fr.from_user_id
        WHERE fr.to_user_id = %(uid)s
          AND fr.status = 'pending'
        ORDER BY fr.created_at DESC
        """,
        {"uid": current.id},
    )

    requests = [
        {
            "id": r["id"],
            "from_user_id": r["from_user_id"],
            "from_username": r["from_username"],
            "from_user_code": r["from_user_code"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    return FriendRequestsResponse(requests=requests)
@router.post("/friends/accept")
def accept_friend_request(
    payload: FriendAcceptRequest,
    current: AuthUser = Depends(get_current_user),
):
    """
    接受一条好友请求：
    - 只能接受发给自己的 pending 请求
    - 接受后写入 friendships（双向）
    - 将 friend_requests 这一对的 pending 记录标记为 accepted
    """
    req = fetch_one(
        """
        SELECT id, from_user_id, to_user_id, status
        FROM friend_requests
        WHERE id = %(rid)s
        """,
        {"rid": payload.request_id},
    )

    if not req:
        raise HTTPException(404, "Friend request not found")

    if req["to_user_id"] != current.id:
        raise HTTPException(403, "You cannot accept this request")

    if req["status"] != "pending":
        raise HTTPException(400, "Request is not pending")

    from_id = req["from_user_id"]
    to_id = req["to_user_id"]

    # 建立双向好友关系
    _ensure_friendship_pair(from_id, to_id)

    # 把这对用户之间所有 pending 请求都标为 accepted
    execute(
        """
        UPDATE friend_requests
        SET status = 'accepted', responded_at = NOW()
        WHERE
          (
            (from_user_id = %(u)s AND to_user_id = %(f)s)
            OR
            (from_user_id = %(f)s AND to_user_id = %(u)s)
          )
          AND status = 'pending'
        """,
        {"u": from_id, "f": to_id},
    )

    return {"message": "Friend request accepted"}


# ---------- Groups ----------

@router.post("/groups", response_model=GroupSummary)
def create_group(payload: GroupCreateRequest, current: AuthUser = Depends(get_current_user)) -> GroupSummary:
    # 1. 先创建 group 记录
    row = fetch_one_returning(
        """
        INSERT INTO groups (name, description, created_by)
        VALUES (%(name)s, %(desc)s, %(uid)s)
        RETURNING id, name, description, created_at
        """,
        {"name": payload.name, "desc": payload.description, "uid": current.id},
    )

    group_id = row["id"]

    # 2. 创建者自动成为 owner
    execute(
        """
        INSERT INTO group_members (group_id, user_id, role)
        VALUES (%(gid)s, %(uid)s, 'owner')
        """,
        {"gid": group_id, "uid": current.id},
    )

    # 3. 合并 members / member_codes（兼容前端 payload）
    raw_codes = []
    if payload.members:
        raw_codes.extend(payload.members)
    if payload.member_codes:
        raw_codes.extend(payload.member_codes)

    # 去重 + 去掉自己的 user_code
    unique_codes = {code.strip() for code in raw_codes if code and code.strip()}
    if current.user_code in unique_codes:
        unique_codes.remove(current.user_code)

    # 4. 通过 user_code 找到用户并加入 group_members
    for code in unique_codes:
        user = fetch_one(
            "SELECT id FROM users WHERE user_code = %(code)s",
            {"code": code},
        )
        if not user:
            # 找不到这个 user_code，就先静默跳过（也可以改成 400 直接报错）
            continue

        # 是否已经在这个组里？
        existing_member = fetch_one(
            """
            SELECT 1 FROM group_members
            WHERE group_id = %(gid)s AND user_id = %(uid)s
            """,
            {"gid": group_id, "uid": user["id"]},
        )
        if existing_member:
            continue

        execute(
            """
            INSERT INTO group_members (group_id, user_id, role)
            VALUES (%(gid)s, %(uid)s, 'member')
            """,
            {"gid": group_id, "uid": user["id"]},
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


def _find_route(route_id: str) -> Optional[dict]:
    """Find a route by id from the in-memory/seeded catalog."""
    try:
        routes = list_routes().routes
    except Exception:
        return None
    for r in routes:
        if str(r.id) == str(route_id):
            return r.dict()
    return None


def _compose_trail_briefing(route: dict) -> str:
    """Create a concise AI-style briefing for a trail."""
    name = route.get("name", "Trail")
    distance = route.get("distance_km", "?")
    gain = route.get("elevation_gain_m", "?")
    difficulty = str(route.get("difficulty", "unknown")).title()
    drive = route.get("drive_time_min", "?")
    tags = route.get("tags") or []
    tag_str = ", ".join(tags) if tags else "no extra tags"
    location = route.get("location", "")
    return (
        f"🧭 **{name}** — {location}\n"
        f"- Distance: {distance} km · Gain: {gain} m · Difficulty: {difficulty}\n"
        f"- Drive: ~{drive} min · Tags: {tag_str}\n"
        f"- Gear: water, layers, headlamp, sun/bug protection; add traction if wet.\n"
        f"- Safety: align pace/turnaround; check weather + sunset; share ETA."
    )


def _fetch_recent_group_messages(group_id: UUID, limit: int = 20) -> List[dict]:
    """Grab recent messages to craft AI tips."""
    rows = fetch_all(
        """
        SELECT sender_display AS sender, content
        FROM group_messages
        WHERE group_id = %(gid)s
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """,
        {"gid": str(group_id), "limit": limit},
    )
    return rows


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
        error_text = f"⚠️ Trail Mind 调路线推荐失败：{exc}"
        row = fetch_one_returning(
            """
            INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
            VALUES (%(gid)s, NULL, 'Trail Mind', 'assistant', %(content)s)
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
        VALUES (%(gid)s, NULL, 'Trail Mind', 'assistant', %(content)s)
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


# ---------- 群内 AI：基于聊天的建议 ----------

@router.post("/groups/{group_id}/ai/chat_suggestions", response_model=GroupMessageModel)
def ai_chat_suggestions(
    group_id: UUID,
    current: AuthUser = Depends(get_current_user),
) -> GroupMessageModel:
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    msgs = _fetch_recent_group_messages(group_id)
    if not msgs:
        content = (
            "🤖 Trail Mind：群里还没有对话。聊聊距离、爬升、狗友好、驾车时间，我来给建议。"
        )
    else:
        senders = list({m.get("sender") for m in msgs if m.get("sender")})[:3]
        content = (
            "🤖 Trail Mind 浏览了最近的聊天：\n"
            f"- 参与者：{', '.join(senders)}\n"
            "- 建议：\n"
            "  • 确认距离/爬升和驾驶时间的共识\n"
            "  • 选 2–3 条候选路线，加标签（狗友好/水源/遮荫）\n"
            "  • 查看天气和日落，设定返程时间\n"
            "  • 列个装备清单：水、分层、头灯、保暖/防晒/止滑"
        )

    row = fetch_one_returning(
        """
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
        VALUES (%(gid)s, NULL, 'Trail Mind', 'assistant', %(content)s)
        RETURNING id, group_id, sender_display AS sender, role, content, created_at
        """,
        {
            "gid": str(group_id),
            "content": content,
        },
    )
    return GroupMessageModel(**row)


# ---------- 群内 AI：选定路线后的通告 ----------

@router.post("/groups/{group_id}/ai/announce_trail", response_model=GroupMessageModel)
def ai_announce_trail(
    group_id: UUID,
    route_id: str = Body(..., embed=True),
    current: AuthUser = Depends(get_current_user),
) -> GroupMessageModel:
    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": str(group_id), "uid": current.id},
    )
    if not member:
        raise HTTPException(403, "Not a member")

    route = _find_route(route_id)
    if not route:
        raise HTTPException(404, "Route not found")

    content = "📣 Trail Mind 行前通告\n" + _compose_trail_briefing(route)

    row = fetch_one_returning(
        """
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
        VALUES (%(gid)s, NULL, 'Trail Mind', 'assistant', %(content)s)
        RETURNING id, group_id, sender_display AS sender, role, content, created_at
        """,
        {
            "gid": str(group_id),
            "content": content,
        },
    )
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
