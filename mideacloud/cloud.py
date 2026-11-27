"""Midea Cloud client."""

import asyncio
import base64
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from secrets import token_hex
from typing import Any, cast

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    CLOUDS,
    DEFAULT_MANUFACTURER_CODE,
    DEFAULT_SN8,
    MSMARTHOME_APP_VERSION,
    MSMARTHOME_SRC,
    ONLINE_STATUS,
    REQUEST_TIMEOUT,
    SN8_END,
    SN8_START,
    MideaCloudName,
)
from .exceptions import (
    LUA_ANALYSIS_ERROR_CODE,
    TOKEN_INVALID_CODES,
    MideaCloudApiError,
    MideaCloudAuthError,
    MideaCloudConnectionError,
    MideaCloudLuaAnalysisError,
    cloud_api_error,
)
from .models import MideaCloudAppliance
from .security import CloudSecurity, MeijuCloudSecurity, MSmartCloudSecurity

_LOGGER = logging.getLogger(__name__)

_NO_CODE = -1


def _stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")


def _is_lua_analysis_error(code: int, message: str) -> bool:
    # Some appliances answer with the Lua stack trace and no dedicated code.
    lowered = message.lower()
    return (
        code == LUA_ANALYSIS_ERROR_CODE
        or "lua analysis exception" in lowered
        or ".lua:" in lowered
    )


def _home_ids(reply: dict[str, Any]) -> list[Any]:
    return [home["homegroupId"] for home in reply.get("homeList") or []]


class MideaCloud(ABC):
    """Base Midea cloud client."""

    _status_endpoint: str
    _control_endpoint: str

    def __init__(
        self,
        session: ClientSession,
        account: str,
        password: str,
        security: CloudSecurity,
        cloud_name: MideaCloudName,
    ) -> None:
        """Initialize the cloud client."""
        definition = CLOUDS[cloud_name]
        self._session = session
        self._account = account
        self._password = password
        self._security = security
        self._app_id = definition.app_id
        self._app_key = definition.app_key
        self._api_url = definition.api_url
        self._device_id = CloudSecurity.get_device_id(account)
        self._access_token: str | None = None
        self._login_lock = asyncio.Lock()

    def _make_general_data(self) -> dict[str, Any]:
        return {}

    def _extra_headers(self) -> dict[str, str]:
        return {}

    async def _api_request(
        self,
        endpoint: str,
        data: dict[str, Any],
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Send a request, logging in again once if the access token expired."""
        if authenticated and self._access_token is None:
            await self._ensure_login(None)
        token = self._access_token
        try:
            return await self._send_request(endpoint, data)
        except MideaCloudApiError as err:
            if not authenticated or err.code not in TOKEN_INVALID_CODES:
                raise
        _LOGGER.debug("Midea cloud access token expired, logging in again")
        await self._ensure_login(token)
        return await self._send_request(endpoint, data)

    async def _ensure_login(self, expired_token: str | None) -> None:
        async with self._login_lock:
            # Another request may have logged in while this one waited.
            if self._access_token in (None, expired_token):
                self._access_token = None
                await self.login()

    async def _send_request(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        data.setdefault("reqId", token_hex(16))
        data.setdefault("stamp", _stamp())
        body = json.dumps(data)
        random = str(int(time.time()))
        headers = {
            "content-type": "application/json; charset=utf-8",
            "secretVersion": "1",
            "sign": self._security.sign(body, random),
            "random": random,
            **self._extra_headers(),
        }
        if self._access_token is not None:
            headers["accesstoken"] = self._access_token
        try:
            async with self._session.post(
                self._api_url + endpoint,
                headers=headers,
                data=body,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                raw = await response.read()
                http_ok = response.ok
        except (ClientError, TimeoutError) as err:
            raise MideaCloudConnectionError(
                f"Error requesting {endpoint}: {err!r}",
            ) from err
        try:
            reply = json.loads(raw)
            code = int(reply["code"])
        except (ValueError, TypeError, KeyError) as err:
            raise MideaCloudConnectionError(
                f"Invalid reply from {endpoint}",
            ) from err
        _LOGGER.debug("Midea cloud %s replied with code %s", endpoint, code)
        if code == 0:
            if not http_ok:
                raise MideaCloudConnectionError(
                    f"HTTP error from {endpoint} with a success code",
                )
            data = reply.get("data") or {}
            if not isinstance(data, dict):
                raise MideaCloudConnectionError(f"Invalid reply from {endpoint}")
            return data
        message = str(reply.get("msg") or reply.get("message") or "")
        if endpoint == self._status_endpoint and _is_lua_analysis_error(
            code,
            message,
        ):
            raise MideaCloudLuaAnalysisError(code, message)
        raise cloud_api_error(code, message)

    async def _get_login_id(self) -> str:
        data = self._make_general_data()
        data.update({"loginAccount": self._account, "type": "1"})
        response = await self._api_request(
            "/v1/user/login/id/get",
            data,
            authenticated=False,
        )
        if not (login_id := response.get("loginId")):
            raise MideaCloudAuthError(_NO_CODE, "No login id returned")
        return cast("str", login_id)

    def _decrypt_sn(self, encrypted_sn: str | None) -> str:
        if not encrypted_sn:
            return ""
        return self._security.aes_decrypt(bytes.fromhex(encrypted_sn))

    @abstractmethod
    async def login(self) -> None:
        """Log in to the cloud."""

    @abstractmethod
    async def list_appliances(self) -> dict[int, MideaCloudAppliance]:
        """Return the appliances of the account, by appliance code."""

    @staticmethod
    def _parse_list_reply[T](
        parse: Callable[[dict[str, Any]], T],
        reply: dict[str, Any],
    ) -> T:
        try:
            return parse(reply)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise MideaCloudConnectionError("Invalid appliance list reply") from err

    @abstractmethod
    def _parse_appliance(self, appliance: dict[str, Any]) -> MideaCloudAppliance:
        """Return the appliance described by an appliance list entry."""

    @abstractmethod
    def _command_data(self, appliance: MideaCloudAppliance) -> dict[str, Any]:
        """Return the appliance fields of a status or control request."""

    async def get_device_status(
        self,
        appliance: MideaCloudAppliance,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the appliance status decoded by the cloud-side Lua codec."""
        data = self._command_data(appliance)
        data["command"] = {"query": query or {}}
        return await self._api_request(self._status_endpoint, data)

    async def send_device_control(
        self,
        appliance: MideaCloudAppliance,
        control: dict[str, Any],
        status: dict[str, Any] | None = None,
    ) -> None:
        """Send a control command encoded by the cloud-side Lua codec."""
        data = self._command_data(appliance)
        command: dict[str, Any] = {"control": control}
        if status:
            command["status"] = status
        data["command"] = command
        await self._api_request(self._control_endpoint, data)


class MeijuCloud(MideaCloud):
    """Meiju (China) cloud client."""

    _status_endpoint = "/mjl/v1/device/status/lua/get"
    _control_endpoint = "/mjl/v1/device/lua/control"

    def __init__(self, session: ClientSession, account: str, password: str) -> None:
        """Initialize the Meiju cloud client."""
        definition = CLOUDS[MideaCloudName.MEIJU]
        super().__init__(
            session,
            account,
            password,
            MeijuCloudSecurity(
                definition.login_key,
                definition.iot_key,
                definition.hmac_key,
            ),
            MideaCloudName.MEIJU,
        )

    async def login(self) -> None:
        """Log in to the cloud."""
        login_id = await self._get_login_id()
        stamp = _stamp()
        data = {
            "iotData": {
                "clientType": 1,
                "deviceId": self._device_id,
                "iampwd": self._security.encrypt_iam_password(
                    login_id,
                    self._password,
                ),
                "iotAppId": self._app_id,
                "loginAccount": self._account,
                "password": self._security.encrypt_password(login_id, self._password),
                "reqId": token_hex(16),
                "stamp": stamp,
            },
            "data": {
                "appKey": self._app_key,
                "deviceId": self._device_id,
                "platform": 2,
            },
            "timestamp": stamp,
            "stamp": stamp,
        }
        response = await self._api_request(
            "/mj/user/login",
            data,
            authenticated=False,
        )
        try:
            access_token = response["mdata"]["accessToken"]
            key = self._security.aes_decrypt_with_fixed_key(
                bytes.fromhex(response["key"]),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise MideaCloudConnectionError("Invalid login reply") from err
        self._security.set_aes_keys(key.encode("ascii"), None)
        self._access_token = access_token

    async def list_appliances(self) -> dict[int, MideaCloudAppliance]:
        """Return the appliances of every home of the account."""
        homes = await self._api_request("/v1/homegroup/list/get", {})
        appliances: dict[int, MideaCloudAppliance] = {}
        for home_id in self._parse_list_reply(_home_ids, homes):
            response = await self._api_request(
                "/v1/appliance/home/list/get",
                {"homegroupId": home_id},
            )
            appliances |= self._parse_list_reply(self._home_appliances, response)
        return appliances

    def _home_appliances(
        self,
        reply: dict[str, Any],
    ) -> dict[int, MideaCloudAppliance]:
        appliances: dict[int, MideaCloudAppliance] = {}
        for home in reply.get("homeList") or []:
            for room in home.get("roomList") or []:
                for appliance in room.get("applianceList") or []:
                    parsed = self._parse_appliance(appliance)
                    appliances[parsed.appliance_code] = parsed
        return appliances

    def _parse_appliance(self, appliance: dict[str, Any]) -> MideaCloudAppliance:
        sn8 = appliance.get("sn8") or DEFAULT_SN8
        return MideaCloudAppliance(
            appliance_code=int(appliance["applianceCode"]),
            name=appliance["name"],
            appliance_type=int(appliance["type"], 16),
            sn=self._decrypt_sn(appliance.get("sn")),
            sn8=sn8,
            model=appliance.get("productModel") or sn8,
            model_number=appliance.get("modelNumber") or "0",
            manufacturer_code=appliance.get("enterpriseCode")
            or DEFAULT_MANUFACTURER_CODE,
            smart_product_id=appliance.get("smartProductId"),
            category=appliance.get("category"),
            online=appliance.get("onlineStatus") == ONLINE_STATUS,
        )

    def _command_data(self, appliance: MideaCloudAppliance) -> dict[str, Any]:
        return {"applianceCode": str(appliance.appliance_code)}


class MSmartHomeCloud(MideaCloud):
    """MSmartHome (international) cloud client."""

    _status_endpoint = "/v1/device/status/lua/get"
    _control_endpoint = "/v1/device/lua/control"

    def __init__(self, session: ClientSession, account: str, password: str) -> None:
        """Initialize the MSmartHome cloud client."""
        definition = CLOUDS[MideaCloudName.MSMARTHOME]
        self._msmart_security = MSmartCloudSecurity(
            definition.login_key,
            definition.iot_key,
            definition.hmac_key,
        )
        super().__init__(
            session,
            account,
            password,
            self._msmart_security,
            MideaCloudName.MSMARTHOME,
        )
        self._auth_base = base64.b64encode(
            f"{definition.app_key}:{definition.iot_key}".encode("ascii"),
        ).decode("ascii")
        self._uid = ""

    def _make_general_data(self) -> dict[str, Any]:
        return {
            "appVersion": MSMARTHOME_APP_VERSION,
            "src": MSMARTHOME_SRC,
            "format": "2",
            "stamp": _stamp(),
            "platformId": "1",
            "deviceId": self._device_id,
            "reqId": token_hex(16),
            "uid": self._uid,
            "clientType": "1",
            "appId": self._app_id,
        }

    def _extra_headers(self) -> dict[str, str]:
        headers = {
            "x-recipe-app": self._app_id,
            "authorization": f"Basic {self._auth_base}",
        }
        if self._uid:
            headers["uid"] = self._uid
        return headers

    async def _re_route(self) -> None:
        """Switch to the regional API server of the account."""
        data = self._make_general_data()
        data.update(
            {"userName": self._account, "platformId": "1", "userType": "0"},
        )
        response = await self._api_request(
            "/v1/unitcenter/router/user/name",
            data,
            authenticated=False,
        )
        if api_url := response.get("masUrl"):
            self._api_url = api_url

    async def login(self) -> None:
        """Log in to the cloud."""
        await self._re_route()
        login_id = await self._get_login_id()
        stamp = _stamp()
        iot_data = self._make_general_data()
        iot_data.pop("uid")
        iot_data.update(
            {
                "iampwd": self._security.encrypt_iam_password(
                    login_id,
                    self._password,
                ),
                "loginAccount": self._account,
                "password": self._security.encrypt_password(login_id, self._password),
                "stamp": stamp,
            },
        )
        data = {
            "iotData": iot_data,
            "data": {
                "appKey": self._app_key,
                "deviceId": self._device_id,
                "platform": "2",
            },
            "stamp": stamp,
        }
        response = await self._api_request(
            "/mj/user/login",
            data,
            authenticated=False,
        )
        try:
            uid = response["uid"]
            access_token = response["mdata"]["accessToken"]
            self._msmart_security.set_encrypted_aes_keys(
                response["accessToken"],
                response["randomData"],
            )
        except (KeyError, TypeError, ValueError) as err:
            raise MideaCloudConnectionError("Invalid login reply") from err
        self._uid = uid
        self._access_token = access_token

    async def list_appliances(self) -> dict[int, MideaCloudAppliance]:
        """Return the appliances of the account."""
        response = await self._api_request(
            "/v1/appliance/user/list/get",
            self._make_general_data(),
        )
        return self._parse_list_reply(self._user_appliances, response)

    def _user_appliances(
        self,
        reply: dict[str, Any],
    ) -> dict[int, MideaCloudAppliance]:
        appliances: dict[int, MideaCloudAppliance] = {}
        for appliance in reply.get("list") or []:
            parsed = self._parse_appliance(appliance)
            appliances[parsed.appliance_code] = parsed
        return appliances

    def _parse_appliance(self, appliance: dict[str, Any]) -> MideaCloudAppliance:
        sn = self._decrypt_sn(appliance.get("sn"))
        sn8 = sn[SN8_START:SN8_END] if len(sn) >= SN8_END else ""
        return MideaCloudAppliance(
            appliance_code=int(appliance["id"]),
            name=appliance["name"],
            appliance_type=int(appliance["type"], 16),
            sn=sn,
            sn8=sn8,
            model=sn8,
            model_number=appliance.get("modelNumber") or "0",
            manufacturer_code=appliance.get("enterpriseCode")
            or DEFAULT_MANUFACTURER_CODE,
            smart_product_id=appliance.get("smartProductId"),
            category=appliance.get("category"),
            online=appliance.get("onlineStatus") == ONLINE_STATUS,
        )

    def _command_data(self, appliance: MideaCloudAppliance) -> dict[str, Any]:
        return {
            "clientType": "1",
            "appId": self._app_id,
            "format": "2",
            "deviceId": self._device_id,
            "iotAppId": self._app_id,
            "applianceMFCode": appliance.manufacturer_code,
            "applianceType": f"0x{appliance.appliance_type:02X}",
            "modelNumber": appliance.model_number,
            "applianceSn": self._security.aes_encrypt_with_fixed_key(
                appliance.sn.encode("ascii"),
            ).hex(),
            "version": "0",
            # The trailing space matches the request the cloud is known to accept.
            "encryptedType ": "2",
            "applianceCode": appliance.appliance_code,
        }


def get_midea_cloud(
    cloud_name: MideaCloudName,
    session: ClientSession,
    account: str,
    password: str,
) -> MideaCloud:
    """Return the client of a Midea cloud."""
    if cloud_name is MideaCloudName.MEIJU:
        return MeijuCloud(session, account, password)
    return MSmartHomeCloud(session, account, password)
