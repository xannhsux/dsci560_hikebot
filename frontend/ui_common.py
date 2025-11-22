# ui_common.py
from __future__ import annotations
from datetime import datetime
from html import escape
from textwrap import dedent
from typing import Dict, Any

import streamlit as st


def render_message_bubble(msg: Dict[str, Any]) -> None:
    sender = msg.get("sender") or "User"
    content = msg.get("content", "")
    ts = msg.get("timestamp")
    is_me = sender == st.session_state.current_user

    align = "flex-end" if is_me else "flex-start"
    bubble_color = "#DCF8C6" if is_me else "#FFFFFF"

    time_str = ""
    if ts:
        try:
            time_str = datetime.fromisoformat(ts).strftime("%H:%M")
        except Exception:
            time_str = str(ts)

    s_sender = escape(sender)
    s_content = escape(content).replace("\n", "<br>")

    html = dedent(
        f"""
        <div style="display:flex;justify-content:{align};margin-bottom:10px;">
          <div style="max-width:75%;font-size:14px;">
            <div style="color:#888;font-size:12px;margin-bottom:2px;">
              {s_sender} · {time_str}
            </div>
            <div style="background:{bubble_color};padding:10px 14px;
                        border-radius:16px;box-shadow:0 1px 2px rgba(0,0,0,0.1);">
              {s_content}
            </div>
          </div>
        </div>
        """
    ).strip()
    st.markdown(html, unsafe_allow_html=True)
