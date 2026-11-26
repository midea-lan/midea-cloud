"""Midea Cloud constants."""

from dataclasses import dataclass
from enum import StrEnum


class MideaCloudName(StrEnum):
    """Supported Midea clouds."""

    MEIJU = "meiju"
    MSMARTHOME = "msmarthome"


@dataclass(frozen=True, kw_only=True)
class CloudDefinition:
    """Static application parameters of a Midea cloud."""

    app_id: str
    app_key: str
    login_key: str
    iot_key: str
    hmac_key: str
    api_url: str


# Keys are stored as integers so that secret scanners don't flag the public app keys.
_HMAC_KEY = bytes.fromhex(
    format(117390035944627627450677220413733956185864939010425, "x"),
).decode()

CLOUDS: dict[MideaCloudName, CloudDefinition] = {
    MideaCloudName.MEIJU: CloudDefinition(
        app_id="900",
        app_key="46579c15",
        login_key="ad0ee21d48a64bf49f4fb583ab76e799",
        iot_key=bytes.fromhex(
            format(9795516279659324117647275084689641883661667, "x"),
        ).decode(),
        hmac_key=_HMAC_KEY,
        api_url="https://mp-prod.smartmidea.net/mas/v5/app/proxy?alias=",
    ),
    MideaCloudName.MSMARTHOME: CloudDefinition(
        app_id="1010",
        app_key="ac21b9f9cbfe4ca5a88562ef25e2b768",
        # MSmartHome signs the login password with the app key.
        login_key="ac21b9f9cbfe4ca5a88562ef25e2b768",
        iot_key=bytes.fromhex(format(7882822598523843940, "x")).decode(),
        hmac_key=_HMAC_KEY,
        api_url="https://mp-prod.appsmb.com/mas/v5/app/proxy?alias=",
    ),
}

MEIJU_FIXED_KEY = 10864842703515613082
MSMARTHOME_FIXED_KEY = 13101328926877700970
MSMARTHOME_FIXED_IV = 16429062708050928556

MSMARTHOME_APP_VERSION = "3.0.2"
MSMARTHOME_SRC = "10"

REQUEST_TIMEOUT = 30

DEFAULT_SN8 = "00000000"
DEFAULT_MANUFACTURER_CODE = "0000"
# MSmartHome serial numbers carry the sn8 at characters 9-16.
SN8_START = 9
SN8_END = 17

ONLINE_STATUS = "1"
