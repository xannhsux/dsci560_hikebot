# app.py
from __future__ import annotations

import streamlit as st

from state import init_state
from api import auth_request, fetch_routes
from ui_home import render_home_page
from ui_chat import render_chat_page, render_members_panel
from ui_common import render_message_bubble  # if needed in future
from api import fetch_groups, fetch_friends
from ui_friends import render_add_friend_page
from ui_groups import render_create_group_page
from api import fetch_friend_requests



def render_auth_gate() -> None:
    st.subheader("Login or Sign up")
    login_tab, signup_tab = st.tabs(["Login", "Sign up"])

    from api import auth_request

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
            try:
                msg = auth_request("/auth/login", username, password)
                st.session_state.user = username
                st.session_state.current_user = username
                st.success(msg)
                st.rerun()
            except Exception as exc:
                st.error(f"Login failed: {exc}")
    with signup_tab:
        with st.form("signup_form"):
            username = st.text_input("Username")
            user_code = st.text_input(
                "Hike ID (User Code)",
                help="4–16 letters or numbers. This will be your unique ID for adding friends."
        )
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            try:
                msg = auth_request("/auth/signup", username, password, user_code)
                st.success(msg)
                st.rerun()
            except Exception as exc:
                st.error(f"Signup failed: {exc}")
    


def render_top_bar(username: str) -> None:
    top = st.container()
    with top:
        col_l, col_r = st.columns([2, 2])
        with col_l:
            st.title("HikeBot")
            st.caption("Hiking group companion for routes, weather, gear, and safety tips.")
        with col_r:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if st.button("Add Friend"):
                    # Switch center panel to the Add Friend page
                    st.session_state.view_mode = "add_friend"
            with c2:
                if st.button("Create Group"):
                    st.session_state.view_mode = "create_group"

            with c3:
                st.markdown(f"**Logged in as `{username}`**")



def render_sidebar_tabs(username: str) -> None:
    st.markdown("### People")
    from api import fetch_groups, fetch_friends

    # ---- compute pending friend requests for badge ----
    pending_count = 0
    try:
        requests = fetch_friend_requests(username)
        pending_count = len(requests)
    except Exception:
        # Don't break sidebar if backend fails
        pending_count = 0

    friends_label = "Friends"
    if pending_count > 0:
        # Red dot style label, e.g. "Friends 🔴 (3)"
        friends_label = f"Friends 🔴 ({pending_count})"

    tab_friends, tab_groups = st.tabs([friends_label, "Groups"])

    # ---- Friends tab ----
    with tab_friends:
        try:
            friends = fetch_friends(username)
        except Exception as exc:
            friends = []
            st.error(f"Unable to load friends: {exc}")

        if pending_count > 0:
            st.markdown(f"**You have {pending_count} pending friend request(s).**")

        if not friends:
            st.caption("No friends yet.")
        else:
            for f in friends:
                name = f.get("display_name") or f.get("username") or "Friend"
                friend_id = f.get("id")
                label = f"💬 {name}"
                if st.button(label, key=f"friend-{friend_id}"):
                    st.session_state.active_group = f"friend:{friend_id}"
                    st.session_state.view_mode = "chat"

    # ---- Groups tab ----
    with tab_groups:
        try:
            groups = fetch_groups(username)
        except Exception as exc:
            groups = []
            st.error(f"Unable to load groups: {exc}")

        if not groups:
            st.caption("No groups yet. Create one from the top-right button.")
            return

        for g in groups:
            gid = g["id"]
            name = g.get("name", "Unnamed group")
            label = f"👥 {name}"
            is_active = (gid == st.session_state.active_group)
            if is_active:
                label = "✅ " + label

            if st.button(label, key=f"group-{gid}"):
                st.session_state.active_group = gid
                st.session_state.view_mode = "chat"



def main() -> None:
    st.set_page_config(page_title="HikeBot Chat", page_icon="🥾", layout="wide")
    init_state()

    user = st.session_state.get("user")
    if not user:
        render_auth_gate()
        return

    st.session_state.current_user = user

    render_top_bar(user)

    col_sidebar, col_main, col_members = st.columns([1.2, 2.6, 1.2])

    with col_sidebar:
        render_sidebar_tabs(user)

    with col_main:
        if st.session_state.view_mode == "home":
            render_home_page(user)
        elif st.session_state.view_mode == "chat":
            render_chat_page(user)
        elif st.session_state.view_mode == "add_friend":
            render_add_friend_page(user)
        elif st.session_state.view_mode == "create_group":
            render_create_group_page(user)

        else:
            # Fallback to home if unknown
            st.session_state.view_mode = "home"
            render_home_page(user)


    with col_members:
        if st.session_state.view_mode == "chat":
            render_members_panel(st.session_state.active_group, user)
        elif st.session_state.view_mode == "add_friend":
            st.subheader("Tips")
            st.caption("Use the center panel to add new friends or accept requests.")
        else:
            st.subheader("Group Members")
            st.caption("Open a group chat to see who is going.")

    st.markdown("---")
    if st.button("Log out"):
        for key in list(st.session_state.keys()):
            st.session_state.pop(key, None)
        st.experimental_rerun()

# ---- Create Group API ----

def create_group(username: str, group_name: str, members: List[str]) -> Dict[str, Any]:
    """
    Create a new group with group_name and initial members.
    Adjust payload or endpoint based on your backend implementation.
    """
    payload = {
        "creator": username,
        "group_name": group_name,
        "members": members,
    }
    r = requests.post(
        f"{BACKEND_URL}/social/groups/create",
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()



if __name__ == "__main__":
    main()
