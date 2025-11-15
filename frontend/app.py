"""Streamlit UI for the HikeBot chatbot."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# --------- 初始化群聊相关状态 ---------

def init_state() -> None:
    # 已登录用户名（后端用）
    if "user" not in st.session_state:
        st.session_state.user = None

    # 群成员列表（前端用，模拟微信群聊）
    if "members" not in st.session_state:
        st.session_state.members = ["Trip leader", "Alice", "Bob", "HikeBot"]

    # 当前这台设备“扮演”的成员（决定气泡在左还是右）
    if "current_user" not in st.session_state:
        st.session_state.current_user = "Trip leader"

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


def fetch_trip_history(username: str) -> List[Dict[str, Any]]:
    response = requests.get(f"{BACKEND_URL}/users/{username}/trips", timeout=15)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("trips", [])


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

def render_sidebar(username: str) -> None:
    with st.sidebar:
        st.header("Trip History")
        try:
            trips = fetch_trip_history(username)
        except requests.RequestException as exc:
            st.error(f"Unable to load history: {exc}")
            trips = []

        if trips:
            for trip in trips:
                status = trip.get("status", "planned")
                label = f"{trip.get('trip_name', 'Trip')} • {trip.get('date', '')}"
                st.markdown(
                    f"- **{label}**  \n  Role: {trip.get('role')} · {status.title()}"
                )
        else:
            st.caption("No hiking history yet.")

        if st.button("Log out"):
            st.session_state.pop("user", None)
            st.rerun()


# --------- Weather 工具（挪到右侧列用） ---------

def render_weather_tool() -> None:
    st.subheader("Weather Snapshot")
    routes = fetch_routes()
    if not routes:
        st.warning("No routes available to check weather.")
        return

    options = {f"{r['name']} — {r.get('location', '')}": r["id"] for r in routes}
    labels = list(options.keys())
    default_index = 0
    selected_label = st.selectbox("Choose a route", labels, index=default_index)
    selected_route = options[selected_label]

    default_time = datetime.utcnow().replace(microsecond=0)
    date_val = st.date_input(
        "Start date", value=default_time.date(), key="weather_date"
    )
    time_val = st.time_input(
        "Start time", value=default_time.time(), key="weather_time"
    )
    target = datetime.combine(date_val, time_val)

    if st.button("Get forecast", key="weather_button"):
        try:
            data = request_weather(selected_route, target)
        except requests.RequestException as exc:
            st.error(f"Unable to fetch weather: {exc}")
            return
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Temperature (°C)", data.get("temp_c"))
        with col2:
            prob = data.get("precip_probability", 0)
            st.metric("Precip probability", f"{prob*100:.0f}%")
        st.write(
            f"Lightning risk: **{data.get('lightning_risk', 'low').title()}**, "
            f"Fire risk: **{data.get('fire_risk', 'low').title()}**"
        )
        st.info(data.get("advisory", ""))


# --------- 新的群聊消息气泡（微信 / Discord 风格） ---------

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

    st.markdown(
        f"""
        <div style="display: flex; justify-content: {align}; margin-bottom: 8px;">
          <div style="max-width: 75%; display: flex; flex-direction: column; align-items: {text_align};">
            <div style="font-size: 12px; color: #888888; margin-bottom: 2px;">
              {sender} · {time_str}
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
              {content}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------- 主入口：改成多列布局的群聊 UI ---------

def main() -> None:
    st.set_page_config(page_title="HikeBot Chat", page_icon="🥾", layout="wide")
    init_state()

    st.title("HikeBot")
    st.caption("Hiking group companion for routes, weather, gear, and safety tips.")

    user = st.session_state.get("user")
    if not user:
        render_auth_gate()
        return

    # 确保登录用户在成员列表里
    if user not in st.session_state.members:
        st.session_state.members.insert(0, user)

    render_sidebar(user)
    st.info(f"Logged in as {user}")

    # 三列：左 -> 群成员；中 -> 聊天；右 -> Weather 工具
    col_left, col_center, col_right = st.columns([1.0, 2.4, 1.6])

    # 左侧：成员列表 + 当前扮演身份
    with col_left:
        st.subheader("Group Members")
        st.session_state.current_user = st.selectbox(
            "Send as… (for demo, local only)",
            options=st.session_state.members,
            index=st.session_state.members.index(st.session_state.current_user)
            if st.session_state.current_user in st.session_state.members
            else 0,
        )
        st.markdown("---")
        for m in st.session_state.members:
            if m == st.session_state.current_user:
                st.markdown(f"✅ **{m}**  _(current sender)_")
            else:
                st.markdown(f"- {m}")

    # 中间：群聊消息气泡 + 输入框
    with col_center:
        st.subheader("Group Chat")

        chat_container = st.container()
        with chat_container:
            if not st.session_state.messages:
                st.caption("No messages yet. Start the conversation!")
            else:
                for msg in st.session_state.messages:
                    render_message_bubble(msg)

        # 聊天输入（底部）
        prompt = st.chat_input("Ask about hikes, gear, weather, or safety…")
        if prompt:
            now_str = datetime.utcnow().isoformat()

            # 当前扮演成员先发一条消息（前端用）
            st.session_state.messages.append(
                {
                    "sender": st.session_state.current_user,
                    "role": "user",
                    "content": prompt,
                    "timestamp": now_str,
                }
            )

            # 把内容发给 backend，让 HikeBot 回应
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

    # 右侧：Weather 工具
    with col_right:
        render_weather_tool()


if __name__ == "__main__":
    main()
