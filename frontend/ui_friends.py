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

    # ← 返回主页按钮
    if st.button("← Back to home", key="back_from_add_friend"):
        st.session_state.view_mode = "home"
        st.rerun()

    # ---- 1) 发送好友请求 ----
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
                # ✅ 不再把 username 传给 API（避免参数数量不匹配）
                res = send_friend_request(username, friend_code.strip())
                name = res.get("username") or res.get("display_name") or friend_code
                st.success(f"Friend request sent to {name}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to send friend request: {exc}")

    st.markdown("---")

    # ---- 2) 待处理的好友请求 ----
    st.markdown("### Incoming friend requests")
    try:
        # ✅ 改这里：不再传 username
        requests = fetch_friend_requests()
    except Exception as exc:
        requests = []
        st.error(f"Unable to load friend requests: {exc}")

    if not requests:
        st.caption("No incoming requests.")
    else:
        for req in requests:
            from_name = req.get("from_username") or "Someone"
            from_code = req.get("from_user_code") or "N/A"
            rid = req.get("id")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"- **{from_name}** ({from_code}) wants to add you.")
            with col2:
                if st.button("Accept", key=f"accept-{rid}"):
                    try:
                        # 这里先保持不动，如果之后 accept 报类似错误再一起改
                        accept_friend_request(username, from_code)
                        st.success(f"You are now friends with {from_name}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Unable to accept request: {exc}")

    st.markdown("---")

    # ---- 3) 好友列表 ----
    st.markdown("### Your friends")
    try:
        # ✅ 改这里：不再传 username
        friends = fetch_friends()
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    if not friends:
        st.caption("You have no friends yet.")
    else:
        for f in friends:
            name = f.get("display_name") or f.get("username") or "Friend"
            st.markdown(f"- {name}")
