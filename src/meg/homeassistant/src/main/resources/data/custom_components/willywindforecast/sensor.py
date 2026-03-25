from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if discovery_info is None:
        return

    forecast_days = hass.data[DOMAIN]["forecast_days"]
    entities = []
    for day_index in range(forecast_days):
        entities.append(WillyWindForecastSensor(day_index, "speed_max", "km/h"))
        entities.append(WillyWindForecastSensor(day_index, "speed_min", "km/h"))
        entities.append(WillyWindForecastSensor(day_index, "dominant_direction", "°"))
        entities.append(WillyWindForecastSensor(day_index, "dominant_direction_text", None))
        entities.append(WillyWindForecastSensor(day_index, "dominant_direction_abbreviation", None))
    add_entities(entities)


class WillyWindForecastSensor(SensorEntity):

    def __init__(self, day_index: int, metric: str, unit: str | None) -> None:
        self._day_index = day_index
        self._metric = metric
        self._unit = unit
        self._state = None
        self._attr_unique_id = f"willy_wind_forecast_{metric}_{day_index}"

    @property
    def name(self) -> str:
        return f"willy_wind_forecast_{self._metric}_{self._day_index}"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self) -> str | None:
        return self._unit

    def update(self) -> None:
        forecast = self.hass.data[DOMAIN].get("forecast", [])
        if self._day_index < len(forecast):
            self._state = forecast[self._day_index].get(self._metric)
