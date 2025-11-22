# state.py
from __future__ import annotations
from typing import Dict, List, Optional

import streamlit as st


def init_state() -> None:
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "messages" not in st.session_state:
        from datetime import datetime
        st.session_state.messages = [
            {
                "sender": "HikeBot",
                "role": "assistant",
                "content": "Hey trail crew! How can I help today?",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
    if "group_members" not in st.session_state:
        st.session_state.group_members: Dict[str, List[str]] = {}
    if "active_group" not in st.session_state:
        st.session_state.active_group: Optional[str] = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "home"
    if "sidebar_tab" not in st.session_state:
        st.session_state.sidebar_tab = "Groups"


def ensure_members_cached(group_id: str, fetcher) -> List[str]:
    """fetcher is usually api.fetch_group_members."""
    if not group_id:
        return []
    if group_id not in st.session_state.group_members:
        try:
            st.session_state.group_members[group_id] = fetcher(group_id)
        except Exception:
            st.session_state.group_members[group_id] = []
    return st.session_state.group_members[group_id]


def in_group(group_id: Optional[str], username: Optional[str], fetcher) -> bool:
    if not group_id or not username:
        return False
    members = ensure_members_cached(group_id, fetcher)
    return username.lower() in [m.lower() for m in members]
