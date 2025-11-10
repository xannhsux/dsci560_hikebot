"""Open-Meteo powered weather helper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

from models import WeatherSnapshot

cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
client = openmeteo_requests.Client(session=retry_session)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _target_as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo:
        return timestamp.astimezone(timezone.utc)
    return timestamp.replace(tzinfo=timezone.utc)


def _closest_index(timestamps: List[datetime], target: datetime) -> int:
    diffs = [abs((ts - target).total_seconds()) for ts in timestamps]
    return diffs.index(min(diffs))


def _prep_hourly_times(hourly) -> List[datetime]:
    rng = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )
    return [ts.to_pydatetime() for ts in rng]


def get_weather_snapshot(latitude: float, longitude: float, target_time: datetime) -> WeatherSnapshot:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["precipitation_probability"],
        "current": ["temperature_2m", "wind_speed_10m", "precipitation", "rain"],
    }
    responses = client.weather_api(WEATHER_URL, params=params)
    response = responses[0]

    current = response.Current()
    temp_c = current.Variables(0).Value()
    precip_amount = current.Variables(2).Value()

    hourly = response.Hourly()
    hourly_probs = hourly.Variables(0).ValuesAsNumpy()
    if len(hourly_probs) == 0:
        precip_probability = 0.0
    else:
        timestamps = _prep_hourly_times(hourly)
        idx = _closest_index(timestamps, _target_as_utc(target_time))
        precip_probability = float(hourly_probs[min(idx, len(hourly_probs) - 1)] / 100)

    lightning_risk = "high" if precip_probability > 0.7 else "moderate" if precip_probability > 0.4 else "low"
    fire_risk = "high" if precip_probability < 0.1 and precip_amount == 0 else "moderate" if precip_probability < 0.3 else "low"
    advisory = (
        f"Current temp {temp_c:.1f}°C, precip chance {precip_probability*100:.0f}%. "
        "Pack layers and check skies near exposed ridgelines."
    )

    return WeatherSnapshot(
        temp_c=round(temp_c, 1),
        precip_probability=round(precip_probability, 2),
        lightning_risk=lightning_risk,
        fire_risk=fire_risk,
        advisory=advisory,
    )
