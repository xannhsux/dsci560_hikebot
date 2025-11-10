"""Streamlit UI for the HikeBot chatbot."""

from __future__ import annotations

import os
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
