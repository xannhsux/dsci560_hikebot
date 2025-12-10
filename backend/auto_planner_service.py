# backend/auto_planner_service.py

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

# --- External Libs ---
# 务必确保安装了: pip install thefuzz python-dateutil
from thefuzz import process
from openai import OpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# --- Internal Imports ---
from pg_db import execute  # 使用 Raw SQL 写入，避免后台任务的 Session 冲突
from models import Trail   # 确保 models.py 里已经有了 Trail 定义

logger = logging.getLogger(__name__)

# ==========================================
# 1. Mock Data (当数据库为空时的救命稻草)
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
    },
    {
        "name": "Lake Serene",
        "location": "Gold Bar, WA",
        "length_km": 13.2,
        "elevation_gain_m": 610,
        "difficulty_rating": 3.5,
        "latitude": 47.7828,
        "longitude": -121.5644,
        "features": "alpine_lake,waterfall,stairs"
    }
]

# ==========================================
# 2. Pydantic Schema (LLM 输出结构)
# ==========================================
class ExtractionSchema(BaseModel):
    is_planning_trip: bool = Field(description="True only if users are actively proposing a plan, not just asking info.")
    trail_name_raw: Optional[str] = None
    target_date_str: Optional[str] = Field(description="YYYY-MM-DD format")

# ==========================================
# 3. Main Service Class
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        # 确保环境变量里有 OPENAI_API_KEY
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def run_pipeline(self, chat_id: str, user_message: str):
        """
        主流程: 意图识别 -> 数据锚定(Grounding) -> 模拟天气 -> 生成人设公告 -> 存入数据库
        """
        # 1. 快速关键词过滤 (省钱策略)
        triggers = ["go to", "hike", "trail", "plan", "weekend", "saturday", "sunday", "trip", "join", "去", "爬山", "路线", "约"]
        if not any(k in user_message.lower() for k in triggers):
            return

        # 2. LLM 意图提取
        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 Trip Intent Detected: '{extraction.trail_name_raw}' on '{extraction.target_date_str}'")

        # 3. 数据库模糊匹配 (含 Mock 兜底)
        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            logger.warning(f"❌ Trail '{extraction.trail_name_raw}' not found in DB or Mock data.")
            return

        # 4. 获取天气 (这里为了演示效果，使用基于季节的模拟数据，除非你有真实 API)
        # 真实项目请调用: weather_info = await get_weather_forecast(...)
        hike_date_obj = datetime.strptime(extraction.target_date_str, "%Y-%m-%d") if extraction.target_date_str else datetime.now()
        month = hike_date_obj.month
        if month in [11, 12, 1, 2, 3]:
            weather_info = "Cold, 2°C, Chance of Snow/Rain"
        elif month in [6, 7, 8, 9]:
            weather_info = "Sunny, 22°C, Clear Skies"
        else:
            weather_info = "Overcast, 12°C, Light Rain likely"

        # 5. 生成专家风格公告 (Expert Persona Generation)
        announcement_json = await self._generate_final_json(trail_record, extraction.target_date_str, weather_info)

        # 6. 存入 DB (让前端可见)
        self._post_announcement_to_db(chat_id, announcement_json)

    async def _extract_intent(self, message: str) -> ExtractionSchema:
        """
        分辨 'Is it raining?' (咨询) 和 'Let's go hiking' (计划)
        """
        current_date = datetime.now().strftime("%Y-%m-%d (%A)")
        
        system_prompt = f"""
        Current Date: {current_date}.
        
        Analyze the user's message. Determine if they are PROPOSING or CONFIRMING a trip.
        
        Distinction:
        - "What is the weather at Rainier?" -> is_planning_trip: FALSE (Just asking info)
        - "Let's do Mailbox this Saturday" -> is_planning_trip: TRUE
        - "I'm down for Rattlesnake" -> is_planning_trip: TRUE
        - "How about hiking Si?" -> is_planning_trip: TRUE
        
        If TRUE, extract:
        - 'trail_name_raw': The hiking location mentioned.
        - 'target_date_str': Calculate YYYY-MM-DD based on Current Date (default to upcoming Saturday if vague 'weekend').
        
        Return JSON matching the schema.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125", # 使用较快模型
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            data = json.loads(response.choices[0].message.content)
            return ExtractionSchema(**data)
        except Exception as e:
            logger.error(f"Intent extraction error: {e}")
            return ExtractionSchema(is_planning_trip=False)

    def _fuzzy_match_trail(self, raw_name: str):
        """
        先查 DB，查不到查 Mock，确保演示一定成功。
        """
        # --- 尝试 1: 真实数据库 ---
        try:
            all_trails = self.db.query(Trail).all()
            if all_trails:
                choices = {t.name: t for t in all_trails}
                # extractOne 返回 (match_key, score)
                best_match, score = process.extractOne(raw_name, list(choices.keys()))
                if score > 70:
                    logger.info(f"✅ DB Match: {best_match} ({score})")
                    return choices[best_match]
        except Exception as e:
            logger.warning(f"DB Query warning (expected if DB empty): {e}")

        # --- 尝试 2: Mock Data (Fallback) ---
        logger.info("⚠️ Using Mock Data for Trail Matching...")
        mock_choices = {t['name']: t for t in MOCK_TRAILS_DB}
        
        best_match, score = process.extractOne(raw_name, list(mock_choices.keys()))
        
        if score > 50: # 稍微降低 Mock 数据的匹配门槛
            logger.info(f"✅ Mock Match: {best_match} ({score})")
            t_data = mock_choices[best_match]
            
            # 动态构建对象，使其表现得像 SQLAlchemy Model
            class MockTrailObj:
                pass
            obj = MockTrailObj()
            for k, v in t_data.items():
                setattr(obj, k, v)
            return obj
            
        return None

    async def _generate_final_json(self, trail, date_str, weather) -> Dict:
        """
        包含 Tone Rules, Safety Checks, 和 Fun Fact 的高级 Prompt
        """
        system_prompt = """
        You are HikeBot, a veteran outdoor guide with 20 years of experience in the PNW.
        
        TASK: Generate a hiking trip announcement JSON.
        
        TONE RULES:
        - If difficulty > 4/5 OR weather includes "Rain"/"Snow": Tone is SERIOUS, COMMANDING, SAFETY-FIRST.
        - If difficulty < 3/5 AND weather is "Sunny": Tone is PLAYFUL, EXCITED, CASUAL (use emojis).
        
        CONTENT RULES:
        1. 'summary': 2 sentences. Don't just list facts. Sell the experience!
        2. 'gear_required': Be specific based on weather (e.g., "Microspikes" if snow, "Sunscreen" if sunny).
        3. 'fun_fact': Include one hidden gem/history/geology fact about this specific trail.
        4. 'safety_analysis': (Internal thought) If elevation > 1000m, warn about "Endurance". If rain, warn about "Slippery roots".
        
        OUTPUT FORMAT (JSON ONLY):
        {
            "title": "Catchy headline with emojis",
            "summary": "Engaging description...",
            "stats": {"dist": "X km", "elev": "Y m"},
            "weather_warning": "Brief weather/safety note",
            "gear_required": ["item1", "item2", "item3"],
            "fun_fact": "Did you know? ..."
        }
        """
        
        user_content = f"""
        FACTS:
        - Trail Name: {trail.name}
        - Difficulty: {trail.difficulty_rating}/5
        - Length: {trail.length_km} km
        - Elevation Gain: {trail.elevation_gain_m} m
        - Features: {trail.features}
        - Date: {date_str}
        - Weather Context: {weather}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo", # 为了生成质量，建议用 GPT-4
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Generation error: {e}")
            # 失败时的兜底返回
            return {
                "title": f"Hike to {trail.name}",
                "summary": "Let's go hiking!",
                "stats": {"dist": f"{trail.length_km}km", "elev": f"{trail.elevation_gain_m}m"},
                "weather_warning": "Check forecast.",
                "gear_required": ["Water", "Boots"],
                "fun_fact": "Hiking is good for you!"
            }

    def _post_announcement_to_db(self, chat_id: str, content_json: Dict):
        """
        Writes directly to Postgres using Raw SQL.
        """
        content_str = json.dumps(content_json)
        try:
            # sender_display='HikeBot', role='assistant' 对应前端的渲染逻辑
            execute(
                """
                INSERT INTO group_messages (group_id, user_id, sender_display, role, content, created_at) 
                VALUES (%(gid)s, NULL, 'HikeBot', 'assistant', %(c)s, NOW())
                """,
                {"gid": chat_id, "c": content_str}
            )
            logger.info("✅ Announcement successfully posted to DB.")
        except Exception as e:
            logger.error(f"Failed to post announcement to DB: {e}")