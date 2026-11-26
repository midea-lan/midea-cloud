"""Midea Cloud client tests."""

import asyncio
from typing import Any
from unittest.mock import Mock

import pytest
from aiohttp import ClientError

from mideacloud import (
    MeijuCloud,
    MideaCloudApiError,
    MideaCloudAppliance,
    MideaCloudAuthError,
    MideaCloudConnectionError,
    MideaCloudLuaAnalysisError,
    MideaCloudName,
    MSmartHomeCloud,
    get_midea_cloud,
)

from .common import (
    MockedCloud,
    meiju_encrypt_sn,
    mock_meiju_login,
    mock_msmarthome_login,
    msmarthome_encrypt_sn,
    msmarthome_fixed_encrypt,
    reply,
    request_bodies,
    request_headers,
)
from .const import (
    MEIJU_API,
    MSMARTHOME_API,
    MSMARTHOME_REGIONAL_API,
    TEST_ACCESS_TOKEN,
    TEST_ACCOUNT,
    TEST_APPLIANCE_CODE,
    TEST_HOME_ID,
    TEST_LOGIN_ID,
    TEST_NEW_ACCESS_TOKEN,
    TEST_PASSWORD,
    TEST_SN,
    TEST_SN8,
    TEST_UID,
)

MEIJU_STATUS = MEIJU_API + "/mjl/v1/device/status/lua/get"
MEIJU_CONTROL = MEIJU_API + "/mjl/v1/device/lua/control"
MEIJU_LOGIN = MEIJU_API + "/mj/user/login"
MSMARTHOME_STATUS = MSMARTHOME_REGIONAL_API + "/v1/device/status/lua/get"
MSMARTHOME_CONTROL = MSMARTHOME_REGIONAL_API + "/v1/device/lua/control"

APPLIANCE = MideaCloudAppliance(
    appliance_code=TEST_APPLIANCE_CODE,
    name="Living room",
    appliance_type=0xAC,
    sn=TEST_SN,
    sn8=TEST_SN8,
    model=TEST_SN8,
    model_number="12",
    manufacturer_code="0000",
    smart_product_id="10001",
    category="AC",
    online=True,
)

pytestmark = pytest.mark.asyncio


async def test_msmarthome_login_and_list_appliances(
    mocked: MockedCloud,
    msmarthome: MSmartHomeCloud,
) -> None:
    """Test MSmartHome logs in on the regional server and lists appliances."""
    mock_msmarthome_login(mocked)
    mocked.post(
        MSMARTHOME_REGIONAL_API + "/v1/appliance/user/list/get",
        payload=reply(
            {
                "list": [
                    {
                        "id": str(TEST_APPLIANCE_CODE),
                        "name": "Living room",
                        "type": "0xAC",
                        "sn": msmarthome_encrypt_sn(TEST_SN),
                        "modelNumber": "12",
                        "enterpriseCode": "0000",
                        "smartProductId": "10001",
                        "category": "AC",
                        "onlineStatus": "1",
                    },
                    {"id": "2", "name": "Dehumidifier", "type": "0xA1"},
                ],
            },
        ),
    )

    await msmarthome.login()
    appliances = await msmarthome.list_appliances()

    assert appliances == {
        TEST_APPLIANCE_CODE: APPLIANCE,
        2: MideaCloudAppliance(
            appliance_code=2,
            name="Dehumidifier",
            appliance_type=0xA1,
            sn="",
            sn8="",
            model="",
            model_number="0",
            manufacturer_code="0000",
            smart_product_id=None,
            category=None,
            online=False,
        ),
    }
    login_body = request_bodies(
        mocked,
        MSMARTHOME_REGIONAL_API + "/mj/user/login",
    )[0]
    assert login_body["iotData"]["loginAccount"] == TEST_ACCOUNT
    assert "uid" not in login_body["iotData"]
    assert TEST_PASSWORD not in str(login_body)
    list_headers = request_headers(
        mocked,
        MSMARTHOME_REGIONAL_API + "/v1/appliance/user/list/get",
    )[0]
    assert list_headers["uid"] == TEST_UID
    assert list_headers["accesstoken"] == TEST_ACCESS_TOKEN


async def test_msmarthome_keeps_server_without_route(
    mocked: MockedCloud,
    msmarthome: MSmartHomeCloud,
) -> None:
    """Test MSmartHome stays on the default server when no route is returned."""
    mocked.post(
        MSMARTHOME_API + "/v1/unitcenter/router/user/name",
        payload=reply({}),
    )
    mocked.post(
        MSMARTHOME_API + "/v1/user/login/id/get",
        payload=reply({"loginId": TEST_LOGIN_ID}),
    )
    mocked.post(
        MSMARTHOME_API + "/mj/user/login",
        payload=reply({}, code=3102),
    )

    with pytest.raises(MideaCloudAuthError) as err:
        await msmarthome.login()

    assert err.value.translation_key == "invalid_auth"


async def test_meiju_login_and_list_appliances(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test Meiju lists the appliances of every home."""
    mock_meiju_login(mocked)
    mocked.post(
        MEIJU_API + "/v1/homegroup/list/get",
        payload=reply(
            {"homeList": [{"homegroupId": str(TEST_HOME_ID)}, {"homegroupId": "7"}]},
        ),
    )
    mocked.post(
        MEIJU_API + "/v1/appliance/home/list/get",
        payload=reply(
            {
                "homeList": [
                    {
                        "roomList": [
                            {
                                "applianceList": [
                                    {
                                        "applianceCode": str(TEST_APPLIANCE_CODE),
                                        "name": "Living room",
                                        "type": "0xAC",
                                        "sn": meiju_encrypt_sn(TEST_SN),
                                        "sn8": TEST_SN8,
                                        "productModel": "KFR-35GW",
                                        "modelNumber": "12",
                                        "enterpriseCode": "0000",
                                        "smartProductId": "10001",
                                        "category": "AC",
                                        "onlineStatus": "1",
                                    },
                                ],
                            },
                            {"applianceList": None},
                        ],
                    },
                ],
            },
        ),
    )
    mocked.post(
        MEIJU_API + "/v1/appliance/home/list/get",
        payload=reply(
            {
                "homeList": [
                    {
                        "roomList": [
                            {
                                "applianceList": [
                                    {
                                        "applianceCode": "2",
                                        "name": "Water heater",
                                        "type": "0xE2",
                                        "onlineStatus": "0",
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ),
    )

    await meiju.login()
    appliances = await meiju.list_appliances()

    assert appliances == {
        TEST_APPLIANCE_CODE: MideaCloudAppliance(
            appliance_code=TEST_APPLIANCE_CODE,
            name="Living room",
            appliance_type=0xAC,
            sn=TEST_SN,
            sn8=TEST_SN8,
            model="KFR-35GW",
            model_number="12",
            manufacturer_code="0000",
            smart_product_id="10001",
            category="AC",
            online=True,
        ),
        2: MideaCloudAppliance(
            appliance_code=2,
            name="Water heater",
            appliance_type=0xE2,
            sn="",
            sn8="00000000",
            model="00000000",
            model_number="0",
            manufacturer_code="0000",
            smart_product_id=None,
            category=None,
            online=False,
        ),
    }
    assert [
        body["homegroupId"]
        for body in request_bodies(mocked, MEIJU_API + "/v1/appliance/home/list/get")
    ] == [str(TEST_HOME_ID), "7"]


async def test_msmarthome_get_device_status(
    mocked: MockedCloud,
    msmarthome: MSmartHomeCloud,
) -> None:
    """Test the MSmartHome status request logs in first and describes the appliance."""
    mock_msmarthome_login(mocked)
    mocked.post(MSMARTHOME_STATUS, payload=reply({"power": "on"}))

    status = await msmarthome.get_device_status(
        APPLIANCE,
        {"query_type": "run_status"},
    )

    assert status == {"power": "on"}
    body = request_bodies(mocked, MSMARTHOME_STATUS)[0]
    assert body["command"] == {"query": {"query_type": "run_status"}}
    assert body["applianceCode"] == TEST_APPLIANCE_CODE
    assert body["applianceType"] == "0xAC"
    assert body["applianceMFCode"] == "0000"
    assert body["modelNumber"] == "12"
    assert body["applianceSn"] == msmarthome_fixed_encrypt(TEST_SN.encode("ascii"))
    assert body["encryptedType "] == "2"


async def test_meiju_get_device_status_default_query(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test the Meiju status request sends an empty query by default."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload=reply())

    assert await meiju.get_device_status(APPLIANCE) == {}

    body = request_bodies(mocked, MEIJU_STATUS)[0]
    assert body["applianceCode"] == str(TEST_APPLIANCE_CODE)
    assert body["command"] == {"query": {}}


@pytest.mark.parametrize(
    ("status", "command"),
    [
        pytest.param(
            {"power": "on", "mode": "cool"},
            {
                "control": {"temperature": 24},
                "status": {"power": "on", "mode": "cool"},
            },
            id="with_status",
        ),
        pytest.param(None, {"control": {"temperature": 24}}, id="without_status"),
    ],
)
async def test_send_device_control(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    status: dict[str, Any] | None,
    command: dict[str, Any],
) -> None:
    """Test the control request carries the control and the current status."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_CONTROL, payload=reply())

    await meiju.send_device_control(APPLIANCE, {"temperature": 24}, status)

    assert request_bodies(mocked, MEIJU_CONTROL)[0]["command"] == command


async def test_msmarthome_send_device_control(
    mocked: MockedCloud,
    msmarthome: MSmartHomeCloud,
) -> None:
    """Test the MSmartHome control endpoint."""
    mock_msmarthome_login(mocked)
    mocked.post(MSMARTHOME_CONTROL, payload=reply())

    await msmarthome.send_device_control(APPLIANCE, {"power": "off"})

    assert request_bodies(mocked, MSMARTHOME_CONTROL)[0]["command"] == {
        "control": {"power": "off"},
    }


async def test_relogin_on_expired_token(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test an expired access token triggers a new login and a retry."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload=reply(code=40002))
    mock_meiju_login(mocked, TEST_NEW_ACCESS_TOKEN)
    mocked.post(MEIJU_STATUS, payload=reply({"power": "on"}))

    assert await meiju.get_device_status(APPLIANCE) == {"power": "on"}

    assert [
        headers["accesstoken"] for headers in request_headers(mocked, MEIJU_STATUS)
    ] == [TEST_ACCESS_TOKEN, TEST_NEW_ACCESS_TOKEN]


async def test_concurrent_requests_share_relogin(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test requests failing on the same expired token log in only once."""
    mock_meiju_login(mocked)
    await meiju.login()
    mocked.post(MEIJU_STATUS, payload=reply(code=40002), repeat=2)
    mock_meiju_login(mocked, TEST_NEW_ACCESS_TOKEN)
    mocked.post(MEIJU_STATUS, payload=reply({"power": "on"}), repeat=2)

    results = await asyncio.gather(
        meiju.get_device_status(APPLIANCE),
        meiju.get_device_status(APPLIANCE),
    )

    assert list(results) == [{"power": "on"}, {"power": "on"}]
    assert len(request_bodies(mocked, MEIJU_LOGIN)) == 2


async def test_waiting_request_logs_in_after_failed_relogin(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test a request waiting on a failed re-login logs in itself."""
    mock_meiju_login(mocked)
    await meiju.login()
    mocked.post(MEIJU_STATUS, payload=reply(code=40002), repeat=2)
    mocked.post(MEIJU_API + "/v1/user/login/id/get", exception=ClientError("boom"))
    mock_meiju_login(mocked, TEST_NEW_ACCESS_TOKEN)
    mocked.post(MEIJU_STATUS, payload=reply({"power": "on"}))

    results = await asyncio.gather(
        meiju.get_device_status(APPLIANCE),
        meiju.get_device_status(APPLIANCE),
        return_exceptions=True,
    )

    assert isinstance(results[0], MideaCloudConnectionError)
    assert results[1] == {"power": "on"}
    assert request_headers(mocked, MEIJU_STATUS)[-1]["accesstoken"] == (
        TEST_NEW_ACCESS_TOKEN
    )


@pytest.mark.parametrize(
    ("cloud_fixture", "api_url", "login_data"),
    [
        pytest.param("meiju", MEIJU_API, {}, id="meiju_missing_fields"),
        pytest.param(
            "meiju",
            MEIJU_API,
            {"key": "not-hex", "mdata": {"accessToken": TEST_ACCESS_TOKEN}},
            id="meiju_invalid_key",
        ),
        pytest.param("msmarthome", MSMARTHOME_API, {}, id="msmarthome_missing_fields"),
        pytest.param(
            "msmarthome",
            MSMARTHOME_API,
            {
                "uid": TEST_UID,
                "accessToken": "not-hex",
                "randomData": "not-hex",
                "mdata": {"accessToken": TEST_ACCESS_TOKEN},
            },
            id="msmarthome_invalid_key",
        ),
    ],
)
async def test_invalid_login_reply(
    mocked: MockedCloud,
    request: pytest.FixtureRequest,
    cloud_fixture: str,
    api_url: str,
    login_data: dict[str, Any],
) -> None:
    """Test a malformed login reply is raised as a connection error."""
    cloud: MeijuCloud | MSmartHomeCloud = request.getfixturevalue(cloud_fixture)
    mocked.post(MSMARTHOME_API + "/v1/unitcenter/router/user/name", payload=reply())
    mocked.post(
        api_url + "/v1/user/login/id/get",
        payload=reply({"loginId": TEST_LOGIN_ID}),
    )
    mocked.post(api_url + "/mj/user/login", payload=reply(login_data))

    with pytest.raises(MideaCloudConnectionError):
        await cloud.login()


@pytest.mark.parametrize(
    ("sn", "sn8"),
    [
        pytest.param("0" * 9 + "ABCDEFGH", "ABCDEFGH", id="sn8_at_end"),
        pytest.param("0" * 9 + "ABCDEFG", "", id="too_short"),
    ],
)
async def test_msmarthome_sn8(
    mocked: MockedCloud,
    msmarthome: MSmartHomeCloud,
    sn: str,
    sn8: str,
) -> None:
    """Test the MSmartHome sn8 is cut from the serial number when long enough."""
    mock_msmarthome_login(mocked)
    mocked.post(
        MSMARTHOME_REGIONAL_API + "/v1/appliance/user/list/get",
        payload=reply(
            {
                "list": [
                    {
                        "id": "2",
                        "name": "Dehumidifier",
                        "type": "0xA1",
                        "sn": msmarthome_encrypt_sn(sn),
                    },
                ],
            },
        ),
    )

    await msmarthome.login()
    appliances = await msmarthome.list_appliances()

    assert appliances[2].sn8 == sn8
    assert appliances[2].model == sn8


async def test_expired_token_during_login_not_retried(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test an expired session error from the login itself is raised."""
    mocked.post(
        MEIJU_API + "/v1/user/login/id/get",
        payload=reply(code=3106),
    )

    with pytest.raises(MideaCloudApiError) as err:
        await meiju.login()

    assert err.value.translation_key == "cloud_session_expired"


async def test_missing_login_id(mocked: MockedCloud, meiju: MeijuCloud) -> None:
    """Test a login id reply without a login id fails the login."""
    mocked.post(MEIJU_API + "/v1/user/login/id/get", payload=reply({}))

    with pytest.raises(MideaCloudAuthError):
        await meiju.login()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ClientError("boom"), id="client_error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_connection_error(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    exception: Exception,
) -> None:
    """Test transport errors are raised as connection errors."""
    mocked.post(MEIJU_API + "/v1/user/login/id/get", exception=exception)

    with pytest.raises(MideaCloudConnectionError) as err:
        await meiju.login()

    assert err.value.translation_key == "cannot_connect"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("not json", id="not_json"),
        pytest.param('{"msg": "no code"}', id="no_code"),
        pytest.param("[]", id="not_object"),
        pytest.param('{"code": 0, "data": ["unexpected"]}', id="data_not_object"),
    ],
)
async def test_invalid_reply(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    body: str,
) -> None:
    """Test unreadable replies are raised as connection errors."""
    mocked.post(MEIJU_API + "/v1/user/login/id/get", body=body)

    with pytest.raises(MideaCloudConnectionError):
        await meiju.login()


@pytest.mark.parametrize(
    ("code", "message"),
    [
        pytest.param(1014, "lua analysis exception", id="code"),
        pytest.param(1, "T_0000_AC.lua:12: attempt to index nil", id="stack_trace"),
        pytest.param(1, "Lua Analysis Exception", id="message"),
    ],
)
async def test_lua_analysis_error(
    mocked: MockedCloud,
    meiju: MeijuCloud,
    code: int,
    message: str,
) -> None:
    """Test Lua codec failures of the status endpoint get a dedicated error."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_STATUS, payload={"code": code, "msg": message})

    with pytest.raises(MideaCloudLuaAnalysisError):
        await meiju.get_device_status(APPLIANCE)


async def test_control_error_is_not_lua_analysis(
    mocked: MockedCloud,
    meiju: MeijuCloud,
) -> None:
    """Test a control failure is a plain API error."""
    mock_meiju_login(mocked)
    mocked.post(MEIJU_CONTROL, payload={"code": 1014, "msg": "lua analysis exception"})

    with pytest.raises(MideaCloudApiError) as err:
        await meiju.send_device_control(APPLIANCE, {"power": "on"})

    assert not isinstance(err.value, MideaCloudLuaAnalysisError)
    assert err.value.code == 1014
    assert err.value.translation_key == "cloud_error"


@pytest.mark.parametrize(
    ("cloud_name", "cloud_class"),
    [
        pytest.param(MideaCloudName.MEIJU, MeijuCloud, id="meiju"),
        pytest.param(MideaCloudName.MSMARTHOME, MSmartHomeCloud, id="msmarthome"),
    ],
)
async def test_get_midea_cloud(
    session: Mock,
    cloud_name: MideaCloudName,
    cloud_class: type,
) -> None:
    """Test the cloud factory."""
    assert isinstance(
        get_midea_cloud(cloud_name, session, TEST_ACCOUNT, TEST_PASSWORD),
        cloud_class,
    )
