"""Midea Cloud test constants."""

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
