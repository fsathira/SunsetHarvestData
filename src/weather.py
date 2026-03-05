"""
Fairfield, CA weather from Open-Meteo Historical API.
Daily temperature and precipitation for stacking with fermentation charts.
"""
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

# Fairfield, CA (Suisun Valley area)
FAIRFIELD_LAT = 38.2494
FAIRFIELD_LON = -122.0398
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def fetch_fairfield_weather(
    start_date: date,
    end_date: date,
    *,
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Fetch daily weather for Fairfield, CA.
    Returns DataFrame with columns: date, temp_max_f, temp_min_f, temp_mean_f, precip_in, day_index.
    """
    params = {
        "latitude": FAIRFIELD_LAT,
        "longitude": FAIRFIELD_LON,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Los_Angeles",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
    }
    r = requests.get(OPEN_METEO_ARCHIVE, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    daily = data.get("daily", {})
    if not daily or not daily.get("time"):
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]),
        "temp_max_f": daily["temperature_2m_max"],
        "temp_min_f": daily["temperature_2m_min"],
        "precip_in": daily["precipitation_sum"],
    })
    df["temp_mean_f"] = (df["temp_max_f"] + df["temp_min_f"]) / 2
    df["day_index"] = range(len(df))
    return df
