from __future__ import annotations
import json
import re
import datetime
import streamlit as st
from typing import Dict, Any
from streamlit_autorefresh import st_autorefresh

from api import (
    fetch_group_messages,
    send_group_message,
    fetch_group_members,
    join_group,
    leave_group,
)
from state import ensure_members_cached, in_group
from ui_common import render_message_bubble


def normalize_group_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize backend group message payload."""
    sender = raw.get("sender") or raw.get("sender_display") or "Unknown"
    content = raw.get("content", "")
    ts = raw.get("timestamp") or raw.get("created_at")
    role = raw.get("role", "user")
    msg_id = raw.get("id") or str(ts)
    return {"id": msg_id, "sender": sender, "content": content, "timestamp": ts, "role": role}


def render_rich_message(msg: Dict[str, Any]) -> None:
    """
    智能渲染：如果消息包含 JSON 行程单，渲染为精美卡片。
    🔥 修复：使用 Markdown 替代 st.columns 以避免嵌套错误。
    """
    sender = msg.get("sender", "Unknown")
    content = msg.get("content", "")
    
    is_card = False
    data = {}

    # --- 1. 尝试提取 JSON ---
    if content:
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and "title" in parsed and "stats" in parsed:
                    data = parsed
                    is_card = True
        except (json.JSONDecodeError, AttributeError):
            pass

    # --- 2. 渲染 UI 分支 ---
    if is_card:
        # === 🌲 渲染行程卡片 (Announcement) ===
        with st.chat_message("assistant", avatar="🏔️"):
            with st.container(border=True):
                st.markdown(f"### {data.get('title')}")
                st.caption(f"📢 Trip Announcement via {sender}")
                
                st.write(data.get('summary', ''))
                
                st.divider()

                # 🔥 关键修改：用 Markdown 表格代替 st.columns(2) 避免报错
                stats = data.get('stats', {})
                dist = stats.get('dist', 'N/A')
                elev = stats.get('elev', 'N/A')
                
                # 这种写法既美观又不会报错
                st.markdown(
                    f"""
                    | 📏 Distance | ⛰️ Elevation |
                    | :---: | :---: |
                    | **{dist}** | **{elev}** |
                    """
                )
                
                st.divider()
                
                # 天气 & 警告
                if data.get('weather_warning'):
                    st.info(f"🌤 {data.get('weather_warning')}")
                
                # 趣味冷知识
                if data.get('fun_fact'):
                    st.markdown(f"> 💡 **Fun Fact:** *{data.get('fun_fact')}*")
                
                # 装备清单
                gear = data.get('gear_required', [])
                if gear:
                    with st.expander("🎒 Gear List", expanded=False):
                        for item in gear:
                            st.checkbox(str(item), value=True, key=f"{msg.get('id')}_{item}", disabled=True)
    else:
        # === 💬 普通聊天消息 ===
        render_message_bubble(msg)


# ... (后面的 render_members_panel 和 render_chat_page 保持不变，可以直接保留或省略，因为 ui_home 才是主入口)
# 为了方便你复制，这里把后面部分也完整放上，确保你不会漏掉 import

def render_members_panel() -> None:
    st.subheader("Group Members")
    group_id = st.session_state.get("active_group")
    if not group_id: return
    
    username = st.session_state.get("user")
    members = ensure_members_cached(group_id, fetch_group_members)
    
    if members:
        for m in members:
            st.markdown(f"- **{m}**" + (" (you)" if m == username else ""))
    
    st.markdown("---")
    if in_group(group_id, username, fetch_group_members):
        if st.button("Quit Group", key="quit_grp_chat"):
             try: leave_group(group_id); st.session_state.active_group = None; st.rerun()
             except: pass

def render_chat_page(username: str) -> None:
    # 这个函数现在其实被 ui_home 取代了，但保留着也没事
    pass