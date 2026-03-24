from __future__ import annotations

import logging
import math

import requests
import voluptuous as vol

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.event import track_time_interval

from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DOMAIN = "willywindforecast"

CONF_FORECAST_DAYS = "forecast_days"
CONF_POLL_PERIOD_HOURS = "poll_period_hours"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_FORECAST_DAYS, default=7): cv.positive_int,
                vol.Optional(CONF_POLL_PERIOD_HOURS, default=3): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

API_BASE = "https://api.willyweather.com.au/v2"


def _search_location(api_key: str, lat: float, lng: float) -> int:
    url = f"{API_BASE}/{api_key}/search.json"
    payload = {
        "lat": lat,
        "lng": lng,
        "range": 5,
        "units": {"distance": "km"},
    }
    resp = requests.get(
        url,
        headers={
            "Content-Type": "application/json",
            "x-payload": str(payload).replace("'", '"'),
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    location_id = data["location"]["id"]
    _LOGGER.debug(
        "Resolved location: id=%s, name=%s, region=%s, state=%s",
        location_id,
        data["location"]["name"],
        data["location"]["region"],
        data["location"]["state"],
    )
    return location_id


def _fetch_forecast(api_key: str, location_id: int, forecast_days: int) -> dict:
    url = f"{API_BASE}/{api_key}/locations/{location_id}/weather.json"
    payload = {"forecasts": ["wind"], "days": forecast_days}
    resp = requests.get(
        url,
        headers={
            "Content-Type": "application/json",
            "x-payload": str(payload).replace("'", '"'),
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _compute_dominant_direction(entries: list[dict]) -> tuple[float, str]:
    if not entries:
        return (0.0, "N")
    sin_sum = 0.0
    cos_sum = 0.0
    for entry in entries:
        speed = entry["speed"]
        rad = math.radians(entry["direction"])
        sin_sum += speed * math.sin(rad)
        cos_sum += speed * math.cos(rad)
    avg_rad = math.atan2(sin_sum, cos_sum)
    avg_deg = math.degrees(avg_rad) % 360

    directions = [
        (0, "N"), (22.5, "NNE"), (45, "NE"), (67.5, "ENE"),
        (90, "E"), (112.5, "ESE"), (135, "SE"), (157.5, "SSE"),
        (180, "S"), (202.5, "SSW"), (225, "SW"), (247.5, "WSW"),
        (270, "W"), (292.5, "WNW"), (315, "NW"), (337.5, "NNW"),
    ]
    closest = min(directions, key=lambda d: min(abs(d[0] - avg_deg), 360 - abs(d[0] - avg_deg)))
    return (round(avg_deg, 1), closest[1])


def _process_forecast(data: dict) -> list[dict]:
    days = data.get("forecasts", {}).get("wind", {}).get("days", [])
    result = []
    for day in days:
        entries = day.get("entries", [])
        if not entries:
            result.append({
                "speed_max": None,
                "speed_min": None,
                "dominant_direction": None,
                "dominant_direction_text": None,
            })
            continue
        speeds = [e["speed"] for e in entries]
        direction, direction_text = _compute_dominant_direction(entries)
        result.append({
            "speed_max": max(speeds),
            "speed_min": min(speeds),
            "dominant_direction": direction,
            "dominant_direction_text": direction_text,
        })
    return result


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config[DOMAIN]
    api_key = conf[CONF_API_KEY]
    forecast_days = conf[CONF_FORECAST_DAYS]
    poll_period_hours = conf[CONF_POLL_PERIOD_HOURS]

    _LOGGER.info("Setting up %s", DOMAIN)
    _LOGGER.debug("API key found")
    _LOGGER.debug("Forecast days: %s", forecast_days)
    _LOGGER.debug("Poll period hours: %s", poll_period_hours)

    lat = hass.states.get("zone.home").attributes.get("latitude")
    lng = hass.states.get("zone.home").attributes.get("longitude")
    _LOGGER.debug("Home location: lat=%s, lng=%s", lat, lng)

    try:
        location_id = _search_location(api_key, lat, lng)
    except Exception:
        _LOGGER.exception("Failed to resolve location from WillyWeather API")
        return False

    _LOGGER.debug("Location ID: %s", location_id)

    try:
        raw = _fetch_forecast(api_key, location_id, forecast_days)
        forecast = _process_forecast(raw)
    except Exception:
        _LOGGER.exception("Failed to fetch initial forecast from WillyWeather API")
        return False

    hass.data[DOMAIN] = {
        "api_key": api_key,
        "location_id": location_id,
        "forecast_days": forecast_days,
        "forecast": forecast,
    }

    def _update(now=None):
        try:
            raw = _fetch_forecast(api_key, location_id, forecast_days)
            hass.data[DOMAIN]["forecast"] = _process_forecast(raw)
            _LOGGER.debug("Forecast data updated")
        except Exception:
            _LOGGER.exception("Failed to update forecast from WillyWeather API")

    track_time_interval(hass, _update, timedelta(hours=poll_period_hours))

    load_platform(hass, "sensor", DOMAIN, {}, config)

    return True
