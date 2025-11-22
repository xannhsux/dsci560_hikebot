# ui_groups.py

from __future__ import annotations
from typing import List, Dict, Any

import streamlit as st

from api import fetch_friends, create_group


def render_create_group_page(username: str) -> None:
    """
    UI for creating a new group.
    User chooses:
        - group name
        - members (multi-select from friends)
        - extra usernames (strangers) via text input
    """
    st.subheader("Create a New Group")

    # ---- 1) Group name ----
    group_name = st.text_input(
        "Group name",
        placeholder="Enter a name for your group (e.g., Weekend Hiking Squad)",
        key="create_group_name",
    )

    st.markdown("---")

    # ---- 2) Select members from friend list ----
    st.markdown("### Select members to invite (friends)")

    try:
        friends = fetch_friends(username)
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    friend_labels_to_username: Dict[str, str] = {}

    if not friends:
        st.caption("You have no friends to add.")
        selected_friend_labels: List[str] = []
    else:
        friend_labels_to_username = {
            f.get("display_name") or f.get("username") or "Friend": f.get("username")
            for f in friends
        }
        labels = list(friend_labels_to_username.keys())

        selected_friend_labels = st.multiselect(
            "Choose one or more friends",
            labels,
            key="create_group_members",
        )

    # ---- 3) Extra strangers field ----
    st.markdown("### Add extra usernames (optional)")

    extra_raw = st.text_input(
        "Usernames separated by comma",
        placeholder="e.g. alice123, bob_smith, charlie",
        key="create_group_extra_usernames",
    )

    st.caption(
        "These usernames do not need to be in your friend list, "
        "but they must exist in the system for the invite to work."
    )

    st.markdown("---")

    # ---- 4) Create group button ----
    if st.button("Create Group", key="create_group_btn"):
        name_clean = group_name.strip()
        if not name_clean:
            st.warning("Please enter a group name.")
            return

        # Friends selected via multiselect
        friend_usernames: List[str] = [
            friend_labels_to_username[label]
            for label in selected_friend_labels
            if label in friend_labels_to_username
        ]

        # Extra strangers from text input
        extra_usernames: List[str] = []
        if extra_raw.strip():
            extra_usernames = [
                u.strip()
                for u in extra_raw.split(",")
                if u.strip()
            ]

        # Merge and deduplicate
        all_members = list(dict.fromkeys(friend_usernames + extra_usernames))

        try:
            result = create_group(username, name_clean, all_members)
            msg = result.get("message") or "Group created."
            group_id = result.get("group_id")
            st.success(f"{msg} (ID: {group_id})")

            # Automatically open the new group chat
            st.session_state.active_group = group_id
            st.session_state.view_mode = "chat"
            st.rerun()

        except Exception as exc:
            st.error(f"Unable to create group: {exc}")

