"""Weather helper that wraps NOAAWeatherCollector for the hiking chatbot."""

from __future__ import annotations

from typing import Dict, Any, Optional

from models import WeatherSnapshot
from noaa_weather_collector import NOAAWeatherCollector

_collector = NOAAWeatherCollector()


def get_weather_snapshot(lat: float, lon: float, name: str) -> Optional[Dict[str, Any]]:
    """
    Returns a single NOAA weather record dict for a given hiking location.
    The raw dict includes clothing recommendations, hiking conditions, etc.
    """
    try:
        record = _collector.get_location_weather(lat, lon, name)
        return record
    except Exception:
        return None


def summarize_weather(record: Dict[str, Any]) -> WeatherSnapshot:
    """
    Convert the raw NOAA record into a compact WeatherSnapshot schema.
    """
    temp_f = record.get("temperature")
    temp_c: float
    if temp_f is None:
        temp_c = 20.0
    elif record.get("temperature_unit") == "F":
        temp_c = (temp_f - 32) * 5.0 / 9.0
    else:
        temp_c = float(temp_f)

    precip_value = record.get("precipitation_chance", "0%")
    precip_field = str(precip_value).replace("%", "")
    try:
        precip_probability = float(precip_field) / 100.0
    except Exception:
        precip_probability = 0.0

    text = record.get("detailed_forecast", "") or record.get("short_forecast", "")

    if precip_probability > 0.7:
        lightning_risk = "high"
    elif precip_probability > 0.4:
        lightning_risk = "moderate"
    else:
        lightning_risk = "low"

    # very naive fire risk heuristic based on precipitation
    if precip_probability < 0.1:
        fire_risk = "high"
    elif precip_probability < 0.3:
        fire_risk = "moderate"
    else:
        fire_risk = "low"

    summary = (
        f"Temperature around {temp_c:.1f}°C, "
        f"precipitation chance {precip_probability * 100:.0f}%. "
        f"Conditions: {record.get('short_forecast', 'Unknown')}."
    )

    # Map into our compact WeatherSnapshot schema expected by the API
    return WeatherSnapshot(
        summary=summary,
        temp_c=round(temp_c, 1),
        precip_prob=round(precip_probability, 2),
        lightning_risk=lightning_risk,  # type: ignore[arg-type]
        fire_risk=fire_risk,            # type: ignore[arg-type]
    )
