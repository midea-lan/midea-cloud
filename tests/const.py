"""Midea Cloud test constants."""

from mideacloud import MideaCloudAppliance
from mideacloud.const import CLOUDS, MideaCloudName

TEST_ACCOUNT = "user@example.com"
TEST_PASSWORD = "secret"
TEST_LOGIN_ID = "login-id"
TEST_ACCESS_TOKEN = "access-token"
TEST_NEW_ACCESS_TOKEN = "new-access-token"
TEST_UID = "uid-1"
TEST_SESSION_KEY = b"0123456789abcdef"
TEST_SESSION_IV = b"fedcba9876543210"
TEST_SN = "000000P0000000Q1F0C9D0000000000"
TEST_SN8 = "00000Q1F"
TEST_APPLIANCE_CODE = 123456789
TEST_HOME_ID = 42

MEIJU_API = CLOUDS[MideaCloudName.MEIJU].api_url
MSMARTHOME_API = CLOUDS[MideaCloudName.MSMARTHOME].api_url
MSMARTHOME_REGIONAL_API = "https://eu.example.com/mas/v5/app/proxy?alias="

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
