"""Midea cloud air conditioner (0xAC)."""

from enum import IntEnum, StrEnum
from typing import Any

from .base import MideaCloudDevice, as_bool, as_float, values_match

MIN_TARGET_TEMPERATURE = 17.0
MAX_TARGET_TEMPERATURE = 30.0
TARGET_TEMPERATURE_STEP = 0.5

_POWER = "power"
_MODE = "mode"
_TEMPERATURE = "temperature"
_SMALL_TEMPERATURE = "small_temperature"
_INDOOR_TEMPERATURE = "indoor_temperature"
_WIND_SPEED = "wind_speed"
_ON = "on"
_OFF = "off"


class ACMode(StrEnum):
    """Air conditioner operating mode."""

    AUTO = "auto"
    COOL = "cool"
    DRY = "dry"
    FAN = "fan"
    HEAT = "heat"


class ACPreset(StrEnum):
    """Air conditioner preset."""

    NONE = "none"
    ECO = "eco"
    COMFORT = "comfort"
    BOOST = "boost"


class ACSwingMode(StrEnum):
    """Air conditioner louver swing."""

    OFF = "off"
    BOTH = "both"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class ACFanSpeed(IntEnum):
    """Air conditioner fan speed, as the wind_speed status value."""

    SILENT = 20
    LOW = 40
    MEDIUM = 60
    HIGH = 80
    FULL = 100
    AUTO = 102


# Matched in order, so NONE (everything off) is checked first.
_PRESETS: dict[ACPreset, dict[str, Any]] = {
    ACPreset.NONE: {
        "eco": _OFF,
        "comfort_power_save": _OFF,
        "cool_power_saving": 0,
        "strong_wind": _OFF,
    },
    ACPreset.ECO: {"eco": _ON, "cool_power_saving": 1},
    ACPreset.COMFORT: {"comfort_power_save": _ON},
    ACPreset.BOOST: {"strong_wind": _ON},
}

_SWING_MODES: dict[ACSwingMode, dict[str, Any]] = {
    ACSwingMode.OFF: {"wind_swing_lr": _OFF, "wind_swing_ud": _OFF},
    ACSwingMode.BOTH: {"wind_swing_lr": _ON, "wind_swing_ud": _ON},
    ACSwingMode.HORIZONTAL: {"wind_swing_lr": _ON, "wind_swing_ud": _OFF},
    ACSwingMode.VERTICAL: {"wind_swing_lr": _OFF, "wind_swing_ud": _ON},
}


class MideaCloudACDevice(MideaCloudDevice):
    """Air conditioner read and controlled through the cloud."""

    queries = (
        {},
        {"query_type": "run_status"},
        {"query_type": "indoor_humidity"},
        {"query_type": "indoor_temperature"},
        {"query_type": "group_data_four"},
    )

    def _matches(self, fields: dict[str, Any]) -> bool:
        for key, expected in fields.items():
            value = self._attributes.get(key)
            if value is None or not values_match(value, expected):
                return False
        return True

    @property
    def power(self) -> bool | None:
        """Return whether the air conditioner is on."""
        return as_bool(self._attributes.get(_POWER))

    @property
    def mode(self) -> ACMode | None:
        """Return the operating mode."""
        value = self._attributes.get(_MODE)
        return next((mode for mode in ACMode if values_match(value, mode)), None)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        whole = as_float(self._attributes.get(_TEMPERATURE))
        fraction = as_float(self._attributes.get(_SMALL_TEMPERATURE))
        if whole is None or fraction is None:
            return None
        return whole + fraction

    @property
    def indoor_temperature(self) -> float | None:
        """Return the indoor temperature."""
        return as_float(self._attributes.get(_INDOOR_TEMPERATURE))

    @property
    def preset(self) -> ACPreset | None:
        """Return the active preset."""
        return next(
            (preset for preset, fields in _PRESETS.items() if self._matches(fields)),
            None,
        )

    @property
    def swing_mode(self) -> ACSwingMode | None:
        """Return the louver swing."""
        return next(
            (swing for swing, fields in _SWING_MODES.items() if self._matches(fields)),
            None,
        )

    @property
    def fan_speed(self) -> ACFanSpeed | None:
        """Return the fan speed."""
        value = self._attributes.get(_WIND_SPEED)
        return next(
            (speed for speed in ACFanSpeed if values_match(value, int(speed))),
            None,
        )

    async def async_turn_on(self) -> None:
        """Turn the air conditioner on in its last mode."""
        control: dict[str, Any] = {_POWER: _ON}
        if (mode := self._attributes.get(_MODE)) is not None:
            # The Lua codec needs the mode to build a power-on command.
            control[_MODE] = mode
        await self.async_set(control)

    async def async_turn_off(self) -> None:
        """Turn the air conditioner off."""
        await self.async_set({_POWER: _OFF})

    async def async_set_mode(self, mode: ACMode) -> None:
        """Turn the air conditioner on in an operating mode."""
        await self.async_set({_POWER: _ON, _MODE: str(mode)})

    async def async_set_target_temperature(
        self,
        temperature: float,
        mode: ACMode | None = None,
    ) -> None:
        """Set the target temperature, optionally switching mode."""
        whole, half = divmod(round(temperature / TARGET_TEMPERATURE_STEP), 2)
        control: dict[str, Any] = {}
        if mode is not None:
            control = {_POWER: _ON, _MODE: str(mode)}
        control[_TEMPERATURE] = whole
        control[_SMALL_TEMPERATURE] = half * TARGET_TEMPERATURE_STEP
        await self.async_set(control)

    async def async_set_preset(self, preset: ACPreset) -> None:
        """Set the preset."""
        await self.async_set(dict(_PRESETS[preset]))

    async def async_set_swing_mode(self, swing_mode: ACSwingMode) -> None:
        """Set the louver swing."""
        await self.async_set(dict(_SWING_MODES[swing_mode]))

    async def async_set_fan_speed(self, fan_speed: ACFanSpeed) -> None:
        """Set the fan speed."""
        await self.async_set({_WIND_SPEED: int(fan_speed)})
