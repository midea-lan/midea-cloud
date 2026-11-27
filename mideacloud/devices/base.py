"""Midea cloud device base."""

import logging
from typing import Any

from mideacloud.cloud import MideaCloud
from mideacloud.exceptions import MideaCloudLuaAnalysisError
from mideacloud.models import MideaCloudAppliance

_LOGGER = logging.getLogger(__name__)

_ON_VALUES = frozenset({"on", "yes", "true"})
_OFF_VALUES = frozenset({"off", "no", "false", "invalid", "unknown"})


def as_bool(value: object) -> bool | None:
    """Return the on/off state of a status value, if it has one."""
    if isinstance(value, str):
        normalized = value.lower()
        if normalized in _ON_VALUES:
            return True
        if normalized in _OFF_VALUES:
            return False
        value = as_float(normalized)
    if isinstance(value, int | float):
        return bool(value)
    return None


def as_float(value: object) -> float | None:
    """Return a status value as a float, if it is a number."""
    if not isinstance(value, str | int | float):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def values_match(value: object, expected: object) -> bool:
    """Compare a status value with an expected value across wire formats."""
    if value == expected:
        return True
    value_float, expected_float = as_float(value), as_float(expected)
    if value_float is not None and expected_float is not None:
        return value_float == expected_float
    value_bool, expected_bool = as_bool(value), as_bool(expected)
    if value_bool is not None and expected_bool is not None:
        return value_bool == expected_bool
    return str(value) == str(expected)


class MideaCloudDevice:
    """An appliance read and controlled through the cloud Lua codec."""

    queries: tuple[dict[str, Any], ...] = ({},)

    def __init__(self, cloud: MideaCloud, appliance: MideaCloudAppliance) -> None:
        """Initialize the device."""
        self._cloud = cloud
        self.appliance = appliance
        self._attributes: dict[str, Any] = {}
        self._reported_fields: set[str] = set()
        self._unsupported_queries: set[int] = set()

    @property
    def attributes(self) -> dict[str, Any]:
        """Return a copy of the last known status."""
        return dict(self._attributes)

    async def async_refresh(self) -> None:
        """Run every status query and merge the replies."""
        for index, query in enumerate(self.queries):
            if index in self._unsupported_queries:
                continue
            try:
                status = await self._cloud.get_device_status(self.appliance, query)
            except MideaCloudLuaAnalysisError:
                # The appliance's Lua codec cannot decode this query; it never will.
                _LOGGER.debug(
                    "Appliance %s does not support query %s",
                    self.appliance.appliance_code,
                    query,
                )
                self._unsupported_queries.add(index)
                continue
            self._attributes.update(status)
            self._reported_fields.update(status)

    async def async_set(self, control: dict[str, Any]) -> None:
        """Send the control fields the appliance reports and store them."""
        if self._reported_fields:
            control = {
                key: value
                for key, value in control.items()
                if key in self._reported_fields
            }
        if not control:
            return
        await self._cloud.send_device_control(
            self.appliance,
            control,
            self._attributes,
        )
        self._attributes.update(control)
