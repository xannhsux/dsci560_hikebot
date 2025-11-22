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
    """
    Center panel page for adding and managing friends.

    It has three main parts:
      1) Add friend by code / username
      2) Incoming friend requests
      3) Existing friend list
    """
    st.subheader("Add & Manage Friends")

    # ---- 1) Add friend form ----
    st.markdown("### Add friend")
    with st.form("add_friend_form"):
        friend_code = st.text_input(
            "Friend code or username",
            placeholder="Enter your friend's code or username",
            key="friend_code_input",
        )
        submitted = st.form_submit_button("Send friend request")
    if submitted:
        code = friend_code.strip()
        if not code:
            st.warning("Please enter a friend code or username.")
        else:
            try:
                result = send_friend_request(username, code)
                msg = result.get("message", "Friend request sent.")
                st.success(msg)
            except Exception as exc:
                st.error(f"Unable to send friend request: {exc}")

    st.markdown("---")

    # ---- 2) Incoming friend requests ----
    st.markdown("### Incoming friend requests")
    try:
        requests = fetch_friend_requests(username)
    except Exception as exc:
        requests = []
        st.error(f"Unable to load friend requests: {exc}")

    if not requests:
        st.caption("No incoming requests.")
    else:
        for req in requests:
            rid = req.get("id")
            from_user = req.get("from_user") or req.get("from_username") or "Unknown"
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"- **{from_user}** wants to add you.")
            with col2:
                if st.button("Accept", key=f"accept-{rid}"):
                    try:
                        result = accept_friend_request(username, rid)
                        msg = result.get("message", "Friend added.")
                        st.success(msg)
                        st.experimental_rerun()
                    except Exception as exc:
                        st.error(f"Unable to accept request: {exc}")

    st.markdown("---")

    # ---- 3) Friend list ----
    st.markdown("### Your friends")
    try:
        friends = fetch_friends(username)
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    if not friends:
        st.caption("You have no friends yet.")
    else:
        for f in friends:
            name = f.get("display_name") or f.get("username") or "Friend"
            st.markdown(f"- {name}")
