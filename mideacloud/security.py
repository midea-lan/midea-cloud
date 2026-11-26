"""Midea Cloud request signing and encryption."""

import hmac
from hashlib import md5, sha256

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from .const import MEIJU_FIXED_KEY, MSMARTHOME_FIXED_IV, MSMARTHOME_FIXED_KEY

_KEY_SPLIT = 16
_IV_END = 32


def _int_to_ascii_key(value: int) -> bytes:
    return format(value, "x").encode("ascii")


class CloudSecurity:
    """Signing and encryption shared by the Midea clouds."""

    def __init__(
        self,
        login_key: str,
        iot_key: str,
        hmac_key: str,
        fixed_key: bytes,
        fixed_iv: bytes | None = None,
    ) -> None:
        """Initialize the cloud security."""
        self._login_key = login_key
        self._iot_key = iot_key
        self._hmac_key = hmac_key
        self._fixed_key = fixed_key
        self._fixed_iv = fixed_iv
        self._aes_key: bytes | None = None
        self._aes_iv: bytes | None = None

    @staticmethod
    def get_device_id(account: str) -> str:
        """Return the client device id the cloud expects for an account."""
        return md5(f"Hello, {account}!".encode("ascii")).hexdigest()[:16]  # noqa: S324

    def sign(self, data: str, random: str) -> str:
        """Sign a request body."""
        msg = self._iot_key + data + random
        return hmac.new(
            self._hmac_key.encode("ascii"),
            msg.encode("ascii"),
            sha256,
        ).hexdigest()

    def encrypt_password(self, login_id: str, password: str) -> str:
        """Hash the password for the login request."""
        password_hash = sha256(password.encode("ascii")).hexdigest()
        login_hash = login_id + password_hash + self._login_key
        return sha256(login_hash.encode("ascii")).hexdigest()

    def encrypt_iam_password(self, login_id: str, password: str) -> str:
        """Hash the password for the IAM part of the login request."""
        raise NotImplementedError

    @staticmethod
    def _double_md5(password: str) -> str:
        first = md5(password.encode("ascii")).hexdigest()  # noqa: S324
        return md5(first.encode("ascii")).hexdigest()  # noqa: S324

    def set_aes_keys(self, key: bytes, iv: bytes | None) -> None:
        """Set the session AES key and IV."""
        self._aes_key = key
        self._aes_iv = iv

    def aes_decrypt(self, data: bytes) -> str:
        """Decrypt with the session key."""
        return self._decrypt(data, self._session_key(), self._aes_iv)

    def aes_encrypt_with_fixed_key(self, data: bytes) -> bytes:
        """Encrypt with the cloud fixed key."""
        return self._encrypt(data, self._fixed_key, self._fixed_iv)

    def aes_decrypt_with_fixed_key(self, data: bytes) -> str:
        """Decrypt with the cloud fixed key."""
        return self._decrypt(data, self._fixed_key, self._fixed_iv)

    def _session_key(self) -> bytes:
        if self._aes_key is None:
            raise ValueError("No session key: log in first")
        return self._aes_key

    @staticmethod
    def _encrypt(data: bytes, key: bytes, iv: bytes | None) -> bytes:
        padded = pad(data, AES.block_size)
        if iv is None:
            return AES.new(key, AES.MODE_ECB).encrypt(padded)
        return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(padded)

    @staticmethod
    def _decrypt(data: bytes, key: bytes, iv: bytes | None) -> str:
        if iv is None:
            decrypted = AES.new(key, AES.MODE_ECB).decrypt(data)
        else:
            decrypted = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(data)
        return unpad(decrypted, AES.block_size).decode()


class MeijuCloudSecurity(CloudSecurity):
    """Meiju cloud security."""

    def __init__(self, login_key: str, iot_key: str, hmac_key: str) -> None:
        """Initialize the Meiju cloud security."""
        super().__init__(
            login_key,
            iot_key,
            hmac_key,
            _int_to_ascii_key(MEIJU_FIXED_KEY),
        )

    def encrypt_iam_password(self, login_id: str, password: str) -> str:  # noqa: ARG002
        """Hash the password for the IAM part of the login request."""
        return self._double_md5(password)


class MSmartCloudSecurity(CloudSecurity):
    """MSmartHome cloud security."""

    def __init__(self, login_key: str, iot_key: str, hmac_key: str) -> None:
        """Initialize the MSmartHome cloud security."""
        super().__init__(
            login_key,
            iot_key,
            hmac_key,
            _int_to_ascii_key(MSMARTHOME_FIXED_KEY),
            _int_to_ascii_key(MSMARTHOME_FIXED_IV),
        )

    def encrypt_iam_password(self, login_id: str, password: str) -> str:
        """Hash the password for the IAM part of the login request."""
        login_hash = login_id + self._double_md5(password) + self._login_key
        return sha256(login_hash.encode("ascii")).hexdigest()

    def set_encrypted_aes_keys(self, encrypted_key: str, encrypted_iv: str) -> None:
        """Set the session AES key and IV from their encrypted login values."""
        key_digest = sha256(self._login_key.encode("ascii")).hexdigest()
        tmp_key = key_digest[:_KEY_SPLIT].encode("ascii")
        tmp_iv = key_digest[_KEY_SPLIT:_IV_END].encode("ascii")
        self.set_aes_keys(
            self._decrypt(bytes.fromhex(encrypted_key), tmp_key, tmp_iv).encode(
                "ascii",
            ),
            self._decrypt(bytes.fromhex(encrypted_iv), tmp_key, tmp_iv).encode(
                "ascii",
            ),
        )
