# backend/auto_planner_service.py

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

# --- External Libs ---
from thefuzz import process
from openai import OpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# --- Internal Imports ---
from pg_db import execute
from models import Trail

logger = logging.getLogger(__name__)

# ==========================================
# 1. Mock Data (Fallback)
# ==========================================
MOCK_TRAILS_DB = [
    {
        "name": "Mailbox Peak",
        "location": "North Bend, WA",
        "length_km": 15.1,
        "elevation_gain_m": 1219,
        "difficulty_rating": 5.0,
        "latitude": 47.4665,
        "longitude": -121.6749,
        "features": "steep,mailbox_at_top,views"
    },
    {
        "name": "Rattlesnake Ledge",
        "location": "North Bend, WA",
        "length_km": 6.4,
        "elevation_gain_m": 353,
        "difficulty_rating": 2.5,
        "latitude": 47.4326,
        "longitude": -121.7679,
        "features": "lake_view,crowded,easy"
    },
    {
        "name": "Mount Rainier (Skyline Trail)",
        "location": "Paradise, WA",
        "length_km": 9.0,
        "elevation_gain_m": 518,
        "difficulty_rating": 4.0,
        "latitude": 46.7861,
        "longitude": -121.7350,
        "features": "glacier,mountain,wildflowers"
    },
    {
        "name": "Mount Si",
        "location": "North Bend, WA",
        "length_km": 12.0,
        "elevation_gain_m": 960,
        "difficulty_rating": 4.5,
        "latitude": 47.4881,
        "longitude": -121.7225,
        "features": "classic,forest,rocky"
    }
]

# ==========================================
# 2. Pydantic Schema
# ==========================================
class ExtractionSchema(BaseModel):
    is_planning_trip: bool = Field(description="True only if users are actively proposing a plan.")
    trail_name_raw: Optional[str] = None
    target_date_str: Optional[str] = None

# ==========================================
# 3. Main Service Class (Ollama Version)
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        
        # 👇 关键修改：连接本地 Ollama
        # host.docker.internal 允许 Docker 容器访问你宿主机的 localhost
        self.client = OpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama", # 随便填
        )
        # 指定使用本地模型
        self.model_name = "llama3" 

    async def run_pipeline(self, chat_id: str, user_message: str):
        # 1. Quick Filter
        triggers = ["go to", "hike", "trail", "plan", "weekend", "saturday", "sunday", "trip", "join", "去", "爬山", "路线", "约"]
        if not any(k in user_message.lower() for k in triggers):
            return

        # 2. Intent Extraction
        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 (Ollama) Trip Intent Detected: '{extraction.trail_name_raw}'")

        # 3. DB Grounding
        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            return

        # 4. Mock Weather
        weather_info = "Sunny, 20°C (Mock)"

        # 5. Generate JSON
        announcement_json = await self._generate_final_json(trail_record, extraction.target_date_str, weather_info)

        # 6. Save to DB
        self._post_announcement_to_db(chat_id, announcement_json)

    async def _extract_intent(self, message: str) -> ExtractionSchema:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Ollama Llama3 对 JSON 格式要求比较严格，Prompt 要简单直接
        system_prompt = f"""
        You are a JSON extractor. Current Date: {current_date}.
        Check if user is planning a hike.
        Return ONLY a JSON object with keys: "is_planning_trip" (bool), "trail_name_raw" (str or null), "target_date_str" (YYYY-MM-DD or null).
        Example: {{"is_planning_trip": true, "trail_name_raw": "Mailbox", "target_date_str": "2023-10-10"}}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                # 开启 JSON 模式 (Ollama 支持)
                response_format={"type": "json_object"}, 
                temperature=0.0
            )
            content = response.choices[0].message.content
            return ExtractionSchema(**json.loads(content))
        except Exception as e:
            logger.error(f"Ollama Intent Error: {e}")
            return ExtractionSchema(is_planning_trip=False)

    def _fuzzy_match_trail(self, raw_name: str):
        # ... (和之前一样，省略重复代码，保持原样) ...
        # --- 尝试 1: 真实数据库 ---
        try:
            all_trails = self.db.query(Trail).all()
            if all_trails:
                choices = {t.name: t for t in all_trails}
                best_match, score = process.extractOne(raw_name, list(choices.keys()))
                if score > 70:
                    return choices[best_match]
        except Exception:
            pass

        # --- 尝试 2: Mock Data ---
        mock_choices = {t['name']: t for t in MOCK_TRAILS_DB}
        best_match, score = process.extractOne(raw_name, list(mock_choices.keys()))
        if score > 50:
            t_data = mock_choices[best_match]
            class MockTrailObj: pass
            obj = MockTrailObj()
            for k, v in t_data.items(): setattr(obj, k, v)
            return obj
        return None

    async def _generate_final_json(self, trail, date_str, weather) -> Dict:
        system_prompt = """
        You are HikeBot. Generate a JSON trip announcement.
        Return ONLY JSON. No markdown code blocks.
        Format:
        {
            "title": "Short title with emoji",
            "summary": "2 sentences description",
            "stats": {"dist": "X km", "elev": "Y m"},
            "weather_warning": "Brief note",
            "gear_required": ["item1", "item2"],
            "fun_fact": "A short fact"
        }
        """
        
        user_content = f"Trail: {trail.name}, Length: {trail.length_km}km, Elev: {trail.elevation_gain_m}m. Date: {date_str}. Weather: {weather}"

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Ollama Gen Error: {e}")
            # Fallback
            return {
                "title": f"Trip to {trail.name}",
                "summary": "Generated by local AI (Ollama).",
                "stats": {"dist": str(trail.length_km), "elev": str(trail.elevation_gain_m)},
                "gear_required": ["Boots"]
            }

    def _post_announcement_to_db(self, chat_id: str, content_json: Dict):
        # ... (保持原样) ...
        content_str = json.dumps(content_json)
        try:
            execute(
                "INSERT INTO group_messages (group_id, sender_display, role, content, created_at) VALUES (%(gid)s, 'HikeBot', 'assistant', %(c)s, NOW())",
                {"gid": chat_id, "c": content_str}
            )
            logger.info("✅ Announcement posted.")
        except Exception as e:
            logger.error(f"DB Write failed: {e}")