# ui_home.py
from __future__ import annotations
import streamlit as st
from api import send_planning_message
from ui_common import render_message_bubble


def render_home_planning_chat(username: str) -> None:
    st.markdown("### Trail Assistant")

    box = st.container()
    with box:
        msgs = st.session_state.messages
        if not msgs:
            st.caption("No messages yet. Start the conversation!")
        else:
            for msg in msgs:
                render_message_bubble(msg)

    prompt = st.chat_input(
        "e.g., 5–8 mi, <1500 ft, coastal, dog-friendly, 1hr drive", key="home_chat_input"
    )
    if prompt:
        from datetime import datetime as _dt
        now_str = _dt.utcnow().isoformat()
        st.session_state.messages.append(
            {"sender": username, "role": "user", "content": prompt, "timestamp": now_str}
        )
        try:
            reply = send_planning_message(prompt)
        except Exception as exc:
            reply = f"⚠️ Unable to reach backend: {exc}"
        st.session_state.messages.append(
            {
                "sender": "Trail Mind",
                "role": "assistant",
                "content": reply,
                "timestamp": _dt.utcnow().isoformat(),
            }
        )
        st.rerun()


def render_home_page(username: str) -> None:
    render_home_planning_chat(username)
