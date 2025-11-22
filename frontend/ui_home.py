# ui_home.py
from __future__ import annotations
from typing import Any, Dict, List

from datetime import datetime
import streamlit as st

from api import request_weather, fetch_routes, send_planning_message
from ui_common import render_message_bubble


def render_trail_list(routes: List[Dict[str, Any]]) -> None:
    """Trail explorer (single selection, similar to weather query)."""
    st.subheader("Browse Trails")

    if not routes:
        st.caption("No routes loaded yet.")
        return

    # Build label → route mapping
    label_to_route = {
        f"{r['name']} — {r.get('location', '')}": r
        for r in routes
    }

    labels = list(label_to_route.keys())

    # Let user select exactly one trail
    selected_label = st.selectbox(
        "Select a trail to view details",
        labels,
        key="trail_explorer_select",
    )
    selected_route = label_to_route[selected_label]

    # Display only the selected trail's details
    st.markdown(f"**{selected_route['name']}** — {selected_route.get('location', '')}")
    st.caption(
        f"{selected_route['distance_km']} km · {selected_route['elevation_gain_m']} m gain · "
        f"{selected_route['difficulty'].title()} · ~{selected_route['drive_time_min']} min drive"
    )

    if summary := selected_route.get("summary"):
        st.write(summary)



def render_weather_query(routes: List[Dict[str, Any]]) -> None:
    st.subheader("Weather Snapshot")

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
    st.subheader("AI Planning Chat")

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
    render_trail_list(routes)
    st.markdown("---")
    render_weather_query(routes)
    st.markdown("---")
    render_home_planning_chat(username)
