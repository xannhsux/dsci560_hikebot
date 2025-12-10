# frontend/app.py
from __future__ import annotations
import streamlit as st
from state import init_state
from api import auth_request
from ui_home import render_home_page

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
            --text: #123124;
            --muted: #5e7a68;
        }
        .stApp {
            background: radial-gradient(140% 140% at 10% 10%, #ffffff 0%, #f6f3ea 50%, #eef3eb 100%);
            color: var(--text);
            font-family: 'Space Grotesk', 'Helvetica Neue', sans-serif;
        }
        .card {
            background: var(--card);
            border: 1px solid rgba(31,122,80,0.12);
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .stButton > button {
            border-radius: 8px;
            font-weight: 500;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_auth_gate() -> None:
    st.markdown("## 👋 Welcome to HikeBot")
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
            user_code = st.text_input("Your user_code (4-16 chars)", key="signup_user_code")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            try:
                msg = auth_request("/auth/signup", username, password, user_code=user_code)
                st.session_state.user = username
                st.session_state.current_user = username
                st.success(msg)
                st.rerun()
            except Exception as exc:
                st.error(f"Signup failed: {exc}")

def render_header(username: str):
    c1, c2 = st.columns([5, 1])
    with c1:
        st.caption(f"Logged in as **{username}**")
    with c2:
        if st.button("Logout", key="logout_btn", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

def main() -> None:
    st.set_page_config(page_title="HikeBot", page_icon="🥾", layout="wide")
    inject_theme()
    init_state()

    username = st.session_state.get("user") or st.session_state.get("current_user")

    if not username:
        render_auth_gate()
        return

    render_header(username)
    # 调用新的 render_home_page，它现在集成了自动刷新和卡片渲染
    render_home_page(username)

if __name__ == "__main__":
    main()