# backend/auto_planner_service.py

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

from thefuzz import process
from openai import AsyncOpenAI # 👈 改为异步客户端
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from pg_db import execute
from models import Trail

logger = logging.getLogger(__name__)

# ... (MOCK_TRAILS_DB 和 ExtractionSchema 保持不变，省略以节省空间) ...
# 请保留你之前的 Mock 数据和 Schema 定义

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
# 3. Main Service Class (Async Ollama Version)
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        
        # 👇 改用 AsyncOpenAI，这样等待 AI 时不会卡死整个后台
        self.client = AsyncOpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama",
        )
        self.model_name = "llama3.2" 

    async def run_pipeline(self, chat_id: str, user_message: str):
        triggers = ["go to", "hike", "trail", "plan", "weekend", "saturday", "sunday", "trip", "join", "去", "爬山", "路线", "约"]
        if not any(k in user_message.lower() for k in triggers):
            return

        # 这里的 await 现在是真的异步等待，不会阻塞
        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 (Async Ollama) Intent: '{extraction.trail_name_raw}'")

        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            return

        weather_info = "Sunny, 20°C (Mock)"

        announcement_json = await self._generate_final_json(trail_record, extraction.target_date_str, weather_info)

        self._post_announcement_to_db(chat_id, announcement_json)

    async def _extract_intent(self, message: str) -> ExtractionSchema:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
        You are a JSON extractor. Current Date: {current_date}.
        Check if user is planning a hike.
        Return ONLY a JSON object with keys: "is_planning_trip", "trail_name_raw", "target_date_str".
        Example: {{"is_planning_trip": true, "trail_name_raw": "Mailbox", "target_date_str": "2023-10-10"}}
        """

        try:
            # 👇 关键修改：加上 await
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

    async def _generate_final_json(self, trail, date_str, weather) -> Dict:
        system_prompt = """
        You are HikeBot. Generate a JSON trip announcement.
        Return ONLY JSON. No markdown.
        Format: {"title": "...", "summary": "...", "stats": {...}, "weather_warning": "...", "gear_required": [...], "fun_fact": "..."}
        """
        user_content = f"Trail: {trail.name}, Length: {trail.length_km}km. Date: {date_str}. Weather: {weather}"

        try:
            # 👇 关键修改：加上 await
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Gen Error: {e}")
            return {"title": "Error generating plan"}

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
            
# backend/services/auto_planner_service.py

# 引入刚才写的服务
from services.wta_service import search_wta_trail, get_recent_trip_reports, check_hazards
import logging

logger = logging.getLogger(__name__)

async def generate_trip_plan(trail_name: str, date_str: str):
    """
    生成包含实时路况的行程单
    """
    logger.info(f"🔎 Checking WTA reports for {trail_name}...")
    
    # 1. 获取 WTA 数据 (这是 RAG 的 Retrieval 部分)
    wta_context = ""
    wta_hazards = []
    
    try:
        url = search_wta_trail(trail_name)
        if url:
            reports = get_recent_trip_reports(url)
            wta_hazards = check_hazards(reports)
            
            # 把最近的评论摘要拼接起来，喂给 LLM
            if reports:
                wta_context = "Recent User Reports from WTA:\n" + "\n- ".join(reports[:3])
            else:
                wta_context = "No recent trip reports found on WTA."
        else:
            wta_context = "Could not find trail on WTA."
            
    except Exception as e:
        logger.error(f"WTA lookup failed: {e}")
        wta_context = "WTA data unavailable."

    # 2. 构建 Prompt (把 WTA 数据塞进去)
    system_prompt = f"""
    You are an expert hiking guide for the Pacific Northwest.
    Plan a trip to: {trail_name} on {date_str}.
    
    [REAL-TIME CONDITIONS DATA]
    {wta_context}
    
    [CRITICAL INSTRUCTION]
    - If the reports mention SNOW, ICE, or SLIPPERY conditions, you MUST include 'Microspikes' or 'Traction devices' in the gear_required list.
    - If reports mention BUGS, include 'Bug spray'.
    - If reports mention BEARS, include 'Bear spray'.
    
    Return ONLY a JSON object with this structure:
    {{
      "title": "Trip to {trail_name}",
      "summary": "...",
      "stats": {{"dist": "...", "elev": "..."}},
      "weather_warning": "Based on reports: {', '.join(wta_hazards) if wta_hazards else 'Check local forecast'}",
      "gear_required": ["Item 1", "Item 2", ...],
      "fun_fact": "..."
    }}
    """
    
    # 3. 调用 LLM (这里用你现有的 call_ollama 或类似函数)
    # response = await call_ollama(system_prompt)
    # return response
    
    # (为了演示，这里直接返回伪代码，你需要把它接入你的 LLM 调用逻辑)
    logger.info(f"Generated Context for LLM: {wta_context[:100]}...")
    return system_prompt