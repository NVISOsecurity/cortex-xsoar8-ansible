"""
Support fixtures for the ``server_settings`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_server_settings_params   — plain builder; importable for cross-module tests via
                                   ``from tests.units.modules.server_settings.conftest
                                   import make_server_settings_params``
- server_settings_params        — pytest fixture wrapping make_server_settings_params
- make_server_settings_manager  — factory fixture; call with **overrides per test
- api_server_settings_response  — realistic XSOAR API response for the system/config endpoint
"""

from __future__ import annotations

import pytest

from plugins.modules.server_settings import XSOARServerSettingsManager
from tests.conftest import build_manager


def make_server_settings_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``server_settings`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARServerSettingsManager`.
    """
    params = {
        "provider": provider_params,
        "delete_settings": ["http.proxy", "mail.transport"],
        "server_settings": {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
        },
        "state": "present",
    }
    params.update(overrides)
    return params


@pytest.fixture
def server_settings_params(provider_params):
    """
    Default params for the ``server_settings`` module.

    Uses ``state="present"`` with a pair of settings keys so that
    :class:`XSOARServerSettingsManager` initialises without performing any API calls.
    """
    return make_server_settings_params(provider_params)


@pytest.fixture
def make_server_settings_manager(mock_connection, server_settings_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_server_settings_manager):
            manager = make_server_settings_manager()                             # defaults
            manager = make_server_settings_manager(state="absent")               # override one param
            manager = make_server_settings_manager(server_settings={"k": "v"})   # custom settings
    """

    def _factory(**overrides):
        return build_manager(XSOARServerSettingsManager, mock_connection, server_settings_params, **overrides)

    return _factory


@pytest.fixture
def api_server_settings_response():
    """
    Realistic GET /xsoar/system/config response payload.

    Includes the ``versn`` field that the manager must strip before returning
    settings to callers.  Values match the defaults in ``server_settings_params``
    so that ``instance_needs_update`` comparisons return False out of the box.
    """
    return {
        "sysConf": {
            "versn": 7,
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
            "mail.from": "xsoar@example.com",
        }
    }
