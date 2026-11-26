"""Midea Cloud exceptions."""

# Maps a Midea cloud error code to a stable slug callers can translate. The wire
# message varies by locale and endpoint, so never match on it.
CLOUD_ERRORS: dict[int, str] = {
    1002: "cloud_error",  # missing or wrong-type request parameter
    3004: "cloud_error",  # malformed/rejected request, or endpoint disabled
    3101: "invalid_auth",  # account password is incorrect
    3102: "invalid_auth",  # account or password incorrect
    3106: "cloud_session_expired",  # login session is invalid; log in again
    3144: "cloud_session_expired",  # login session invalid (empty loginId)
    3201: "device_not_registered",  # device is bound to a different account
    3301: "invalid_cloud_server",  # invalid app key for this cloud
    7610: "account_locked",  # too many failed logins; ~5 minute lockout
    9999: "cloud_error",  # generic or transient cloud error
    40404: "cloud_error",  # the API endpoint was retired or moved
    65027: "too_many_logged_in_devices",  # too many simultaneous logins
}

LOGIN_ERROR_CODES = frozenset({3101, 3102, 3301, 7610, 65027})

# The access token expired or was revoked; a new login fixes it.
TOKEN_INVALID_CODES = frozenset({3106, 3144, 7400, 40002})

# The cloud-side Lua codec of the appliance failed on the request.
LUA_ANALYSIS_ERROR_CODE = 1014


class MideaCloudError(Exception):
    """Base exception of the Midea Cloud library."""

    translation_key = "cloud_error"


class MideaCloudConnectionError(MideaCloudError):
    """The Midea cloud could not be reached or sent an invalid reply."""

    translation_key = "cannot_connect"


class MideaCloudApiError(MideaCloudError):
    """The Midea cloud rejected a request."""

    def __init__(self, code: int, message: str) -> None:
        """Initialize with the cloud error code and message."""
        super().__init__(f"Cloud request failed with code {code}: {message}")
        self.code = code
        self.message = message
        self.translation_key = CLOUD_ERRORS.get(code, "cloud_error")


class MideaCloudAuthError(MideaCloudApiError):
    """The Midea cloud rejected the account credentials."""


class MideaCloudLuaAnalysisError(MideaCloudApiError):
    """The cloud-side Lua codec of the appliance failed on the request.

    Retrying the same request does not help: the appliance protocol does not
    support it.
    """


def cloud_api_error(code: int, message: str) -> MideaCloudApiError:
    """Return the most specific exception for a cloud error code."""
    if code in LOGIN_ERROR_CODES:
        return MideaCloudAuthError(code, message)
    return MideaCloudApiError(code, message)
