"""Midea Cloud security tests."""

import pytest

from mideacloud.const import CLOUDS, MideaCloudName
from mideacloud.security import (
    CloudSecurity,
    MeijuCloudSecurity,
    MSmartCloudSecurity,
)


def test_device_id() -> None:
    """Test the device id is derived from the account."""
    assert CloudSecurity.get_device_id("user@example.com") == "d4fcee355a8b22d6"


@pytest.mark.parametrize(
    ("cloud_name", "security_class"),
    [
        pytest.param(MideaCloudName.MEIJU, MeijuCloudSecurity, id="meiju_ecb"),
        pytest.param(MideaCloudName.MSMARTHOME, MSmartCloudSecurity, id="msmart_cbc"),
    ],
)
def test_fixed_key_round_trip(
    cloud_name: MideaCloudName,
    security_class: type[MeijuCloudSecurity] | type[MSmartCloudSecurity],
) -> None:
    """Test data encrypted with the fixed key decrypts back."""
    definition = CLOUDS[cloud_name]
    security = security_class(
        definition.login_key,
        definition.iot_key,
        definition.hmac_key,
    )

    encrypted = security.aes_encrypt_with_fixed_key(b"serial-number")

    assert security.aes_decrypt_with_fixed_key(encrypted) == "serial-number"


def test_session_key_required() -> None:
    """Test decrypting with the session key before login fails."""
    definition = CLOUDS[MideaCloudName.MSMARTHOME]
    security = MSmartCloudSecurity(
        definition.login_key,
        definition.iot_key,
        definition.hmac_key,
    )
    with pytest.raises(ValueError, match="log in first"):
        security.aes_decrypt(bytes(16))


def test_base_iam_password_not_implemented() -> None:
    """Test the base security has no IAM password scheme."""
    security = CloudSecurity("login", "iot", "hmac", b"0123456789abcdef")
    with pytest.raises(NotImplementedError):
        security.encrypt_iam_password("login-id", "password")
