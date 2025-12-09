# backend/ai_service.py (请完全覆盖)
import random
import re
from typing import List, Dict, Any
from pg_db import fetch_one_returning, fetch_all, fetch_one

# Mock Database of Trails
MOCK_TRAILS = [
    {"name": "Lost Lake Loop", "dist": "5.2km", "diff": "Easy", "tags": ["lake", "easy", "relax"]},
    {"name": "Bald Mountain Ridge", "dist": "12km", "diff": "Hard", "tags": ["view", "hard", "steep"]},
    {"name": "Whispering Pines", "dist": "8.5km", "diff": "Moderate", "tags": ["forest", "moderate"]},
    {"name": "Coastal Trail", "dist": "10km", "diff": "Moderate", "tags": ["ocean", "moderate", "windy"]},
    {"name": "Summit Scramble", "dist": "15km", "diff": "Hard", "tags": ["summit", "hard", "rocky"]},
]

# 决策关键词：当 AI 听到这些词，它就会认为大家决定好了
DECISION_KEYWORDS = [
    "let's go", "finalized", "confirmed", "it's a plan", "locked in", 
    "deal", "sounds good to everyone", "see you there", "booked", "settled"
]

def post_system_message(group_id: str, content: str, sender_name: str = "Trail Mind"):
    """Insert a message into the group chat as an AI agent."""
    fetch_one_returning(
        """
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
        VALUES (%(gid)s, NULL, %(sender)s, 'assistant', %(content)s)
        RETURNING id
        """,
        {
            "gid": group_id,
            "sender": sender_name,
            "content": content
        }
    )

def _get_recent_context(group_id: str, limit: int = 20) -> str:
    rows = fetch_all(
        "SELECT content FROM group_messages WHERE group_id = %(gid)s ORDER BY created_at DESC LIMIT %(lim)s",
        {"gid": group_id, "lim": limit}
    )
    texts = [r["content"] for r in reversed(rows)]
    return " ".join(texts).lower()

def generate_route_suggestions(group_id: str):
    """Context-Aware Recommendation."""
    context = _get_recent_context(group_id)
    wants_hard = any(w in context for w in ["hard", "challenging", "steep", "workout"])
    wants_easy = any(w in context for w in ["easy", "chill", "relax", "beginner", "flat"])
    wants_water = any(w in context for w in ["water", "lake", "river", "ocean"])

    candidates = []
    if wants_hard:
        candidates = [t for t in MOCK_TRAILS if t["diff"] == "Hard"]
        intro = "💪 Based on your chat, you guys want a challenge! Check these out:"
    elif wants_easy:
        candidates = [t for t in MOCK_TRAILS if t["diff"] == "Easy"]
        intro = "🍃 Sounds like a relaxed vibe. Here are some chill trails:"
    else:
        candidates = MOCK_TRAILS
        intro = "Here are some top-rated trails for the group:"

    if wants_water:
        water_trails = [t for t in candidates if any(x in t["tags"] for x in ["lake", "ocean"])]
        if water_trails: candidates = water_trails

    selected = random.sample(candidates, min(len(candidates), 2))
    msg = f"{intro}\n\n"
    for r in selected:
        msg += f"🌲 **{r['name']}** ({r['diff']})\n"
        msg += f"   - Distance: {r['dist']}\n"
        msg += f"   - *Vibe:* {', '.join(r['tags'])}\n\n"
    msg += "Discuss and let me know when you decide!"
    post_system_message(group_id, msg)
    return {"status": "ok"}

def generate_trip_plan(group_id: str):
    """Auto Announcement Generator."""
    context = _get_recent_context(group_id, limit=50)
    
    # 1. Extract Info
    location = "Undecided Location"
    time = "TBD"
    carpool = "Please discuss carpool"
    
    for trail in MOCK_TRAILS:
        if trail["name"].lower() in context:
            location = trail["name"]
            break
    
    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', context)
    if time_match: time = time_match.group(1)
    
    if "drive" in context or "car" in context or "seat" in context:
        carpool = "Carpooling mentioned. Drivers please confirm."

    # 2. Contextual Info
    weather_info = "☀️ Partly Cloudy, 18°C. Perfect hiking weather."
    if "rain" in context: weather_info = "🌧️ Chance of rain. Bring waterproofs!"
        
    gear_list = ["🥾 Hiking boots", "💧 2L Water", "🧥 Layers", "🔋 Power bank", "🍫 Snacks"]
    safety_notes = "Stay on marked trails. No cell service in canyon areas."
    
    # 3. Post Announcement
    announcement = f"""📢 **OFFICIAL TRIP PLAN**

Since you've finalized the plan, here is the summary:

📍 **Destination:** {location}
⏰ **Meetup Time:** {time}
🚗 **Carpool:** {carpool}

---
🎒 **Gear List:**
{chr(10).join(['- ' + g for g in gear_list])}

🌤️ **Weather:**
{weather_info}

⚠️ **Safety Instructions:**
{safety_notes}

*Have a safe hike!*
"""
    post_system_message(group_id, announcement, sender_name="HikeBot")
    return {"status": "ok"}

# 🟢 NEW: Active Listener Hook
def process_message_hook(group_id: str, user_message: str):
    """
    Called every time a user sends a message.
    Checks if the AI should proactively intervene.
    """
    msg_lower = user_message.lower()
    
    # 1. Check for Decision/Consensus
    # Logic: If user says "confirmed" or "let's go", trigger plan.
    if any(keyword in msg_lower for keyword in DECISION_KEYWORDS):
        # Prevention: Check if AI just posted recently to avoid loops (omitted for simple demo)
        generate_trip_plan(group_id)
        return

    # 2. Check for Help Request (Optional)
    if "@hikebot" in msg_lower and ("recommend" in msg_lower or "where" in msg_lower):
        generate_route_suggestions(group_id)
        return