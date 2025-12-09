# frontend/api.py (请完全覆盖)
from __future__ import annotations
import os
import requests
from datetime import datetime
from typing import Any, Dict, List
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def send_planning_message(message: str) -> str:
    r = requests.post(f"{BACKEND_URL}/chat", json={"user_message": message}, timeout=15)
    r.raise_for_status()
    return r.json().get("reply", "")

def auth_request(path: str, username: str, password: str, user_code: str | None = None) -> str:
    payload = {"username": username, "password": password}
    if path == "/auth/signup": payload["user_code"] = user_code or ""
    r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=15)
    if r.status_code != 200: raise RuntimeError(r.json().get("detail", "Auth failed"))
    data = r.json()
    st.session_state.user = data["user"]["username"]
    st.session_state.user_code = data["user"]["user_code"]
    st.session_state.current_user = data["user"]["username"]
    st.session_state.current_user_id = data["user"]["id"]
    return data.get("message", "OK")

def _auth_headers() -> Dict[str, str]:
    u, c = st.session_state.get("user"), st.session_state.get("user_code")
    return {"X-Username": u, "X-User-Code": c} if u and c else {}

def fetch_groups() -> List[Dict]: return requests.get(f"{BACKEND_URL}/social/groups", headers=_auth_headers()).json().get("groups", [])
def create_group(name: str, member_codes: List[str]) -> Dict:
    return requests.post(f"{BACKEND_URL}/social/groups", json={"name": name, "member_codes": member_codes}, headers=_auth_headers()).json()

def fetch_group_members_detailed(group_id: str) -> List[Dict]:
    return requests.get(f"{BACKEND_URL}/social/groups/{group_id}/members", headers=_auth_headers()).json().get("members", [])
def fetch_group_members(group_id: str) -> List[str]:
    return [m["username"] for m in fetch_group_members_detailed(group_id)]

def join_group(gid: str): requests.post(f"{BACKEND_URL}/social/groups/{gid}/join", headers=_auth_headers())
def leave_group(gid: str): requests.post(f"{BACKEND_URL}/social/groups/{gid}/leave", headers=_auth_headers())
def invite_group_member(gid: str, c: str): requests.post(f"{BACKEND_URL}/social/groups/{gid}/invite", json={"friend_code": c}, headers=_auth_headers())
def kick_group_member(gid: str, uid: int): requests.post(f"{BACKEND_URL}/social/groups/{gid}/kick", json={"user_id": uid}, headers=_auth_headers())

def fetch_group_messages(gid: str): return requests.get(f"{BACKEND_URL}/social/groups/{gid}/messages", headers=_auth_headers()).json().get("messages", [])
def send_group_message(gid: str, c: str): requests.post(f"{BACKEND_URL}/social/groups/{gid}/messages", json={"content": c}, headers=_auth_headers())

# AI Calls
def ask_ai_recommend(gid: str): 
    requests.post(f"{BACKEND_URL}/social/groups/{gid}/ai/recommend_routes", headers=_auth_headers())

def fetch_friends(): return requests.get(f"{BACKEND_URL}/social/friends", headers=_auth_headers()).json().get("friends", [])
def send_friend_request(fc: str): requests.post(f"{BACKEND_URL}/social/friends/add", json={"friend_code": fc}, headers=_auth_headers())
def fetch_friend_requests(): return requests.get(f"{BACKEND_URL}/social/friends/requests", headers=_auth_headers()).json().get("requests", [])
def accept_friend_request(rid: int): requests.post(f"{BACKEND_URL}/social/friends/accept", json={"request_id": rid}, headers=_auth_headers())
def get_or_create_dm(fid: int): return requests.post(f"{BACKEND_URL}/social/friends/dm", json={"friend_id": fid}, headers=_auth_headers()).json().get("group_id")

# 🟢 新增：remove_friend
def remove_friend(friend_id: int):
    requests.post(f"{BACKEND_URL}/social/friends/remove", json={"friend_id": friend_id}, headers=_auth_headers()).raise_for_status()