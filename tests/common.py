"""Midea Cloud test helpers."""

import asyncio
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from mideacloud.const import (
    CLOUDS,
    MEIJU_FIXED_KEY,
    MSMARTHOME_FIXED_IV,
    MSMARTHOME_FIXED_KEY,
    MideaCloudName,
)

from .const import (
    MEIJU_API,
    MSMARTHOME_API,
    MSMARTHOME_REGIONAL_API,
    TEST_ACCESS_TOKEN,
    TEST_LOGIN_ID,
    TEST_SESSION_IV,
    TEST_SESSION_KEY,
    TEST_UID,
)


@dataclass(frozen=True)
class Request:
    """A request sent to the mocked cloud."""

    headers: dict[str, str]
    body: dict[str, Any]


class _Response:
    def __init__(
        self,
        raw: bytes | None,
        exception: Exception | None,
        status: int,
    ) -> None:
        self._raw = raw
        self._exception = exception
        self.ok = status < HTTPStatus.BAD_REQUEST

    async def __aenter__(self) -> Self:
        # Yield like a real network round trip so concurrent requests interleave.
        await asyncio.sleep(0)
        if self._exception is not None:
            raise self._exception
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def read(self) -> bytes:
        assert self._raw is not None
        return self._raw


class MockedCloud:
    """Replies to ``ClientSession.post`` with queued per-URL responses."""

    def __init__(self) -> None:
        """Initialize the mocked cloud."""
        self._replies: dict[str, deque[_Response]] = defaultdict(deque)
        self.requests: dict[str, list[Request]] = defaultdict(list)

    def post(
        self,
        url: str,
        *,
        payload: object = None,
        body: str | None = None,
        exception: Exception | None = None,
        status: int = HTTPStatus.OK,
        repeat: int = 1,
    ) -> None:
        """Queue the reply to the next request to a URL."""
        raw = body.encode() if body is not None else json.dumps(payload).encode()
        for _ in range(repeat):
            self._replies[url].append(_Response(raw, exception, status))

    def session_post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: str,
        **_kwargs: object,
    ) -> _Response:
        """Stand in for ``ClientSession.post``."""
        assert self._replies[url], f"Unexpected request to {url}"
        self.requests[url].append(Request(dict(headers), json.loads(data)))
        return self._replies[url].popleft()


def reply(data: dict[str, Any] | None = None, code: int = 0) -> dict[str, Any]:
    """Return a cloud reply payload."""
    payload: dict[str, Any] = {"code": code, "msg": "message"}
    if data is not None:
        payload["data"] = data
    return payload


def _ascii_key(value: int) -> bytes:
    return format(value, "x").encode("ascii")


def cbc_encrypt(data: bytes, key: bytes, iv: bytes) -> str:
    """Encrypt with AES CBC and return hex."""
    return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(pad(data, 16)).hex()


def ecb_encrypt(data: bytes, key: bytes) -> str:
    """Encrypt with AES ECB and return hex."""
    return AES.new(key, AES.MODE_ECB).encrypt(pad(data, 16)).hex()


def meiju_login_reply(access_token: str = TEST_ACCESS_TOKEN) -> dict[str, Any]:
    """Return a Meiju login reply carrying the test session key."""
    return reply(
        {
            "key": ecb_encrypt(TEST_SESSION_KEY, _ascii_key(MEIJU_FIXED_KEY)),
            "mdata": {"accessToken": access_token},
        },
    )


def msmarthome_login_reply(access_token: str = TEST_ACCESS_TOKEN) -> dict[str, Any]:
    """Return a MSmartHome login reply carrying the test session key and IV."""
    digest = sha256(
        CLOUDS[MideaCloudName.MSMARTHOME].login_key.encode("ascii"),
    ).hexdigest()
    key, iv = digest[:16].encode("ascii"), digest[16:32].encode("ascii")
    return reply(
        {
            "uid": TEST_UID,
            "accessToken": cbc_encrypt(TEST_SESSION_KEY, key, iv),
            "randomData": cbc_encrypt(TEST_SESSION_IV, key, iv),
            "mdata": {"accessToken": access_token},
        },
    )


def meiju_encrypt_sn(sn: str) -> str:
    """Encrypt a serial number as the Meiju cloud lists it."""
    return ecb_encrypt(sn.encode("ascii"), TEST_SESSION_KEY)


def msmarthome_encrypt_sn(sn: str) -> str:
    """Encrypt a serial number as the MSmartHome cloud lists it."""
    return cbc_encrypt(sn.encode("ascii"), TEST_SESSION_KEY, TEST_SESSION_IV)


def msmarthome_fixed_encrypt(data: bytes) -> str:
    """Encrypt with the MSmartHome fixed key and IV."""
    return cbc_encrypt(
        data,
        _ascii_key(MSMARTHOME_FIXED_KEY),
        _ascii_key(MSMARTHOME_FIXED_IV),
    )


def mock_meiju_login(
    mocked: MockedCloud,
    access_token: str = TEST_ACCESS_TOKEN,
) -> None:
    """Mock a successful Meiju login."""
    mocked.post(
        MEIJU_API + "/v1/user/login/id/get",
        payload=reply({"loginId": TEST_LOGIN_ID}),
    )
    mocked.post(
        MEIJU_API + "/mj/user/login",
        payload=meiju_login_reply(access_token),
    )


def mock_msmarthome_login(
    mocked: MockedCloud,
    access_token: str = TEST_ACCESS_TOKEN,
) -> None:
    """Mock a successful MSmartHome login routed to the regional server."""
    mocked.post(
        MSMARTHOME_API + "/v1/unitcenter/router/user/name",
        payload=reply({"masUrl": MSMARTHOME_REGIONAL_API}),
    )
    mocked.post(
        MSMARTHOME_REGIONAL_API + "/v1/user/login/id/get",
        payload=reply({"loginId": TEST_LOGIN_ID}),
    )
    mocked.post(
        MSMARTHOME_REGIONAL_API + "/mj/user/login",
        payload=msmarthome_login_reply(access_token),
    )


def request_bodies(mocked: MockedCloud, url: str) -> list[dict[str, Any]]:
    """Return the JSON bodies posted to a URL."""
    return [request.body for request in mocked.requests[url]]


def request_headers(mocked: MockedCloud, url: str) -> list[dict[str, str]]:
    """Return the headers posted to a URL."""
    return [request.headers for request in mocked.requests[url]]
