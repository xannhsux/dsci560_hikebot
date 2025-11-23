# api.py
from __future__ import annotations

import os
import requests
from datetime import datetime
from typing import Any, Dict, List, cast

import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ============================================================
# General AI Planning Chat (no auth needed)
# ============================================================

def send_planning_message(message: str) -> str:
    """Send general AI planning chat request."""
    r = requests.post(
        f"{BACKEND_URL}/chat",
        json={"user_message": message},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("reply", "")


# ============================================================
# Auth (Signup / Login)
# ============================================================

def auth_request(path: str, username: str, password: str, user_code: str | None = None) -> str:
    """
    Shared login/signup auth call.

    path: "/auth/login" 或 "/auth/signup"
    """
    payload: Dict[str, Any] = {"username": username, "password": password}

    if path == "/auth/signup":
        payload["user_code"] = user_code or ""

    r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=15)
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = ""
        raise RuntimeError(detail or f"Auth failed ({r.status_code})")

    data = r.json()
    user = data.get("user") or {}

    # 保存当前登录用户到 session_state（供 _auth_headers 使用）
    st.session_state.user = user.get("username")
    st.session_state.user_code = user.get("user_code")
    st.session_state.current_user = user.get("username")

    return data.get("message", "OK")


# ============================================================
# Auth Headers
# ============================================================

def _auth_headers() -> Dict[str, str]:
    """
    构造后端需要的认证头：
    X-Username / X-User-Code
    """
    user = st.session_state.get("user")
    code = st.session_state.get("user_code")
    if not user or not code:
        return {}
    return {
        "X-Username": user,
        "X-User-Code": code,
    }


# ============================================================
# Route APIs (no auth needed)
# ============================================================

def fetch_routes() -> List[Dict[str, Any]]:
    """获取可用路线列表。"""
    r = requests.get(f"{BACKEND_URL}/routes", timeout=15)
    r.raise_for_status()
    return r.json().get("routes", [])


def request_weather(route_id: str, when: datetime) -> Dict[str, Any]:
    """请求某条路线在某个时间的天气快照。"""
    payload = {"route_id": route_id, "start_iso": when.isoformat()}
    r = requests.post(
        f"{BACKEND_URL}/weather/snapshot",
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


# ============================================================
# Social / Groups (with auth headers)
# ============================================================

def fetch_groups() -> List[Dict[str, Any]]:
    """
    获取当前用户所在的所有群组。
    后端从 header 中解析当前用户，不需要额外参数。
    """
    r = requests.get(
        f"{BACKEND_URL}/social/groups",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    # 你后端如果是直接返回 list，就直接 r.json()
    data = r.json()
    if isinstance(data, dict):
        return data.get("groups", [])
    return cast(List[Dict[str, Any]], data)


def create_group(name: str, member_codes: List[str]) -> Dict[str, Any]:
    """
    创建一个新群组，当前登录用户自动作为创建者加入。
    member_codes: 其他要邀请进来的用户 user_code 列表。
    """
    payload = {
        "name": name,
        "description": "",        # 如需描述可在前端加输入框
        "member_codes": member_codes,
    }
    r = requests.post(
        f"{BACKEND_URL}/social/groups",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_group_messages(group_id: str) -> List[Dict[str, Any]]:
    """获取某个群聊的历史消息。"""
    r = requests.get(
        f"{BACKEND_URL}/social/groups/{group_id}/messages",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("messages", [])
    return cast(List[Dict[str, Any]], data)


def send_group_message(group_id: str, content: str) -> Dict[str, Any]:
    """在群里发送一条消息。"""
    payload = {"content": content}
    r = requests.post(
        f"{BACKEND_URL}/social/groups/{group_id}/messages",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_group_members(group_id: str) -> List[str]:
    """获取某个群的成员（返回用户名列表）。"""
    r = requests.get(
        f"{BACKEND_URL}/social/groups/{group_id}/members",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    # 兼容两种后端写法：{"members": [...]} 或直接 [...]
    if isinstance(data, dict):
        members = data.get("members", [])
    else:
        members = data
    return cast(List[str], members)


def join_group(group_id: str) -> List[str]:
    """加入某个群，返回最新成员列表。"""
    r = requests.post(
        f"{BACKEND_URL}/social/groups/{group_id}/join",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        members = data.get("members", [])
    else:
        members = data
    return cast(List[str], members)


def leave_group(group_id: str) -> List[str]:
    """退出某个群，返回最新成员列表。"""
    r = requests.post(
        f"{BACKEND_URL}/social/groups/{group_id}/leave",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        members = data.get("members", [])
    else:
        members = data
    return cast(List[str], members)


def ask_ai_trail(group_id: str) -> Dict[str, Any]:
    """让 HikeBot AI 在当前群里推荐路线（消息会写进群聊里）。"""
    r = requests.post(
        f"{BACKEND_URL}/social/groups/{group_id}/ai/recommend_routes",
        headers=_auth_headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


# ============================================================
# Friends (with auth headers)
# ============================================================

def fetch_friends() -> List[Dict[str, Any]]:
    """
    获取当前用户的好友列表。
    后端通过 header 中的 X-Username / X-User-Code 判定是谁。
    """
    r = requests.get(
        f"{BACKEND_URL}/social/friends",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("friends", [])
    return cast(List[Dict[str, Any]], data)


def send_friend_request(friend_code: str) -> Dict[str, Any]:
    """
    发送好友请求。
    friend_code: 对方的 user_code（Hike ID）。
    """
    payload = {"friend_code": friend_code}
    r = requests.post(
        f"{BACKEND_URL}/social/friends/add",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_friend_requests() -> List[Dict[str, Any]]:
    """
    获取“别人加我”的待处理好友请求列表。

    ⚠️ 目前后端如果还没实现 /social/friends/requests
    会返回 404，这个属于下一步要补的后端功能。
    """
    r = requests.get(
        f"{BACKEND_URL}/social/friends/requests",
        headers=_auth_headers(),
        timeout=15,
    )
    if r.status_code == 404:
        # 后端还没实现时，前端不崩掉，返回空列表即可
        return []
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("requests", [])
    return cast(List[Dict[str, Any]], data)


def accept_friend_request(request_id: str) -> Dict[str, Any]:
    """
    接受某条好友请求。
    request_id：好友请求的 ID（由 /friends/requests 返回）。
    """
    payload = {"request_id": request_id}
    r = requests.post(
        f"{BACKEND_URL}/social/friends/accept",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
