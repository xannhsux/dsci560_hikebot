from __future__ import annotations

import streamlit as st

from state import init_state
from api import auth_request, fetch_routes, fetch_groups, fetch_friends, fetch_friend_requests
from ui_home import render_home_page
from ui_chat import render_chat_page, render_members_panel
from ui_friends import render_add_friend_page
from ui_groups import render_create_group_page


def render_auth_gate() -> None:
    st.subheader("Login or Sign up")
    login_tab, signup_tab = st.tabs(["Login", "Sign up"])

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
            username = st.text_input("New username", key="signup_username")
            password = st.text_input("New password", type="password", key="signup_password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                msg = auth_request("/auth/signup", username, password)
                st.session_state.user = username
                st.session_state.current_user = username
                st.success(msg)
                st.rerun()
            except Exception as exc:
                st.error(f"Signup failed: {exc}")


def render_top_bar(username: str) -> None:
    top = st.container()
    with top:
        left_col, mid_col, right_col = st.columns([2, 3, 3])

        with left_col:
            st.markdown(f"**Logged in as:** `{username}`")

        with mid_col:
            st.markdown("### HikeBot – Group Trip Planner")

        with right_col:
            nav1, nav2, nav3, nav4 = st.columns(4)
            with nav1:
                if st.button("🏠 Home", key="nav_home"):
                    st.session_state.view_mode = "home"
                    st.rerun()
            with nav2:
                if st.button("👥 Friends", key="nav_friends"):
                    st.session_state.view_mode = "friends"
                    st.rerun()
            with nav3:
                if st.button("👨‍👩‍👧 Groups", key="nav_groups"):
                    st.session_state.view_mode = "groups"
                    st.rerun()
            with nav4:
                if st.button("🚪 Logout", key="nav_logout"):
                    for key in [
                        "user",
                        "user_code",
                        "current_user",
                        "active_group",
                        "view_mode",
                    ]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()


def render_sidebar(username: str) -> None:
    with st.sidebar:
        st.header("Trip Explorer")

        # browse routes
        try:
            routes = fetch_routes()
        except Exception as exc:
            st.error(f"Unable to load routes: {exc}")
            routes = []

        chosen_route = None
        if routes:
            route_labels = [
                f"{r.get('name', 'Route')} — {r.get('location', '')}"
                for r in routes
            ]
            selected_label = st.selectbox(
                "Pick a route to inspect",
                route_labels,
                key="sidebar_route_select",
            )
            idx = route_labels.index(selected_label)
            chosen_route = routes[idx]
            st.markdown(f"**Selected route:** {chosen_route.get('name', 'Route')}")

        st.markdown("---")
        st.subheader("Active Group")
        render_members_panel()


def render_main_home(username: str) -> None:
    st.subheader("Plan your next hike")

    col_main, col_side = st.columns([3, 1])

    with col_main:
        render_home_page(username)

    with col_side:
        st.markdown("### Quick stats")
        st.write("This column can show quick tips, recent trips, etc.")
        st.info(
            "• Use the **Friends** tab to add partners.\n"
            "• Use **Groups** to create a dedicated chat for each trip."
        )

    st.markdown("---")
    st.markdown("### Social overview")

    # friend request notification badge
    pending_count = 0
    try:
        fr = fetch_friend_requests()
        pending_count = len(fr) if isinstance(fr, list) else len(fr.get("requests", []))
    except Exception:
        pending_count = 0

    if pending_count > 0:
        friends_label = f"Friends 🔴 ({pending_count})"
    else:
        friends_label = "Friends"

    tab_friends, tab_groups = st.tabs([friends_label, "Groups"])

    # ---- Friends tab ----
    with tab_friends:
        try:
            friends = fetch_friends()
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
                code = f.get("user_code") or ""
                st.markdown(f"- **{name}**  (`{code}`)")

            if st.button("Go to friend management", key="go_friends_page"):
                st.session_state.view_mode = "friends"
                st.rerun()

    # ---- Groups tab ----
    with tab_groups:
        try:
            groups = fetch_groups()
        except Exception as exc:
            groups = []
            st.error(f"Unable to load groups: {exc}")

        if not groups:
            st.caption("No groups yet. Create one from the top navigation.")
        else:
            for g in groups:
                gid = g.get("id")
                name = g.get("name") or "Group"
                desc = g.get("description") or ""
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{name}**  \n{desc}")
                with col2:
                    if st.button("Enter chat", key=f"enter_group_{gid}"):
                        st.session_state.active_group = gid
                        st.session_state.view_mode = "chat"
                        st.rerun()


def main() -> None:
    st.set_page_config(page_title="HikeBot", page_icon="🥾", layout="wide")
    init_state()

    username = st.session_state.get("user") or st.session_state.get("current_user")

    if not username:
        render_auth_gate()
        return

    render_top_bar(username)

    sidebar_col, main_col = st.columns([1, 3])

    with sidebar_col:
        render_sidebar(username)

    with main_col:
        view_mode = st.session_state.get("view_mode", "home")

        if view_mode == "home":
            render_main_home(username)
        elif view_mode == "chat":
            render_chat_page(username)
        elif view_mode == "friends":
            render_add_friend_page(username)
        elif view_mode == "groups":
            render_create_group_page(username)
        else:
            st.write("Unknown view mode, going back to home.")
            st.session_state.view_mode = "home"
            st.rerun()


if __name__ == "__main__":
    main()
