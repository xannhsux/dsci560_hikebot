# frontend/ui_chat.py
from __future__ import annotations
import json
from typing import Dict, Any

import streamlit as st

from api import (
    fetch_group_messages,
    send_group_message,
    fetch_group_members,
    join_group,
    leave_group,
    ask_ai_trail,
    ask_ai_chat_suggestions,
    announce_trail_briefing,
    fetch_routes,
)
from state import ensure_members_cached, in_group
from ui_common import render_message_bubble


def normalize_group_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize backend group message payload into the shape expected by
    render_message_bubble.
    """
    sender = raw.get("sender") or raw.get("sender_display") or "Unknown"
    content = raw.get("content", "")
    ts = raw.get("timestamp") or raw.get("created_at")
    role = raw.get("role", "user") # Extract role if available
    return {"sender": sender, "content": content, "timestamp": ts, "role": role}


def render_rich_message(msg: Dict[str, Any]) -> None:
    """
    Smart renderer that distinguishes between plain text messages and
    structured AI JSON announcements (HikeBot Trip Cards).
    """
    sender = msg.get("sender", "Unknown")
    content = msg.get("content", "")
    role = msg.get("role", "user")

    # 1. Check if this is a potential AI Card (JSON)
    # Usually sent by HikeBot or role='assistant'
    is_announcement = False
    data = {}

    if sender == "HikeBot" or role == "assistant":
        try:
            parsed = json.loads(content)
            # Basic validation to ensure it's our trip schema
            if isinstance(parsed, dict) and "title" in parsed:
                data = parsed
                is_announcement = True
        except (json.JSONDecodeError, TypeError):
            # Not JSON, treat as normal text
            pass

    # 2. Render UI
    if is_announcement:
        # === Render AI Trip Card ===
        with st.chat_message("assistant", avatar="🤖"):
            st.caption(f"Bot Suggestion via {sender}")
            
            # Header
            st.markdown(f"### 🌲 {data.get('title', 'Trip Plan')}")
            
            # Summary
            st.write(data.get('summary', ''))
            
            # Stats Metrics
            stats = data.get('stats', {})
            if stats:
                c1, c2 = st.columns(2)
                c1.metric("📏 Distance", stats.get('dist', 'N/A'))
                c2.metric("⛰️ Elevation", stats.get('elev', 'N/A'))
            
            # Weather Warning
            weather = data.get('weather_warning')
            if weather:
                st.info(f"🌤 **Weather Note:** {weather}")
            
            # Gear Checklist
            gear = data.get('gear_required', [])
            if gear:
                with st.expander("🎒 Required Gear Checklist", expanded=False):
                    for idx, item in enumerate(gear):
                        # Use a unique key to avoid Streamlit duplicate ID errors
                        st.checkbox(item, value=True, key=f"gear_{idx}_{str(hash(content))[:8]}", disabled=True)
            
            # Future expansion: Add a 'Join Trip' button here
            # if st.button("Join this Hike", key=f"join_{str(hash(content))[:8]}"):
            #     pass

    else:
        # === Render Standard Message Bubble ===
        # Fallback to the common renderer for human messages or plain bot text
        render_message_bubble(msg)


def render_members_panel() -> None:
    """Sidebar panel: current group's member list + join/leave controls.

    Uses st.session_state.active_group to know which group is active.
    """
    st.subheader("Group Members")

    group_id = st.session_state.get("active_group")
    if not group_id:
        st.caption("No group selected.")
        return

    username = st.session_state.get("user") or st.session_state.get("current_user")

    # Cache members in session_state.group_members to avoid repeated calls.
    members = ensure_members_cached(group_id, fetch_group_members)
    if members:
        for m in members:
            if m == username:
                st.markdown(f"- **{m}** (you)")
            else:
                st.markdown(f"- {m}")
    else:
        st.caption("No members yet.")

    st.markdown("---")

    # Join / leave controls
    if in_group(group_id, username, fetch_group_members):
        if st.button("Quit this group", key="quit-current-group"):
            try:
                new_members = leave_group(group_id)
                st.session_state.group_members[group_id] = new_members
                st.session_state.active_group = None
                st.session_state.view_mode = "home"
                st.success("You left the group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to leave group: {exc}")
    else:
        if st.button("Join this group", key="join-current-group"):
            try:
                new_members = join_group(group_id)
                st.session_state.group_members[group_id] = new_members
                st.session_state.active_group = group_id
                st.success("Joined group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to join group: {exc}")


def render_chat_page(username: str) -> None:
    """Main group chat view.

    - Uses st.session_state.active_group as the current group.
    - Only allows sending messages if the user has joined the group.
    """
    group_id = st.session_state.get("active_group")
    if not group_id:
        st.info("Select a group from the Home page to start chatting.")
        return

    # preload routes for briefing selection
    routes = []
    try:
        routes = fetch_routes()
    except Exception:
        routes = []

    # Header with AI helper
    header = st.container()
    with header:
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.subheader(f"Group {group_id} · Chat")
        with c2:
            if st.button("AI Suggestions", key="ask-ai-chat-tips"):
                try:
                    ask_ai_chat_suggestions(group_id)
                    st.success("Trail Mind added suggestions to the chat.")
                except Exception as exc:
                    st.error(f"Unable to get AI suggestions: {exc}")
        with c3:
            route_options = routes or []
            route_labels = [f"{r.get('name','Route')} — {r.get('location','')}" for r in route_options]
            if route_labels:
                default_idx = 0
                selected_label = st.selectbox(
                    "Trail briefing",
                    route_labels,
                    index=default_idx,
                    key=f"brief_route_{group_id}",
                )
                chosen = route_options[route_labels.index(selected_label)]
                if st.button("Send briefing", key="send-briefing"):
                    try:
                        announce_trail_briefing(group_id, chosen.get("id"))
                        st.success("Trail briefing posted.")
                    except Exception as exc:
                        st.error(f"Unable to post briefing: {exc}")
            if st.button("AI Route Ideas", key="ask-ai-trail"):
                try:
                    ask_ai_trail(group_id)
                    st.success("AI route ideas sent to the group.")
                except Exception as exc:
                    st.error(f"Unable to ask AI: {exc}")

    # Ensure the user is in this group before allowing chat
    if not in_group(group_id, username, fetch_group_members):
        st.warning("You are not in this group yet. Join to chat.")
        if st.button("Join this group", key="join-from-chat"):
            try:
                new_members = join_group(group_id)
                st.session_state.group_members[group_id] = new_members
                st.success("Joined group.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to join group: {exc}")
        return

    # Chat history
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
                # UPDATED: Use the new rich renderer
                render_rich_message(msg)

    # Input box at the bottom
    text = st.chat_input("Share an update with the group…", key="group_chat_input")
    if text:
        try:
            send_group_message(group_id, text)
        except Exception as exc:
            st.error(f"Unable to send message: {exc}")
            return
        st.rerun()