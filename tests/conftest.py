"""Midea Cloud test fixtures."""

from unittest.mock import Mock

import pytest
from aiohttp import ClientSession

from mideacloud import MeijuCloud, MSmartHomeCloud

from .common import MockedCloud
from .const import TEST_ACCOUNT, TEST_PASSWORD


@pytest.fixture
def mocked() -> MockedCloud:
    """Return the mocked Midea cloud."""
    return MockedCloud()


@pytest.fixture
def session(mocked: MockedCloud) -> Mock:
    """Return an aiohttp session posting to the mocked cloud."""
    return Mock(spec=ClientSession, post=mocked.session_post)


@pytest.fixture
def meiju(session: Mock) -> MeijuCloud:
    """Return a Meiju cloud client."""
    return MeijuCloud(session, TEST_ACCOUNT, TEST_PASSWORD)


@pytest.fixture
def msmarthome(session: Mock) -> MSmartHomeCloud:
    """Return a MSmartHome cloud client."""
    return MSmartHomeCloud(session, TEST_ACCOUNT, TEST_PASSWORD)
