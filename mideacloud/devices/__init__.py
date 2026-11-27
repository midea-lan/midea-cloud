"""Midea cloud devices."""

from mideacloud.cloud import MideaCloud
from mideacloud.models import MideaCloudAppliance

from .ac import (
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
    TARGET_TEMPERATURE_STEP,
    ACFanSpeed,
    ACMode,
    ACPreset,
    ACSwingMode,
    MideaCloudACDevice,
)
from .base import MideaCloudDevice

_DEVICE_TYPES: dict[int, type[MideaCloudDevice]] = {
    0xAC: MideaCloudACDevice,
}


def get_cloud_device(
    cloud: MideaCloud,
    appliance: MideaCloudAppliance,
) -> MideaCloudDevice | None:
    """Return the device for a cloud appliance, or None if its type is unsupported."""
    if device_class := _DEVICE_TYPES.get(appliance.appliance_type):
        return device_class(cloud, appliance)
    return None


__all__ = [
    "MAX_TARGET_TEMPERATURE",
    "MIN_TARGET_TEMPERATURE",
    "TARGET_TEMPERATURE_STEP",
    "ACFanSpeed",
    "ACMode",
    "ACPreset",
    "ACSwingMode",
    "MideaCloudACDevice",
    "MideaCloudDevice",
    "get_cloud_device",
]
