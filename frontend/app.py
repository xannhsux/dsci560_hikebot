from __future__ import annotations

import streamlit as st

from state import init_state
from api import auth_request
from ui_home import render_home_page
from ui_chat import render_chat_page
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


def render_main_home(username: str) -> None:
    st.subheader("Trail Assistant")
    render_home_page(username)


def main() -> None:
    st.set_page_config(page_title="Trail Mind", page_icon="🥾", layout="wide")
    inject_theme()
    init_state()

    username = st.session_state.get("user") or st.session_state.get("current_user")

    if not username:
        render_auth_gate()
        return

    render_top_bar(username)

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
