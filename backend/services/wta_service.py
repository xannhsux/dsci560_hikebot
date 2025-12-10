# backend/services/wta_service.py

import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_wta_trail(trail_name: str):
    """
    1. 在 WTA 上搜索 Trail 名字，获取 Trail 的详情页 URL
    """
    search_url = "https://www.wta.org/@@search"
    params = {
        "SearchableText": trail_name,
        "portal_type": "hike_region" # 限制搜索类型为 Hiking Guide
    }
    
    try:
        # 伪装成浏览器，防止被反爬
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        resp = requests.get(search_url, params=params, headers=headers, timeout=5)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.content, "lxml")
        
        # 找到第一个搜索结果
        result = soup.find("a", {"class": "result-title"})
        if result:
            return result['href'] # 返回 Trail 的详情页链接
            
    except Exception as e:
        logger.error(f"WTA Search failed: {e}")
        return None

def get_recent_trip_reports(trail_url: str, days: int = 7):
    """
    2. 进入详情页，抓取最近 X 天的 Trip Reports 关键词
    """
    if not trail_url:
        return []

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Trip Reports 通常在详情页面的下方，或者有单独的链接，WTA 的结构是 /hike-name/@@related_tripreports_listing
        # 但简单起见，我们直接访问 Trail 主页，WTA 主页通常会显示最新的几个 Report
        resp = requests.get(trail_url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, "lxml")
        
        reports = []
        
        # 定位 Trip Reports 区域 (WTA 网页结构可能会变，这是基于当前结构的写法)
        # 查找 class 为 'trip-reports' 的区域
        report_items = soup.find_all("div", class_="trip-report-item", limit=5)
        
        for item in report_items:
            # 获取日期
            date_div = item.find("div", class_="elapsed-time")
            if not date_div: continue
            date_str = date_div.get_text(strip=True) # e.g. "Jun 20, 2024"
            
            # 简单的提取标题和内容摘要
            title = item.find("h3").get_text(strip=True) if item.find("h3") else ""
            content_snippet = item.find("div", class_="show-with-full").get_text(strip=True) if item.find("div", class_="show-with-full") else ""
            
            # 组合成一段文本
            full_text = f"{title}. {content_snippet}"
            reports.append(full_text)
            
        return reports

    except Exception as e:
        logger.error(f"WTA Scraping failed: {e}")
        return []

def check_hazards(reports: list):
    """
    3. 简单的关键词匹配，快速判断有没有危险
    """
    combined_text = " ".join(reports).lower()
    
    hazards = []
    if any(w in combined_text for w in ["snow", "ice", "microspikes", "spikes", "crampons"]):
        hazards.append("Snow/Ice detected (Spikes recommended)")
    if any(w in combined_text for w in ["mud", "muddy", "slippery"]):
        hazards.append("Muddy trail (Gaiters/Boots recommended)")
    if any(w in combined_text for w in ["bear", "cougar", "goat"]):
        hazards.append("Wildlife activity reported")
    if any(w in combined_text for w in ["bug", "mosquito", "flies"]):
        hazards.append("Bugs reported (Bug spray needed)")
        
    return hazards