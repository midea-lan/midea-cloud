"""Midea cloud device tests."""

from dataclasses import replace
from typing import Any

import pytest

from mideacloud import MeijuCloud
from mideacloud.devices import (
    ACFanSpeed,
    ACMode,
    ACPreset,
    ACSwingMode,
    MideaCloudACDevice,
    get_cloud_device,
)

from .common import MockedCloud, mock_meiju_login, reply, request_bodies
from .const import APPLIANCE, MEIJU_CONTROL, MEIJU_STATUS

pytestmark = pytest.mark.asyncio

STATUS = {
    "power": "on",
    "mode": "cool",
    "temperature": 24,
    "small_temperature": 0.5,
    "indoor_temperature": 26.5,
    "eco": "off",
    "comfort_power_save": "off",
    "cool_power_saving": 0,
    "strong_wind": "off",
    "wind_swing_lr": "off",
    "wind_swing_ud": "on",
    "wind_speed": 60,
}


async def _refreshed_ac(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    status: dict[str, Any],
) -> MideaCloudACDevice:
    """Return an air conditioner whose first refresh reported a status."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload=reply(status))
    mocked.post(MEIJU_STATUS, payload=reply(), repeat=4)
    device = MideaCloudACDevice(meiju, APPLIANCE)
    await device.async_refresh()
    return device


async def test_refresh_merges_queries(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test a refresh runs every query and merges the replies."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload=reply({"power": "on", "mode": "cool"}))
    mocked.post(MEIJU_STATUS, payload=reply({"mode": "heat"}))
    mocked.post(MEIJU_STATUS, payload=reply(), repeat=2)
    mocked.post(MEIJU_STATUS, payload=reply({"indoor_temperature": 21}))
    device = MideaCloudACDevice(meiju, APPLIANCE)

    await device.async_refresh()

    assert device.attributes == {
        "power": "on",
        "mode": "heat",
        "indoor_temperature": 21,
    }
    assert [body["command"] for body in request_bodies(mocked, MEIJU_STATUS)] == [
        {"query": {}},
        {"query": {"query_type": "run_status"}},
        {"query": {"query_type": "indoor_humidity"}},
        {"query": {"query_type": "indoor_temperature"}},
        {"query": {"query_type": "group_data_four"}},
    ]


async def test_refresh_skips_unsupported_query(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test a query the Lua codec cannot decode is not sent again."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload=reply())
    mocked.post(MEIJU_STATUS, payload=reply(code=1014))
    mocked.post(MEIJU_STATUS, payload=reply(), repeat=3 + 4)
    device = MideaCloudACDevice(meiju, APPLIANCE)

    await device.async_refresh()
    await device.async_refresh()

    queries = [body["command"] for body in request_bodies(mocked, MEIJU_STATUS)]
    assert queries.count({"query": {"query_type": "run_status"}}) == 1
    assert len(queries) == 5 + 4


async def test_ac_state(mocked: MockedCloud, meiju: MeijuCloud) -> None:
    """Test the air conditioner state is read from the status."""
    device = await _refreshed_ac(mocked, meiju, STATUS)

    assert device.power is True
    assert device.mode is ACMode.COOL
    assert device.target_temperature == 24.5
    assert device.indoor_temperature == 26.5
    assert device.preset is ACPreset.NONE
    assert device.swing_mode is ACSwingMode.VERTICAL
    assert device.fan_speed is ACFanSpeed.MEDIUM


async def test_ac_unknown_state(mocked: MockedCloud, meiju: MeijuCloud) -> None:
    """Test missing or unknown status values read as None."""
    device = await _refreshed_ac(
        mocked,
        meiju,
        {"power": "standby", "mode": "turbo", "temperature": 24, "wind_speed": 50},
    )

    assert device.power is None
    assert device.mode is None
    assert device.target_temperature is None
    assert device.indoor_temperature is None
    assert device.preset is None
    assert device.swing_mode is None
    assert device.fan_speed is None


@pytest.mark.parametrize(
    ("status", "power", "preset"),
    [
        pytest.param({"power": True}, True, None, id="bool"),
        pytest.param({"power": 0}, False, None, id="number"),
        pytest.param({"power": "1"}, True, None, id="numeric_string"),
        pytest.param({"power": "no"}, False, None, id="no"),
        pytest.param({"power": None}, None, None, id="null"),
        pytest.param(
            {"eco": "on", "cool_power_saving": "1"},
            None,
            ACPreset.ECO,
            id="eco",
        ),
        pytest.param(
            {"comfort_power_save": "on"}, None, ACPreset.COMFORT, id="comfort"
        ),
        pytest.param({"strong_wind": 1}, None, ACPreset.BOOST, id="boost"),
    ],
)
async def test_ac_value_formats(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    status: dict[str, Any],
    power: bool | None,
    preset: ACPreset | None,
) -> None:
    """Test on/off values are read across the wire formats appliances use."""
    device = await _refreshed_ac(mocked, meiju, status)

    assert device.power is power
    assert device.preset is preset


@pytest.mark.parametrize(
    ("method", "args", "control"),
    [
        pytest.param(
            "async_turn_on",
            (),
            {"power": "on", "mode": "cool"},
            id="turn_on",
        ),
        pytest.param("async_turn_off", (), {"power": "off"}, id="turn_off"),
        pytest.param(
            "async_set_mode",
            (ACMode.HEAT,),
            {"power": "on", "mode": "heat"},
            id="mode",
        ),
        pytest.param(
            "async_set_target_temperature",
            (22.5,),
            {"temperature": 22, "small_temperature": 0.5},
            id="temperature",
        ),
        pytest.param(
            "async_set_target_temperature",
            (21.9, ACMode.DRY),
            {"power": "on", "mode": "dry", "temperature": 22, "small_temperature": 0.0},
            id="temperature_and_mode",
        ),
        pytest.param(
            "async_set_preset",
            (ACPreset.NONE,),
            {
                "eco": "off",
                "comfort_power_save": "off",
                "cool_power_saving": 0,
                "strong_wind": "off",
            },
            id="preset_none",
        ),
        pytest.param(
            "async_set_preset",
            (ACPreset.BOOST,),
            {
                "eco": "off",
                "comfort_power_save": "off",
                "cool_power_saving": 0,
                "strong_wind": "on",
            },
            id="preset_boost",
        ),
        pytest.param(
            "async_set_swing_mode",
            (ACSwingMode.BOTH,),
            {"wind_swing_lr": "on", "wind_swing_ud": "on"},
            id="swing",
        ),
        pytest.param(
            "async_set_fan_speed",
            (ACFanSpeed.AUTO,),
            {"wind_speed": 102},
            id="fan_speed",
        ),
    ],
)
async def test_ac_control(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    method: str,
    args: tuple[Any, ...],
    control: dict[str, Any],
) -> None:
    """Test controls send the fields to change along with the current status."""
    device = await _refreshed_ac(mocked, meiju, STATUS)
    mocked.post(MEIJU_CONTROL, payload=reply())

    await getattr(device, method)(*args)

    assert request_bodies(mocked, MEIJU_CONTROL)[0]["command"] == {
        "control": control,
        "status": STATUS,
    }
    assert device.attributes == STATUS | control


async def test_control_drops_fields_the_appliance_lacks(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test fields the appliance never reported are not sent."""
    device = await _refreshed_ac(mocked, meiju, {"power": "off", "eco": "on"})
    mocked.post(MEIJU_CONTROL, payload=reply(), repeat=2)

    await device.async_set_preset(ACPreset.NONE)
    await device.async_turn_on()

    assert [
        body["command"]["control"] for body in request_bodies(mocked, MEIJU_CONTROL)
    ] == [{"eco": "off"}, {"power": "on"}]


async def test_control_without_status_sends_everything(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test controls before the first refresh are sent in full."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_CONTROL, payload=reply())
    device = MideaCloudACDevice(meiju, APPLIANCE)

    await device.async_set_swing_mode(ACSwingMode.OFF)

    assert request_bodies(mocked, MEIJU_CONTROL)[0]["command"] == {
        "control": {"wind_swing_lr": "off", "wind_swing_ud": "off"},
    }


async def test_preset_replaces_previous_preset(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test selecting a preset turns the previous one off."""
    device = await _refreshed_ac(
        mocked,
        meiju,
        STATUS | {"eco": "on", "cool_power_saving": 1},
    )
    mocked.post(MEIJU_CONTROL, payload=reply())

    await device.async_set_preset(ACPreset.BOOST)

    assert device.preset is ACPreset.BOOST


async def test_controls_before_refresh_are_not_filtered(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test fields sent before the first refresh do not limit later controls."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_CONTROL, payload=reply(), repeat=2)
    device = MideaCloudACDevice(meiju, APPLIANCE)

    await device.async_set_mode(ACMode.COOL)
    await device.async_set_target_temperature(22.5)

    assert request_bodies(mocked, MEIJU_CONTROL)[1]["command"]["control"] == {
        "temperature": 22,
        "small_temperature": 0.5,
    }


async def test_control_with_nothing_to_send(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test a control with no field the appliance reports sends nothing."""
    device = await _refreshed_ac(mocked, meiju, {"power": "on"})

    await device.async_set_fan_speed(ACFanSpeed.LOW)

    assert MEIJU_CONTROL not in mocked.requests


async def test_get_cloud_device(meiju: MeijuCloud) -> None:
    """Test the device class is picked by appliance type."""
    assert isinstance(get_cloud_device(meiju, APPLIANCE), MideaCloudACDevice)
    assert get_cloud_device(meiju, replace(APPLIANCE, appliance_type=0xA1)) is None
