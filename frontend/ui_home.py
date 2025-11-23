# ui_home.py
from __future__ import annotations
from typing import Any, Dict, List

from datetime import datetime
import streamlit as st

from api import request_weather, fetch_routes, send_planning_message
from ui_common import render_message_bubble


def render_hero(username: str, routes: List[Dict[str, Any]]) -> None:
    route_count = len(routes)
    easy = len([r for r in routes if r.get("difficulty") == "easy"])
    moderate = len([r for r in routes if r.get("difficulty") == "moderate"])
    hard = len([r for r in routes if r.get("difficulty") == "hard"])
    st.markdown(
        f"""
        <div class="hero">
          <div class="pill">Hike-ready</div>
          <h2 style="margin:6px 0 6px;">Hey {username}, pick a trail and rally the crew.</h2>
          <p style="color: var(--muted); margin-bottom: 10px;">
            Weather snapshots, gear hints, and group chat in one canvas.
          </p>
          <div style="display:flex;gap:18px;flex-wrap:wrap;">
            <div class="card" style="flex:1;min-width:160px;">
              <div style="color:var(--muted);font-size:12px;">Routes loaded</div>
              <div class="metric" style="font-size:26px;">{route_count}</div>
            </div>
            <div class="card" style="flex:1;min-width:160px;">
              <div style="color:var(--muted);font-size:12px;">Easy / Mod / Hard</div>
              <div class="metric" style="font-size:26px;">{easy} · {moderate} · {hard}</div>
            </div>
            <div class="card" style="flex:1;min-width:160px;">
              <div style="color:var(--muted);font-size:12px;">Chatbot</div>
              <div class="metric" style="font-size:26px;">Route tips & gear lists</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trail_grid(routes: List[Dict[str, Any]]) -> None:
    """Trail explorer displayed as cards."""
    st.markdown("#### Featured trails")

    if not routes:
        st.caption("No routes loaded yet.")
        return

    cols = st.columns(3)
    for idx, route in enumerate(routes[:6]):
        with cols[idx % 3]:
            st.markdown(
                f"""
                <div class="card" style="min-height: 150px; margin-bottom:10px;">
                  <div class="pill">#{route.get('difficulty', 'trail')}</div>
                  <h4 style="margin:8px 0 2px;">{route.get('name','Trail')}</h4>
                  <p style="margin:0;color:var(--muted);">
                    {route.get('location','')} · {route.get('distance_km','?')} km · {route.get('elevation_gain_m','?')} m gain
                  </p>
                  <p style="margin:6px 0 0; color:var(--text);">
                    ~{route.get('drive_time_min','?')} min drive
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )



def render_weather_query(routes: List[Dict[str, Any]]) -> None:
    st.markdown("#### Weather snapshot")

    if not routes:
        st.caption("No routes available to query weather.")
        return

    route_map = {f"{r['name']} — {r.get('location', '')}": r for r in routes}
    labels = list(route_map.keys())
    selected_label = st.selectbox("Select a trail", labels, key="weather_route_select")
    selected_route = route_map[selected_label]

    when = datetime.utcnow()
    st.caption(f"Querying weather around now: {when.isoformat(timespec='minutes')} (UTC)")

    if st.button("Check weather"):
        try:
            data = request_weather(selected_route["id"], when)
            st.json(data)
        except Exception as exc:
            st.error(f"Unable to fetch weather: {exc}")


def render_home_planning_chat(username: str) -> None:
    st.markdown("### Planning chat")

    box = st.container()
    with box:
        msgs = st.session_state.messages
        if not msgs:
            st.caption("No messages yet. Start the conversation!")
        else:
            for msg in msgs:
                render_message_bubble(msg)

    prompt = st.chat_input(
        "Ask about hikes, gear, weather, or safety…", key="home_chat_input"
    )
    if prompt:
        from datetime import datetime as _dt
        now_str = _dt.utcnow().isoformat()
        st.session_state.messages.append(
            {"sender": username, "role": "user", "content": prompt, "timestamp": now_str}
        )
        try:
            reply = send_planning_message(prompt)
        except Exception as exc:
            reply = f"⚠️ Unable to reach backend: {exc}"
        st.session_state.messages.append(
            {
                "sender": "HikeBot",
                "role": "assistant",
                "content": reply,
                "timestamp": _dt.utcnow().isoformat(),
            }
        )
        st.rerun()


def render_home_page(username: str) -> None:
    routes = fetch_routes()
    render_hero(username, routes)

    col1, col2 = st.columns([2, 1])
    with col1:
        render_trail_grid(routes)
    with col2:
        render_weather_query(routes)

    st.markdown("---")
    render_home_planning_chat(username)
