# ui_groups.py

from api import fetch_friends, create_group
import streamlit as st
from typing import List, Dict, Any


def render_create_group_page(username: str) -> None:
    st.subheader("Create a hiking group")

    # Back Button
    if st.button("← Back to home", key="back_from_create_group"):
        st.session_state.view_mode = "home"
        st.rerun()

    # ---- Fetch friends ----
    try:
        friends = fetch_friends()
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

    # ---- Group Name + Members ----
    name = st.text_input("Group name")
    selected_labels = st.multiselect(
        "Invite friends (optional)",
        friend_labels,
    )

    member_codes = [friend_map[l]["user_code"] for l in selected_labels]
    all_members = list(dict.fromkeys(member_codes))

    # ---- Create Group ----
    if st.button("Create Group", type="primary"):
        if not name.strip():
            st.error("Please enter a group name.")
            return

        try:
            result = create_group(name.strip(), all_members)
            msg = result.get("message") or "Group created."
            group_id = result.get("group_id")

            st.success(f"{msg} (ID: {group_id})")

            # Auto open group chat
            st.session_state.active_group = group_id
            st.session_state.view_mode = "chat"
            st.rerun()

        except Exception as exc:
            st.error(f"Unable to create group: {exc}")
