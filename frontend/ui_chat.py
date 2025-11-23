# ui_chat.py
from __future__ import annotations
from typing import Dict, Any

import streamlit as st

from api import (
    fetch_group_messages,
    send_group_message,
    fetch_group_members,
    join_group,
    leave_group,
    ask_ai_trail,
)
from state import ensure_members_cached, in_group
from ui_common import render_message_bubble


def normalize_group_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    sender = raw.get("sender") or raw.get("sender_display") or "Unknown"
    content = raw.get("content", "")
    ts = raw.get("timestamp") or raw.get("created_at")
    return {"sender": sender, "content": content, "timestamp": ts}


def render_members_panel(group_id: str, username: str) -> None:
    st.subheader("Group Members")
    if not group_id:
        st.caption("No group selected.")
        return

    members = ensure_members_cached(group_id, fetch_group_members)

    if members:
        for name in members:
            st.markdown(f"- {name}")
    else:
        st.caption("No members yet.")

    st.markdown("---")

    # ---- Join/Leave group ----
    if in_group(group_id, username, fetch_group_members):
        if st.button("Quit this group", key="quit-current-group"):
            try:
                members = leave_group(group_id)
                st.session_state.group_members[group_id] = members
                st.session_state.active_group = None
                st.session_state.view_mode = "home"
                st.success("You left the group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to leave group: {exc}")
    else:
        if st.button("Join this group", key="join-current-group"):
            try:
                members = join_group(group_id)
                st.session_state.group_members[group_id] = members
                st.session_state.active_group = group_id
                st.success("Joined group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to join group: {exc}")


def render_chat_page(username: str) -> None:
    group_id = st.session_state.active_group

    # Not in group yet
    if not in_group(group_id, username, fetch_group_members):
        st.warning("You are not in this group yet. Join to chat.")
        if st.button("Join this group", key="join-from-chat"):
            try:
                members = join_group(group_id)
                st.session_state.group_members[group_id] = members
                st.success("Joined group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to join group: {exc}")
        return

    # ---- Header ----
    header = st.container()
    with header:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.subheader(f"Group {group_id} · Chat")
        with c2:
            if st.button("Ask AI for Trail", key="ask-ai-trail"):
                try:
                    ask_ai_trail(group_id)
                    st.success("AI route request sent.")
                except Exception as exc:
                    st.error(f"Unable to ask AI: {exc}")

    # ---- Chat Messages ----
    chat_box = st.container()
    with chat_box:
        try:
            raws = fetch_group_messages(group_id)
        except Exception as exc:
            st.error(f"Unable to load group chat: {exc}")
            raws = []

        if not raws:
            st.caption("No messages yet. Say hi!")
        else:
            for raw in raws:
                msg = normalize_group_message(raw)
                render_message_bubble(msg)

    # ---- Send Message ----
    text = st.chat_input("Share an update with the group…", key="group_chat_input")
    if text:
        try:
            send_group_message(group_id, text)
        except Exception as exc:
            st.error(f"Unable to send message: {exc}")
            return

        st.rerun()
