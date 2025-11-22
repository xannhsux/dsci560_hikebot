# api.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List

import os
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def send_planning_message(message: str) -> str:
    """Send general AI planning chat request."""
    r = requests.post(f"{BACKEND_URL}/chat",
                      json={"user_message": message},
                      timeout=15)
    r.raise_for_status()
    return r.json().get("reply", "")


def auth_request(endpoint: str, username: str, password: str) -> str:
    """Login or signup."""
    r = requests.post(
        f"{BACKEND_URL}{endpoint}",
        json={"username": username, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("message", "Success.")


def fetch_routes() -> List[Dict[str, Any]]:
    r = requests.get(f"{BACKEND_URL}/routes", timeout=15)
    r.raise_for_status()
    return r.json().get("routes", [])


def request_weather(route_id: str, when: datetime) -> Dict[str, Any]:
    payload = {"route_id": route_id, "start_iso": when.isoformat()}
    r = requests.post(f"{BACKEND_URL}/weather/snapshot", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()
    

# ---- Social / group APIs (example) ----

def fetch_groups(username: str) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{BACKEND_URL}/social/groups",
        params={"username": username},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("groups", [])


def fetch_friends(username: str) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{BACKEND_URL}/social/friends",
        params={"username": username},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("friends", [])


def fetch_group_messages(group_id: str) -> List[Dict[str, Any]]:
    r = requests.get(f"{BACKEND_URL}/social/groups/{group_id}/messages", timeout=15)
    r.raise_for_status()
    return r.json().get("messages", [])


def send_group_message(group_id: str, username: str, content: str) -> None:
    payload = {"group_id": group_id, "username": username, "content": content}
    r = requests.post(f"{BACKEND_URL}/social/groups/message", json=payload, timeout=15)
    r.raise_for_status()


def fetch_group_members(group_id: str) -> List[str]:
    r = requests.get(f"{BACKEND_URL}/social/groups/{group_id}/members", timeout=15)
    r.raise_for_status()
    return r.json().get("members", [])


def join_group(group_id: str, username: str) -> List[str]:
    payload = {"group_id": group_id, "username": username}
    r = requests.post(f"{BACKEND_URL}/social/groups/join", json=payload, timeout=15)
    r.raise_for_status()
    return r.json().get("members", [])


def leave_group(group_id: str, username: str) -> List[str]:
    payload = {"group_id": group_id, "username": username}
    r = requests.post(f"{BACKEND_URL}/social/groups/leave", json=payload, timeout=15)
    r.raise_for_status()
    return r.json().get("members", [])


def ask_ai_trail(group_id: str, username: str) -> None:
    payload = {"group_id": group_id, "username": username}
    r = requests.post(f"{BACKEND_URL}/social/groups/ask_trail", json=payload, timeout=15)
    r.raise_for_status()

# ---- Friend APIs ----

def fetch_friends(username: str) -> List[Dict[str, Any]]:
    """Fetch friend list for the current user."""
    r = requests.get(
        f"{BACKEND_URL}/social/friends",
        params={"username": username},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("friends", [])


def send_friend_request(username: str, friend_code: str) -> Dict[str, Any]:
    """
    Send a friend request using a friend code or username.

    Adjust the endpoint and payload according to your backend.
    """
    payload = {"username": username, "friend_code": friend_code}
    r = requests.post(f"{BACKEND_URL}/social/friends/add", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def accept_friend_request(username: str, request_id: str) -> Dict[str, Any]:
    """Accept a pending friend request."""
    payload = {"username": username, "request_id": request_id}
    r = requests.post(f"{BACKEND_URL}/social/friends/accept", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_friend_requests(username: str) -> List[Dict[str, Any]]:
    """Fetch incoming friend requests."""
    r = requests.get(
        f"{BACKEND_URL}/social/friends/requests",
        params={"username": username},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("requests", [])
