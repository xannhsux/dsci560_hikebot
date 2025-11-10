"""Streamlit UI for the HikeBot chatbot."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def send_message(message: str) -> str:
    payload: Dict[str, Any] = {"user_message": message}
    response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("reply", "No response received.")


def render_chat(messages: List[Dict[str, str]]) -> None:
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def auth_request(endpoint: str, username: str, password: str) -> str:
    response = requests.post(
        f"{BACKEND_URL}{endpoint}",
        json={"username": username, "password": password},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("message", "Success.")


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
                st.success(message)
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Signup failed: {exc.response.text if exc.response else exc}")

    return False


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
                st.markdown(f"- **{label}**  \n  Role: {trip.get('role')} · {status.title()}")
        else:
            st.caption("No hiking history yet.")

        if st.button("Log out"):
            st.session_state.pop("user", None)
            st.rerun()


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
    date_val = st.date_input("Start date", value=default_time.date(), key="weather_date")
    time_val = st.time_input("Start time", value=default_time.time(), key="weather_time")
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


def main() -> None:
    st.set_page_config(page_title="HikeBot Chat", page_icon="🥾")
    st.title("HikeBot")
    st.caption("Hiking group companion for routes, weather, gear, and safety tips.")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hey trail crew! How can I help today?"}
        ]

    user = st.session_state.get("user")
    if not user:
        render_auth_gate()
        return

    render_sidebar(user)
    st.info(f"Logged in as {user}")
    render_chat(st.session_state.messages)
    render_weather_tool()

    if prompt := st.chat_input("Ask about hikes, gear, weather, or safety…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            reply = send_message(prompt)
        except requests.RequestException as exc:
            reply = f"⚠️ Unable to reach backend: {exc}"
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()


if __name__ == "__main__":
    main()
