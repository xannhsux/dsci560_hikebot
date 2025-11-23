from __future__ import annotations

import streamlit as st

from state import init_state
from api import auth_request, fetch_routes, fetch_groups, fetch_friends, fetch_friend_requests
from ui_home import render_home_page
from ui_chat import render_chat_page, render_members_panel
from ui_friends import render_add_friend_page
from ui_groups import render_create_group_page


def inject_theme() -> None:
    """Global theming for a bright hiking look."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Source+Serif+4:wght@500&display=swap');
        :root {
            --bg: #f6f3ea;
            --panel: #f0eddf;
            --card: #ffffff;
            --accent: #1f7a50;
            --accent-2: #d9a441;
            --stroke: rgba(31, 122, 80, 0.18);
            --text: #123124;
            --muted: #5e7a68;
        }
        .stApp {
            background: radial-gradient(140% 140% at 10% 10%, #ffffff 0%, #f6f3ea 50%, #eef3eb 100%);
            color: var(--text);
            font-family: 'Space Grotesk', 'Helvetica Neue', sans-serif;
        }
        section[data-testid="stSidebar"] {
            background: #f4f1e6;
            border-right: 1px solid rgba(31, 122, 80, 0.08);
        }
        .top-bar {
            background: linear-gradient(135deg, rgba(31,122,80,0.08), rgba(217,164,65,0.08));
            padding: 14px 18px;
            border: 1px solid var(--stroke);
            border-radius: 12px;
            margin-bottom: 14px;
        }
        .hero {
            background: linear-gradient(120deg, rgba(31,122,80,0.1), rgba(217,164,65,0.06));
            border: 1px solid var(--stroke);
            border-radius: 18px;
            padding: 18px 20px;
            margin-bottom: 14px;
        }
        .pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(31,122,80,0.12);
            border: 1px solid var(--stroke);
            color: var(--accent);
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            letter-spacing: 0.4px;
        }
        .card {
            background: var(--card);
            border: 1px solid rgba(31,122,80,0.12);
            border-radius: 14px;
            padding: 14px 16px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.08);
        }
        .metric {
            color: #1f5e3f;
            font-weight: 600;
        }
        .stButton > button, button[kind="secondary"] {
            background: linear-gradient(135deg, #1f7a50, #26895b);
            color: #f7f5ee;
            border-radius: 12px;
            border: 1px solid var(--stroke);
            font-weight: 600;
        }
        .stButton > button:hover {
            border-color: rgba(242,201,76,0.6);
        }
        input, textarea {
            border-radius: 10px !important;
            border: 1px solid rgba(31,122,80,0.2) !important;
            background: #ffffff !important;
            color: var(--text) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_gate() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="pill">Trail crew access</div>
          <h2 style="margin:6px 0 4px;">Log in or join the crew</h2>
          <p style="color: var(--muted); margin: 0;">Secure your handle and Hike ID to sync friends, groups, and weather-ready plans.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
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
            user_code = st.text_input(
                "Your user_code (4-16 letters/numbers)", key="signup_user_code"
            )
            submitted = st.form_submit_button("Create trail ID")
        if submitted:
            try:
                msg = auth_request("/auth/signup", username, password, user_code=user_code)
                st.session_state.user = username
                st.session_state.current_user = username
                st.success(msg)
                st.rerun()
            except Exception as exc:
                st.error(f"Signup failed: {exc}")


def render_top_bar(username: str) -> None:
    top = st.container()
    with top:
        st.markdown('<div class="top-bar">', unsafe_allow_html=True)
        left_col, mid_col, right_col = st.columns([2, 3, 3])

        with left_col:
            st.markdown(f"**Trail ID:** `{username}`")

        with mid_col:
            st.markdown("### HikeBot · Plan, Coordinate, Hike")

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
                if st.button("🗻 Groups", key="nav_groups"):
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
        st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar(username: str) -> None:
    with st.sidebar:
        st.markdown("### Route Explorer")

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
                "Pick a trail",
                route_labels,
                key="sidebar_route_select",
            )
            idx = route_labels.index(selected_label)
            chosen_route = routes[idx]
            st.markdown(
                f"<div class='card' style='margin-top:6px;'>"
                f"<div class='pill'>Trail card</div>"
                f"<h4 style='margin:6px 0 2px;'>{chosen_route.get('name', 'Route')}</h4>"
                f"<p style='margin:0;color:var(--muted);'>"
                f"{chosen_route.get('distance_km', '?')} km · "
                f"{chosen_route.get('elevation_gain_m', '?')} m gain · "
                f"{chosen_route.get('difficulty', '').title()}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

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
    inject_theme()
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
