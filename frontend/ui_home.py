from __future__ import annotations
import streamlit as st
from datetime import datetime as _dt
from typing import Dict, Any, List
from streamlit_autorefresh import st_autorefresh  # 引入：自动刷新

# 从 ui_chat 导入我们刚才写好的核心逻辑
from ui_chat import render_rich_message, normalize_group_message 

from api import (
    fetch_groups, create_group, join_group, leave_group, 
    fetch_group_messages, send_group_message, fetch_group_members, fetch_group_members_detailed,
    ask_ai_recommend,
    fetch_friends, fetch_friend_requests, send_friend_request, accept_friend_request, get_or_create_dm,
    send_planning_message,
    invite_group_member, kick_group_member,
    remove_friend
)
from state import in_group
from ui_common import render_message_bubble

def render_social_panel(username: str):
    """Mobile-friendly navigation panel (groups, friends, profile)."""
    try: all_groups = fetch_groups()
    except: all_groups = []
    try: friends = fetch_friends()
    except: friends = []
    try: pending_reqs = fetch_friend_requests()
    except: pending_reqs = []

    display_groups = [g for g in all_groups if not (g.get("name") or "").upper().startswith("DM:")]

    with st.container(border=True):
        st.markdown("### 🏔 Groups")
        if not display_groups:
            st.caption("No groups yet.")
        for g in display_groups:
            gid = g.get("id")
            name = g.get("name") or "Group"
            is_active = st.session_state.get("active_group") == gid
            label = f"📍 {name}" if is_active else f"# {name}"
            if st.button(label, key=f"btn_group_{gid}", type="primary" if is_active else "secondary", use_container_width=True):
                st.session_state.active_group = gid
                st.rerun()

        with st.expander("➕ Create Group"):
            new_grp_name = st.text_input("Group Name", key="new_grp_name")
            friend_options = {f"{f['username']} (@{f['user_code']})": f['user_code'] for f in friends}
            selected_labels = st.multiselect("Invite Friends", options=list(friend_options.keys()), key="create_grp_invite")
            if st.button("Create", key="do_create_grp", use_container_width=True):
                if new_grp_name:
                    try:
                        codes = [friend_options[l] for l in selected_labels]
                        res = create_group(new_grp_name, codes)
                        st.toast("Group Created Successfully! 🎉")
                        st.session_state.active_group = res["group_id"]
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Please enter a group name.")

    with st.container(border=True):
        st.markdown("### 👥 Friends")
        if friends:
            for f in friends:
                fid = f.get("id")
                name = f.get("display_name") or f.get("username")
                code = f.get("user_code")
                if st.button(f"👤 {name}", key=f"dm_sidebar_{fid}", use_container_width=True, help=f"ID: {code}"):
                    try:
                        dm_id = get_or_create_dm(fid)
                        st.session_state.active_group = dm_id
                        st.rerun()
                    except Exception as e: st.error(str(e))
        else:
            st.caption("No friends added yet.")

        pending_count = len(pending_reqs)
        add_label = f"👋 Add Friend 🔴 ({pending_count})" if pending_count > 0 else "👋 Add Friend"
        with st.expander(add_label, expanded=(pending_count > 0)):
            if pending_reqs:
                st.info("Pending Requests:")
                for r in pending_reqs:
                    if st.button(f"Accept {r['from_username']}", key=f"acc_{r['id']}", type="primary", use_container_width=True):
                        accept_friend_request(r['id'])
                        st.toast(f"You are now friends with {r['from_username']}! 🤝")
                        st.rerun()
                st.divider()

            new_friend_code = st.text_input("Enter Friend's ID", key="new_friend_code")
            if st.button("Send Request", key="do_add_friend", use_container_width=True):
                if new_friend_code:
                    try: 
                        send_friend_request(new_friend_code)
                        st.toast(f"Request sent to {new_friend_code} 🚀")
                    except Exception as e: st.error(f"Failed: {e}")

def render_ai_interface(username: str):
    """首页的 AI 助手界面 (非群聊)"""
    st.title("🤖 Trail Assistant")
    st.caption("Ask me about trails, weather, gear, or safety.")
    
    # 这里也可以加上自动刷新，以防 AI 回复慢
    st_autorefresh(interval=5000, key="ai_home_refresh")

    with st.container(border=True, height=500):
        for msg in st.session_state.messages: 
            # 尝试用 render_rich_message 渲染，支持卡片
            try:
                render_rich_message(msg)
            except:
                render_message_bubble(msg)

    prompt = st.chat_input("Ask HikeBot...", key="ai_chat_input")
    if prompt:
        st.session_state.messages.append({"sender": username, "role": "user", "content": prompt, "timestamp": _dt.utcnow().isoformat()})
        st.rerun()

def process_ai_response():
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "user":
        try: reply = send_planning_message(msgs[-1]["content"])
        except Exception as exc: reply = f"⚠️ Error: {exc}"
        msgs.append({"sender": "HikeBot", "role": "assistant", "content": reply, "timestamp": _dt.utcnow().isoformat()})
        st.rerun()

def render_group_interface(group_id: str, username: str):
    """渲染主群聊界面 (集成自动刷新 + 卡片消息)"""
    
    # 🔥 核心功能 1: 自动刷新 (每 5 秒拉取最新消息)
    st_autorefresh(interval=5000, key=f"chat_refresh_{group_id}")

    # 💥 核心修复：将所有 API 调用移到顶部，确保数据在布局前加载
    members = [] 
    all_grps = []
    
    # --- 提前加载数据 ---
    try:
        members = fetch_group_members_detailed(group_id)
    except Exception as e:
        st.error(f"Failed to load group members: {e}")
        members = [] # 确保失败时是空列表
        
    try:
        all_grps = fetch_groups()
    except Exception:
        all_grps = [] # 确保失败时是空列表

    # 1. 判断是私聊 (DM) 还是群聊
    is_dm = False
    group_name = "Chat Room"
    
    for g in all_grps:
        if g["id"] == group_id: 
            group_name = g["name"]
            if group_name.startswith("DM:"):
                is_dm = True
                group_name = group_name.replace("DM: ", "💬 ")
            break
    
    st.title(group_name)
    if st.button("🚪 Exit", key=f"leave_{group_id}", use_container_width=True):
        leave_group(group_id)
        st.session_state.active_group = None
        st.rerun()

    with st.container(border=True):
        st.markdown("#### ✨ AI Copilot")
        st.caption("I'm listening for your plans...")
        if st.button("🗺 Recommend Trails", use_container_width=True):
            ask_ai_recommend(group_id)
            st.toast("AI is thinking... wait a few seconds!")
            st.rerun()

    # Members panel (stacked for mobile)
    with st.container(border=True):
        st.markdown("#### 👥 Members")
        
        my_role = "member"
        current_uid = st.session_state.get("current_user_id")

        if not members:
            st.caption("No members loaded or API failed.")
        
        for m in members:
            if m.get("user_id") == current_uid:
                my_role = m.get("role")
                break
        
        for m in members:
            role_icon = "👑" if m["role"] == "admin" else "👤"
            st.write(f"{role_icon} **{m['username']}**")
            st.caption(f"@{m['user_code']}")
            
            if my_role == "admin" and m["user_id"] != current_uid:
                if is_dm:
                    if st.button("🚫 Delete Friend", key=f"del_{m['user_id']}", type="primary", use_container_width=True):
                        remove_friend(m["user_id"])
                        try: kick_group_member(group_id, m["user_id"])
                        except: pass
                        st.toast(f"Friend {m['username']} removed.")
                        st.session_state.active_group = None 
                        st.rerun()
                else:
                    if st.button("Kick", key=f"kick_{m['user_id']}", type="primary", use_container_width=True):
                        kick_group_member(group_id, m["user_id"])
                        st.rerun()
            st.markdown("---")

        if not is_dm and my_role == "admin":
            with st.expander("Invite User"):
                inv_code = st.text_input("User ID", key=f"inv_c_{group_id}")
                if st.button("Invite", key=f"do_inv_{group_id}", use_container_width=True):
                    try: invite_group_member(group_id, inv_code); st.success("Invited!")
                    except Exception as e: st.error(f"Error: {e}")

    # Chat area
    with st.container(border=True, height=520):
        try: raws = fetch_group_messages(group_id)
        except: raws = []
        
        if not raws: 
            st.caption("Start the conversation!")
        
        for raw in raws:
            msg = normalize_group_message(raw)
            render_rich_message(msg)

    username_val = st.session_state.get("user")
    is_member = any(m.get("username") == username_val for m in members)

    if not is_member and not is_dm:
         if st.button("Join this group", type="primary", use_container_width=True): 
             join_group(group_id); st.rerun()
    else:
         group_name_display = group_name.replace("💬 ", "")
         if st.chat_input(f"Message {group_name_display}...", key=f"chat_in_{group_id}"):
             send_group_message(group_id, st.session_state[f"chat_in_{group_id}"])
             st.rerun()
                 
def render_home_page(username: str) -> None:
    active_group_id = st.session_state.get("active_group")
    if st.session_state.active_group is None:
        process_ai_response()

    st.markdown("## 📱 HikeBot")
    st.caption("Mobile-friendly planning and group chat")

    if active_group_id: 
        render_group_interface(active_group_id, username)
    else: 
        render_ai_interface(username)
        render_social_panel(username)
