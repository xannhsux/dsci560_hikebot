# backend/auto_planner_service.py

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from thefuzz import process
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from pg_db import execute
from models import Trail

# --- 引入 WTA 爬虫服务 ---
# 注意：这些函数在 services 文件夹里是同步的，我们在下面进行调用
from services.wta_service import search_wta_trail, get_recent_trip_reports, check_hazards

logger = logging.getLogger(__name__)

# ==========================================
# 1. Mock Data & Schema (保持不变)
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

class ExtractionSchema(BaseModel):
    is_planning_trip: bool = Field(description="True only if users are actively proposing a plan.")
    trail_name_raw: Optional[str] = None
    target_date_str: Optional[str] = None

# ==========================================
# 3. Main Service Class (Async Ollama Version)
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        
        self.client = AsyncOpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama",
        )
        self.model_name = "llama3.2" 

    async def run_pipeline(self, chat_id: str, user_message: str):
        triggers = ["go to", "hike", "trail", "plan", "weekend", "saturday", "sunday", "trip", "join", "去", "爬山", "路线", "约"]
        if not any(k in user_message.lower() for k in triggers):
            return

        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 (Async Ollama) Intent: '{extraction.trail_name_raw}'")

        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            return

        # ---------------------------------------------
        # 🔥🔥🔥 WTA 爬虫集成 (WTA INTEGRATION) 🔥🔥🔥
        # ---------------------------------------------
        logger.info(f"🔎 Checking WTA reports for {trail_record.name}...")
        wta_context = ""
        wta_hazards = []
        
        try:
            # 爬虫函数必须在这里被调用
            url = search_wta_trail(trail_record.name)
            if url:
                reports = get_recent_trip_reports(url)
                wta_hazards = check_hazards(reports)
                
                if reports:
                    wta_context = "Recent User Reports from WTA:\n- " + "\n- ".join(reports[:3])
                else:
                    wta_context = "No recent trip reports found on WTA."
            else:
                wta_context = "Could not find trail on WTA."
                
        except Exception as e:
            logger.error(f"WTA lookup failed: {e}")
            wta_context = f"WTA data failed to load: {e}"
        # ---------------------------------------------

        weather_info = "Sunny, 20°C (Mock)" # 保持 Mock Weather，直到你集成真正的 API

        announcement_json = await self._generate_final_json(
            trail_record, 
            extraction.target_date_str, 
            weather_info,
            wta_context, # 传入 WTA 结果
            wta_hazards # 传入 Hazards
        )

        self._post_announcement_to_db(chat_id, announcement_json)
        
    # --- Intent Extraction (保持不变) ---
    async def _extract_intent(self, message: str) -> ExtractionSchema:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
        You are a JSON extractor. Current Date: {current_date}.
        Check if user is planning a hike.
        Return ONLY a JSON object with keys: "is_planning_trip", "trail_name_raw", "target_date_str".
        Example: {{"is_planning_trip": true, "trail_name_raw": "Mailbox", "target_date_str": "2023-10-10"}}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                response_format={"type": "json_object"}, 
                temperature=0.0
            )
            content = response.choices[0].message.content
            return ExtractionSchema(**json.loads(content))
        except Exception as e:
            logger.error(f"Intent Error: {e}")
            return ExtractionSchema(is_planning_trip=False)

    # --- Fuzzy Match (保持不变) ---
    def _fuzzy_match_trail(self, raw_name: str):
        # ... (此处代码不变，省略) ...
        try:
            all_trails = self.db.query(Trail).all()
            if all_trails:
                choices = {t.name: t for t in all_trails}
                best_match, score = process.extractOne(raw_name, list(choices.keys()))
                if score > 70: return choices[best_match]
        except: pass
        
        mock_choices = {t['name']: t for t in MOCK_TRAILS_DB}
        best_match, score = process.extractOne(raw_name, list(mock_choices.keys()))
        if score > 50:
            t_data = mock_choices[best_match]
            class MockTrailObj: pass
            obj = MockTrailObj()
            for k, v in t_data.items(): setattr(obj, k, v)
            return obj
        return None

    # --- JSON Generation (WTA PROMPT INJECTION) ---
    async def _generate_final_json(self, trail, date_str, weather, wta_context: str, wta_hazards: List[str]) -> Dict:
        # 优化 Prompt，将 WTA 数据注入
        system_prompt = f"""
        You are an expert hiking guide for the Pacific Northwest. Generate a detailed JSON trip announcement.
        
        [INPUT DATA]
        Trail: {trail.name} | Length: {trail.length_km}km | Date: {date_str}
        Mock Weather: {weather}
        
        [REAL-TIME CONDITIONS DATA]
        {wta_context}
        
        [CRITICAL INSTRUCTION]
        - Based on the "REAL-TIME CONDITIONS DATA", you MUST include all necessary safety gear.
        - If reports mention SNOW, ICE, or SLIPPERY conditions, INCLUDE 'Microspikes' or 'Traction devices' in gear_required.
        - If reports mention BUGS, INCLUDE 'Bug spray'.
        
        Return ONLY a JSON object with this format:
        {{"title": "...", "summary": "...", "stats": {{"dist": "...", "elev": "..."}}, "weather_warning": "{', '.join(wta_hazards) if wta_hazards else 'Check local forecast'}", "gear_required": ["Item 1", "Item 2", ...], "fun_fact": "..."}}
        """

        user_content = f"Generate the full plan for the {trail.name} hike."

        try:
            logger.info(f"Generated LLM System Prompt (WTA injected).")
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Gen Error: {e}")
            return {"title": "Error generating plan", "summary": f"AI failed: {e}", "stats": {"dist": "N/A", "elev": "N/A"}}

    # --- DB Post (保持不变) ---
    def _post_announcement_to_db(self, chat_id: str, content_json: Dict):
        content_str = json.dumps(content_json)
        try:
            execute(
                "INSERT INTO group_messages (group_id, sender_display, role, content, created_at) VALUES (%(gid)s, 'HikeBot', 'assistant', %(c)s, NOW())",
                {"gid": chat_id, "c": content_str}
            )
            logger.info("✅ Posted.")
        except Exception as e:
            logger.error(f"DB Write failed: {e}")