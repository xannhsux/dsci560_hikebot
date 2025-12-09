# frontend/ui_friends.py
from __future__ import annotations
from typing import List, Dict, Any
import streamlit as st

from api import (
    fetch_friends,
    send_friend_request,
    fetch_friend_requests,
    accept_friend_request,
    get_or_create_dm,  # <--- 记得导入这个新函数
)


def render_add_friend_page(username: str) -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="pill">Trail partners</div>
          <h3 style="margin:6px 0;">Add & manage friends</h3>
          <p style="margin:0;color:var(--muted);">Share your Hike ID to build your crew and drop into group chats faster.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Back Button
    if st.button("← Back to home", key="back_from_add_friend"):
        st.session_state.view_mode = "home"
        st.rerun()

    # ---- Add Friend ----
    st.markdown("<div class='card'>", unsafe_allow_html=True)
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

    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Incoming Requests ----
    try:
        requests = fetch_friend_requests()
    except Exception:
        requests = []

    if requests:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### Incoming requests")
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
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Friends List (With Chat Button) ----
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Your friends")

    try:
        friends = fetch_friends()
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    if not friends:
        st.caption("You have no friends yet.")
    else:
        for f in friends:
            fid = f.get("id")
            name = f.get("display_name") or f.get("username") or "Friend"
            code = f.get("user_code") or ""
            
            # 使用列布局：左边显示名字，右边显示 Chat 按钮
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{name}** (`{code}`)")
            with c2:
                if st.button("💬 Chat", key=f"dm_btn_{fid}"):
                    try:
                        # 1. 获取或创建 DM Group
                        dm_group_id = get_or_create_dm(fid)
                        # 2. 设置状态跳转
                        st.session_state.active_group = dm_group_id
                        st.session_state.view_mode = "chat"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to open chat: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)