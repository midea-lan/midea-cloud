"""Midea Cloud version tests."""

from importlib.metadata import version

from mideacloud.version import __version__


def test_version_matches_package_metadata() -> None:
    """Test the module version is the one published in the package metadata."""
    assert __version__ == version("midea-cloud")
