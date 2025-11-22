# ui_groups.py

from api import fetch_friends, create_group
import streamlit as st
from typing import List, Dict, Any


def render_create_group_page(username: str) -> None:
    """
    UI for creating a new group.
    User chooses:
        - group name
        - members (multi-select from friends)
    """
    st.subheader("Create a hiking group")

    # ← 返回主页按钮
    if st.button("← Back to home", key="back_from_create_group"):
        st.session_state.view_mode = "home"
        st.rerun()

    # 1) 取好友列表 —— 不再传 username
    try:
        friends = fetch_friends()  # ✅ 修复：不再传参数
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    friend_labels: List[str] = []
    friend_map: Dict[str, Dict[str, Any]] = {}

    for f in friends:
        name = f.get("display_name") or f.get("username") or "Friend"
        code = f.get("user_code")
        label = f"{name} ({code})"
        friend_labels.append(label)
        friend_map[label] = f

    # 2) 填 group 名 + 邀请成员
    name = st.text_input("Group name")
    selected_labels = st.multiselect(
        "Invite friends (optional)",
        friend_labels,
    )

    # 成员代码
    member_codes = [friend_map[l]["user_code"] for l in selected_labels]
    all_members = list(dict.fromkeys(member_codes))  # 去重

    if st.button("Create Group", type="primary"):
        if not name.strip():
            st.error("Please enter a group name.")
            return

        name_clean = name.strip()

        try:
            # 保持原参数结构不变（之后如需换成 token 再一起改）
            result = create_group(username, name_clean, all_members)
            msg = result.get("message") or "Group created."
            group_id = result.get("group_id")
            st.success(f"{msg} (ID: {group_id})")

            st.session_state.active_group = group_id
            st.session_state.view_mode = "chat"
            st.rerun()

        except Exception as exc:
            st.error(f"Unable to create group: {exc}")
