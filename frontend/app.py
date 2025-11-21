"""Streamlit UI for the HikeBot chatbot."""

from __future__ import annotations

import os
from datetime import datetime
from html import escape
from textwrap import dedent
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# --------- 初始化群聊相关状态 ---------

def init_state() -> None:
    # 已登录用户名（后端用）
    if "user" not in st.session_state:
        st.session_state.user = None

    # 当前登录用户（决定聊天气泡位置）
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    # 聊天记录：可以同时兼容旧结构和新结构
    # 新结构：{"sender", "role", "content", "timestamp"}
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "sender": "HikeBot",
                "role": "assistant",
                "content": "Hey trail crew! How can I help today?",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

    if "group_members" not in st.session_state:
        st.session_state.group_members: Dict[str, List[str]] = {}

    if "active_group_route" not in st.session_state:
        st.session_state.active_group_route: Optional[str] = None

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "home"


# --------- 调用后端的函数 ---------

def send_message(message: str) -> str:
    payload: Dict[str, Any] = {"user_message": message}
    response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("reply", "No response received.")


def auth_request(endpoint: str, username: str, password: str) -> str:
    response = requests.post(
        f"{BACKEND_URL}{endpoint}",
        json={"username": username, "password": password},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("message", "Success.")


@st.cache_data(ttl=600)
def fetch_routes() -> List[Dict[str, Any]]:
    response = requests.get(f"{BACKEND_URL}/routes", timeout=15)
    response.raise_for_status()
    return response.json().get("routes", [])


def request_weather(route_id: str, when: datetime) -> Dict[str, Any]:
    payload = {"route_id": route_id, "start_iso": when.isoformat()}
    response = requests.post(f"{BACKEND_URL}/weather/snapshot", json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def join_route_group(route_id: str, username: str) -> List[str]:
    payload = {"route_id": route_id, "username": username}
    response = requests.post(f"{BACKEND_URL}/groups/join", json=payload, timeout=15)
    response.raise_for_status()
    return response.json().get("members", [])


def leave_route_group_request(route_id: str, username: str) -> List[str]:
    payload = {"route_id": route_id, "username": username}
    response = requests.post(f"{BACKEND_URL}/groups/leave", json=payload, timeout=15)
    response.raise_for_status()
    return response.json().get("members", [])


def fetch_group_members(route_id: str) -> List[str]:
    response = requests.get(f"{BACKEND_URL}/groups/{route_id}/members", timeout=15)
    response.raise_for_status()
    return response.json().get("members", [])


def fetch_group_messages(route_id: str) -> List[Dict[str, Any]]:
    response = requests.get(f"{BACKEND_URL}/groups/{route_id}/messages", timeout=15)
    response.raise_for_status()
    return response.json().get("messages", [])


def send_group_message(route_id: str, username: str, content: str) -> List[Dict[str, Any]]:
    payload = {"route_id": route_id, "username": username, "content": content}
    response = requests.post(f"{BACKEND_URL}/groups/message", json=payload, timeout=15)
    response.raise_for_status()
    return response.json().get("messages", [])


def get_cached_members(route_id: str) -> List[str]:
    if not route_id:
        return []
    if route_id not in st.session_state.group_members:
        try:
            members = fetch_group_members(route_id)
        except requests.RequestException:
            members = []
        st.session_state.group_members[route_id] = members
    return st.session_state.group_members[route_id]


def handle_join_route(route_id: str, username: str) -> bool:
    if not username:
        st.warning("Please log in to join a group.")
        return False
    try:
        members = join_route_group(route_id, username)
    except requests.RequestException as exc:
        st.error(f"Unable to join group: {exc}")
        return False
    st.session_state.group_members[route_id] = members
    st.session_state.active_group_route = route_id
    st.session_state.view_mode = "group"
    return True


def handle_leave_route(route_id: str, username: str) -> bool:
    if not username:
        st.warning("Please log in to manage groups.")
        return False
    try:
        members = leave_route_group_request(route_id, username)
    except requests.RequestException as exc:
        st.error(f"Unable to leave group: {exc}")
        return False
    st.session_state.group_members[route_id] = members
    if st.session_state.active_group_route == route_id:
        st.session_state.view_mode = "home"
    return True


def user_in_group(route_id: Optional[str], username: Optional[str]) -> bool:
    if not route_id or not username:
        return False
    members = st.session_state.group_members.get(route_id)
    if members is None:
        members = get_cached_members(route_id)
    return any(member.lower() == username.lower() for member in members)


# --------- 认证 UI（基本不变，只加了一行 current_user） ---------

def render_auth_gate() -> bool:
    st.subheader("Login or Sign up")
    login_tab, signup_tab = st.tabs(["Login", "Sign up"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
            try:
                message = auth_request("/auth/login", username, password)
                st.session_state["user"] = username
                # 登录成功后，当前扮演身份 = 自己
                st.session_state["current_user"] = username
                st.success(message)
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Login failed: {exc.response.text if exc.response else exc}")

    with signup_tab:
        with st.form("signup_form"):
            username = st.text_input("New username", key="signup_username")
            password = st.text_input("New password", type="password", key="signup_password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                message = auth_request("/auth/signup", username, password)
                st.session_state["user"] = username
                st.session_state["current_user"] = username
                st.success(message)
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Signup failed: {exc.response.text if exc.response else exc}")

    return False


# --------- Sidebar：行程历史 + Logout（原样保留） ---------

def render_sidebar(username: str, routes: List[Dict[str, Any]]) -> None:
    with st.sidebar:
        st.header("Trail Groups")
        if not routes:
            st.caption("No trail data yet. Ask HikeBot for recommendations first.")
        else:
            if not st.session_state.active_group_route:
                st.session_state.active_group_route = routes[0]["id"]

            options = {f"{r['name']} — {r.get('location', '')}": r["id"] for r in routes}
            labels = list(options.keys())
            current_route = st.session_state.active_group_route
            try:
                current_index = list(options.values()).index(current_route)
            except ValueError:
                current_index = 0

            label = st.selectbox(
                "Choose a trail", labels, index=current_index, key="sidebar_group_select"
            )
            selected_route = options[label]
            if selected_route != st.session_state.active_group_route:
                st.session_state.active_group_route = selected_route

            route = next((r for r in routes if r["id"] == selected_route), None)
            if route:
                st.caption(
                    f"{route['distance_km']} km · {route['elevation_gain_m']} m gain · "
                    f"{route['difficulty'].title()} · ~{route['drive_time_min']} min drive"
                )
                st.write(route.get("summary", ""))

            joined = user_in_group(selected_route, username)
            if joined:
                if st.button("Quit this group", key=f"sidebar-leave-{selected_route}"):
                    if handle_leave_route(selected_route, username):
                        st.success("You left this group.")
            else:
                if st.button("Join this group", key=f"sidebar-join-{selected_route}"):
                    if handle_join_route(selected_route, username):
                        st.success("You're in! Check the member list below.")

            members = get_cached_members(selected_route)
            st.markdown("**Members**")
            if members:
                for member in members:
                    st.markdown(f"- {member}")
            else:
                st.caption("No one has joined this group yet.")

        st.markdown("---")
        if st.button("Log out"):
            st.session_state.pop("user", None)
            st.rerun()


# --------- Weather 工具（挪到右侧列用） ---------

def render_message_bubble(msg: Dict[str, Any]) -> None:
    # 兼容旧结构
    sender = msg.get("sender")
    role = msg.get("role", "user")
    content = msg.get("content", "")
    ts = msg.get("timestamp")

    if sender is None:
        # 如果是旧结构：没有 sender，用 role 猜一下
        sender = "You" if role == "user" else "HikeBot"

    # 自己的消息右对齐，别人左对齐
    is_me = sender == st.session_state.current_user
    align = "flex-end" if is_me else "flex-start"
    bubble_color = "#DCF8C6" if is_me else "#FFFFFF"  # 右绿左白
    text_align = "right" if is_me else "left"

    # 时间格式化
    time_str = ""
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%H:%M")
        except Exception:
            time_str = str(ts)

    safe_sender = escape(sender)
    safe_time = escape(time_str)
    safe_content = escape(content).replace("\n", "<br>")

    bubble_html = dedent(
        f"""
        <div style="display: flex; justify-content: {align}; margin-bottom: 8px;">
          <div style="max-width: 75%; display: flex; flex-direction: column; align-items: {text_align};">
            <div style="font-size: 12px; color: #888888; margin-bottom: 2px;">
              {safe_sender} · {safe_time}
            </div>
            <div style="
              background-color: {bubble_color};
              padding: 8px 12px;
              border-radius: 16px;
              box-shadow: 0 1px 2px rgba(0,0,0,0.1);
              font-size: 14px;
              line-height: 1.4;
              white-space: pre-wrap;
              text-align: left;
            ">
              {safe_content}
            </div>
          </div>
        </div>
        """
    ).strip()

    st.markdown(bubble_html, unsafe_allow_html=True)


# --------- 主入口：群聊 UI ---------

def render_home_chat(user: str) -> None:
    st.subheader("AI Planning Chat")
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.caption("No messages yet. Start the conversation!")
        else:
            for msg in st.session_state.messages:
                render_message_bubble(msg)

    prompt = st.chat_input("Ask about hikes, gear, weather, or safety…", key="home_chat_input")
    if prompt:
        now_str = datetime.utcnow().isoformat()
        st.session_state.messages.append(
            {
                "sender": st.session_state.current_user,
                "role": "user",
                "content": prompt,
                "timestamp": now_str,
            }
        )
        try:
            reply = send_message(prompt)
        except requests.RequestException as exc:
            reply = f"⚠️ Unable to reach backend: {exc}"

        st.session_state.messages.append(
            {
                "sender": "HikeBot",
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        st.rerun()


def render_group_chat(user: str, routes: List[Dict[str, Any]]) -> None:
    route_id = st.session_state.active_group_route
    if not route_id:
        st.warning("Join a trail group from the sidebar to start chatting.")
        return

    route = next((r for r in routes if r["id"] == route_id), None)
    title = route["name"] if route else route_id
    st.subheader(f"{title} · Group Chat")
    if st.button("← Back to AI home", key="back_home"):
        st.session_state.view_mode = "home"
        st.rerun()

    try:
        messages = fetch_group_messages(route_id)
    except requests.RequestException as exc:
        st.error(f"Unable to load group chat: {exc}")
        return

    for msg in messages:
        render_message_bubble(
            {
                "sender": msg.get("sender"),
                "role": "user",
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp"),
            }
        )

    group_input = st.chat_input("Share an update with the group…", key="group_chat_input")
    if group_input:
        try:
            send_group_message(route_id, user, group_input)
        except requests.RequestException as exc:
            st.error(f"Unable to send message: {exc}")
            return
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="HikeBot Chat", page_icon="🥾", layout="wide")
    init_state()

    st.title("HikeBot")
    st.caption("Hiking group companion for routes, weather, gear, and safety tips.")

    user = st.session_state.get("user")
    if not user:
        render_auth_gate()
        return

    st.session_state.current_user = user

    routes = fetch_routes()
    render_sidebar(user, routes)
    st.info(f"Logged in as {user}")

    if routes and not st.session_state.active_group_route:
        st.session_state.active_group_route = routes[0]["id"]

    if (
        st.session_state.view_mode == "home"
        and st.session_state.active_group_route
        and user_in_group(st.session_state.active_group_route, user)
    ):
        if st.button("Go to current trail group", key="jump_to_group"):
            st.session_state.view_mode = "group"
            st.rerun()

    if st.session_state.view_mode == "group":
        render_group_chat(user, routes)
    else:
        render_home_chat(user)


if __name__ == "__main__":
    main()
