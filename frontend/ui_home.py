from __future__ import annotations
import streamlit as st
from datetime import datetime as _dt
from typing import Dict, Any, List
from streamlit_autorefresh import st_autorefresh  # ✅ 关键引入：自动刷新

# 从 ui_chat 导入我们刚才写好的高级渲染函数
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

# (删除了本地的 normalize_group_message，直接使用 ui_chat 的版本以保持一致)

def render_social_sidebar(username: str):
    """渲染左侧的好友/群组导航栏"""
    c_ref, c_prof = st.columns([1, 3])
    with c_ref:
        if st.button("🔄", help="Refresh Data"): st.rerun()
    with c_prof: st.caption("Last updated: Just now")

    my_code = st.session_state.get("user_code", "Loading...")
    with st.container(border=True):
        st.markdown(f"**👤 {username}**")
        st.code(my_code, language="text")
        st.caption("Share this ID with friends.")

    st.markdown("---")

    try: all_groups = fetch_groups()
    except: all_groups = []
    try: friends = fetch_friends()
    except: friends = []
    try: pending_reqs = fetch_friend_requests()
    except: pending_reqs = []
    
    pending_count = len(pending_reqs)
    if pending_count > 0: st.warning(f"🔔 {pending_count} Friend Request(s)")

    display_groups = [g for g in all_groups if not (g.get("name") or "").upper().startswith("DM:")]

    st.markdown("### 🏔 Groups")
    if st.button("🤖 AI Assistant", key="btn_group_ai", use_container_width=True):
        st.session_state.active_group = None
        st.rerun()

    for g in display_groups:
        gid = g.get("id")
        name = g.get("name") or "Group"
        is_active = st.session_state.get("active_group") == gid
        label = f"📍 {name}" if is_active else f"# {name}"
        type_primary = "primary" if is_active else "secondary"
        if st.button(label, key=f"btn_group_{gid}", type=type_primary, use_container_width=True):
            st.session_state.active_group = gid
            st.rerun()

    st.markdown("---")
    st.markdown("### 👥 Friends")
    if not friends: st.caption("No friends added yet.")
    else:
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

    st.markdown("---")
    
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

    add_label = f"👋 Add Friend 🔴 ({pending_count})" if pending_count > 0 else "👋 Add Friend"
    with st.expander(add_label, expanded=(pending_count > 0)):
        if pending_reqs:
            st.info("Pending Requests:")
            for r in pending_reqs:
                col_info, col_btn = st.columns([3, 2])
                with col_info:
                    st.write(f"**{r['from_username']}**")
                    st.caption(f"ID: {r['from_user_code']}")
                with col_btn:
                    if st.button("Accept", key=f"acc_{r['id']}", type="primary"):
                        accept_friend_request(r['id'])
                        st.toast(f"You are now friends with {r['from_username']}! 🤝")
                        st.rerun()
            st.divider()

        st.write("Add by ID:")
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

    # 1. 判断是私聊 (DM) 还是群聊
    is_dm = False
    group_name = "Chat Room"
    try:
        all_grps = fetch_groups()
        for g in all_grps:
            if g["id"] == group_id: 
                group_name = g["name"]
                if group_name.startswith("DM:"):
                    is_dm = True
                    group_name = group_name.replace("DM: ", "💬 ")
                break
    except: pass
    
    # Header
    c1, c2 = st.columns([6, 1.5])
    with c1: st.title(group_name)
    with c2:
        if st.button("🚪 Exit", key=f"leave_{group_id}"):
            leave_group(group_id)
            st.session_state.active_group = None
            st.rerun()

    col_chat, col_info = st.columns([3, 1])

    with col_info:
        # AI Actions
        with st.container(border=True):
            st.markdown("#### ✨ AI Copilot")
            st.caption("I'm listening for your plans...")
            if st.button("🗺 Recommend Trails", use_container_width=True):
                # 触发后台任务
                ask_ai_recommend(group_id)
                st.toast("AI is thinking... wait a few seconds!")
                # 注意：这里不需要手动等待，st_autorefresh 会自动刷出结果
                st.rerun()

        st.markdown("---")
        st.markdown("#### 👥 Members")
        try:
            members = fetch_group_members_detailed(group_id)
            my_role = "member"
            current_uid = st.session_state.get("current_user_id")
            for m in members:
                if m.get("user_id") == current_uid:
                    my_role = m.get("role")
                    break
            
            for m in members:
                role_icon = "👑" if m["role"] == "admin" else "👤"
                st.write(f"{role_icon} **{m['username']}**")
                st.caption(f"@{m['user_code']}")
                
                # Logic: If Admin AND not myself
                if my_role == "admin" and m["user_id"] != current_uid:
                    # 🟢 UI Logic Switch: DM vs Group
                    if is_dm:
                        if st.button("🚫 Delete Friend", key=f"del_{m['user_id']}", type="primary"):
                            remove_friend(m["user_id"])
                            try: kick_group_member(group_id, m["user_id"])
                            except: pass
                            st.toast(f"Friend {m['username']} removed.")
                            st.session_state.active_group = None 
                            st.rerun()
                    else:
                        if st.button("Kick", key=f"kick_{m['user_id']}", type="primary"):
                            kick_group_member(group_id, m["user_id"])
                            st.rerun()
                st.markdown("---")

            if not is_dm:
                with st.expander("Invite User"):
                    inv_code = st.text_input("User ID", key=f"inv_c_{group_id}")
                    if st.button("Invite", key=f"do_inv_{group_id}", use_container_width=True):
                        try: invite_group_member(group_id, inv_code); st.success("Invited!")
                        except Exception as e: st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Load failed: {e}")

    with col_chat:
        with st.container(border=True, height=550):
            try: raws = fetch_group_messages(group_id)
            except: raws = []
            
            if not raws: 
                st.caption("Start the conversation!")
            
            for raw in raws:
                # 🔥 核心功能 2: 使用 ui_chat 的逻辑渲染精美卡片
                msg = normalize_group_message(raw)
                render_rich_message(msg)

        current_members = [m["username"] for m in members] if 'members' in locals() else []
        username_val = st.session_state.get("user")
        
        # 简单的权限检查，防止未加入者发言
        is_member = False
        if members:
            for m in members:
                if m['username'] == username_val:
                    is_member = True
                    break

        if not is_member and not is_dm:
             if st.button("Join this group", type="primary"): join_group(group_id); st.rerun()
        else:
             if st.chat_input(f"Message {group_name}...", key=f"chat_in_{group_id}"):
                 send_group_message(group_id, st.session_state[f"chat_in_{group_id}"])
                 st.rerun()

def render_home_page(username: str) -> None:
    if st.session_state.active_group is None: process_ai_response()
    col_left, col_right = st.columns([1, 4], gap="medium")
    with col_left: render_social_sidebar(username)
    with col_right:
        if st.session_state.get("active_group"): render_group_interface(st.session_state.active_group, username)
        else: render_ai_interface(username)