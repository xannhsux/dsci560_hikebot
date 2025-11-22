# api.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
import os
import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ============================================================
# General AI Planning Chat (no auth needed)
# ============================================================

def send_planning_message(message: str) -> str:
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
    """Shared login/signup auth call."""
    payload: Dict[str, Any] = {"username": username, "password": password}

    if path == "/auth/signup" and user_code:
        payload["user_code"] = user_code

    r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=15)
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = ""
        raise RuntimeError(detail or f"Auth failed ({r.status_code})")

    data = r.json()
    user = data.get("user") or {}

    # Store current user session
    st.session_state.user = user.get("username")
    st.session_state.user_code = user.get("user_code")
    st.session_state.current_user = user.get("username")

    return data.get("message", "OK")


# ============================================================
# Auth Headers
# ============================================================

def _auth_headers() -> Dict[str, str]:
    """Build headers required by backend auth."""
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
    r = requests.get(f"{BACKEND_URL}/routes", timeout=15)
    r.raise_for_status()
    return r.json().get("routes", [])


def request_weather(route_id: str, when: datetime) -> Dict[str, Any]:
    payload = {"route_id": route_id, "start_iso": when.isoformat()}
    r = requests.post(f"{BACKEND_URL}/weather/snapshot", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


# ============================================================
# Social / Groups (with auth headers)
# ============================================================

def fetch_groups() -> List[Dict[str, Any]]:
    r = requests.get(
        f"{BACKEND_URL}/social/groups",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("groups", [])


def create_group(name: str, member_codes: List[str]) -> Dict[str, Any]:
    payload = {"name": name, "member_codes": member_codes}
    r = requests.post(
        f"{BACKEND_URL}/social/groups",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_group_messages(group_id: str) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{BACKEND_URL}/social/groups/{group_id}/messages",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def send_group_message(group_id: str, content: str) -> Dict[str, Any]:
    payload = {"content": content}
    r = requests.post(
        f"{BACKEND_URL}/social/groups/{group_id}/messages",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


from typing import cast

def fetch_group_members(group_id: str) -> List[str]:
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
    r = requests.get(
        f"{BACKEND_URL}/social/friends",
        params={"username": username}, 
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("friends", [])


def send_friend_request(friend_code: str) -> Dict[str, Any]:
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
    r = requests.get(
        f"{BACKEND_URL}/social/friends/requests",
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("requests", [])


def accept_friend_request(request_id: str) -> Dict[str, Any]:
    payload = {"request_id": request_id}
    r = requests.post(
        f"{BACKEND_URL}/social/friends/accept",
        json=payload,
        headers=_auth_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
