# ui_friends.py
from __future__ import annotations
from typing import List, Dict, Any
import streamlit as st

from api import (
    fetch_friends,
    send_friend_request,
    fetch_friend_requests,
    accept_friend_request,
)


def render_add_friend_page(username: str) -> None:
    st.subheader("Add & Manage Friends")

    # Back Button
    if st.button("← Back to home", key="back_from_add_friend"):
        st.session_state.view_mode = "home"
        st.rerun()

    # ---- Add Friend ----
    st.markdown("### Add friend")

    friend_code = st.text_input(
        "Friend code (Hike ID)",
        placeholder="Enter your friend's Hike ID (user code)",
        key="add_friend_code",
    )

    if st.button("Send friend request", type="primary", key="btn_send_friend_request"):
        if not friend_code.strip():
            st.error("Please enter a friend code.")
        else:
            try:
                res = send_friend_request(friend_code.strip())
                name = res.get("username") or res.get("display_name") or friend_code
                st.success(f"Friend request sent to {name}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to send friend request: {exc}")

    st.markdown("---")

    # ---- Incoming Requests ----
    st.markdown("### Incoming friend requests")

    try:
        # NEW: 现在不传 username
        requests = fetch_friend_requests()
    except Exception as exc:
        requests = []
        st.error(f"Unable to load friend requests: {exc}")

    if not requests:
        st.caption("No incoming requests.")
    else:
        for req in requests:
            rid = req.get("request_id") or req.get("id")
            from_name = req.get("from_username") or "Someone"
            from_code = req.get("from_user_code") or "N/A"

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"- **{from_name}** (`{from_code}`) wants to add you.")
            with col2:
                if st.button("Accept", key=f"accept-{rid}"):
                    try:
                        accept_friend_request(rid)
                        st.success(f"You are now friends with {from_name}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Unable to accept request: {exc}")

    st.markdown("---")

    # ---- Friends ----
    st.markdown("### Your friends")

    try:
        # NEW: 现在不传 username
        friends = fetch_friends()
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    if not friends:
        st.caption("You have no friends yet.")
    else:
        for f in friends:
            name = f.get("display_name") or f.get("username") or "Friend"
            code = f.get("user_code") or ""
            st.markdown(f"- **{name}** (`{code}`)")
