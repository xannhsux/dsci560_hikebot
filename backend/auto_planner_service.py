# backend/auto_planner_service.py

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

# --- External Libs ---
# 确保安装了: pip install thefuzz python-dateutil openai
from thefuzz import process
from openai import OpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# --- Internal Imports ---
from pg_db import execute
from models import Trail

logger = logging.getLogger(__name__)

# ==========================================
# 1. Mock Data (Fallback for empty DB)
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
    # 允许为空，防止本地模型提取失败时报错
    trail_name_raw: Optional[str] = None
    target_date_str: Optional[str] = None

# ==========================================
# 3. Main Service Class (Ollama Version)
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        
        # 👇 核心修改：连接宿主机的 Ollama
        # 必须在 docker-compose.yml 里配置 extra_hosts: "host.docker.internal:host-gateway"
        self.client = OpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama", # Ollama 不需要真实 Key，但库需要占位符
        )
        # 指定你本地已下载的模型 (llama3, mistral, qwen2 等)
        self.model_name = "llama3" 

    async def run_pipeline(self, chat_id: str, user_message: str):
        """
        主流程: 关键词过滤 -> 意图识别(Ollama) -> DB/Mock匹配 -> 生成公告(Ollama) -> 存库
        """
        # 1. Quick Filter (关键词过滤，省资源)
        triggers = ["go to", "hike", "trail", "plan", "weekend", "saturday", "sunday", "trip", "join", "去", "爬山", "路线", "约"]
        if not any(k in user_message.lower() for k in triggers):
            return

        # 2. Intent Extraction (LLM)
        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 (Ollama) Trip Intent Detected: '{extraction.trail_name_raw}'")

        # 3. DB Grounding (Fuzzy Match)
        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            logger.warning(f"❌ Trail '{extraction.trail_name_raw}' not found in DB or Mock.")
            return

        # 4. Mock Weather (简化演示)
        weather_info = "Sunny, 20°C (Mock Data)"

        # 5. Generate JSON (LLM)
        announcement_json = await self._generate_final_json(trail_record, extraction.target_date_str, weather_info)

        # 6. Save to DB
        self._post_announcement_to_db(chat_id, announcement_json)

    async def _extract_intent(self, message: str) -> ExtractionSchema:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Ollama 比较容易“话痨”，Prompt 需要强调只返回 JSON
        system_prompt = f"""
        You are a JSON extractor. Current Date: {current_date}.
        Check if user is planning a hike.
        Return ONLY a JSON object with keys: "is_planning_trip" (bool), "trail_name_raw" (str or null), "target_date_str" (YYYY-MM-DD or null).
        Do NOT output markdown blocks or explanations.
        Example: {{"is_planning_trip": true, "trail_name_raw": "Mailbox", "target_date_str": "2023-10-10"}}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                # 开启 JSON 模式 (确保 Ollama 版本较新)
                response_format={"type": "json_object"}, 
                temperature=0.0
            )
            content = response.choices[0].message.content
            return ExtractionSchema(**json.loads(content))
        except Exception as e:
            logger.error(f"Ollama Intent Error: {e}")
            # 失败兜底
            return ExtractionSchema(is_planning_trip=False)

    def _fuzzy_match_trail(self, raw_name: str):
        """
        先查真实数据库，如果没有数据，查 Mock 数据。
        """
        # --- 尝试 1: 真实数据库 ---
        try:
            all_trails = self.db.query(Trail).all()
            if all_trails:
                choices = {t.name: t for t in all_trails}
                best_match, score = process.extractOne(raw_name, list(choices.keys()))
                if score > 70:
                    return choices[best_match]
        except Exception:
            pass # DB 出错或为空，跳过

        # --- 尝试 2: Mock Data ---
        mock_choices = {t['name']: t for t in MOCK_TRAILS_DB}
        best_match, score = process.extractOne(raw_name, list(mock_choices.keys()))
        
        if score > 50:
            t_data = mock_choices[best_match]
            # 动态构建对象以模拟 SQLAlchemy Model
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
            # 生成失败时的兜底返回
            return {
                "title": f"Trip to {trail.name}",
                "summary": "Generated by local AI (Ollama).",
                "stats": {"dist": str(trail.length_km), "elev": str(trail.elevation_gain_m)},
                "gear_required": ["Boots"],
                "fun_fact": "AI generation failed, but hiking is fun!"
            }

    def _post_announcement_to_db(self, chat_id: str, content_json: Dict):
        """
        使用 Raw SQL 写入，避免 Session 冲突，并确保前端能看到 'HikeBot' 发的消息。
        """
        content_str = json.dumps(content_json)
        try:
            execute(
                """
                INSERT INTO group_messages (group_id, sender_display, role, content, created_at) 
                VALUES (%(gid)s, 'HikeBot', 'assistant', %(c)s, NOW())
                """,
                {"gid": chat_id, "c": content_str}
            )
            logger.info("✅ Announcement posted to DB.")
        except Exception as e:
            logger.error(f"DB Write failed: {e}")