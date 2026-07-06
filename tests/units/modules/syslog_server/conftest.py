"""
Support fixtures for the ``syslog_server`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_syslog_server_params   — plain builder; importable for cross-module tests via
                                ``from tests.units.modules.syslog_server.conftest
                                import make_syslog_server_params``
- syslog_server_params        — pytest fixture wrapping make_syslog_server_params
- make_syslog_server_manager  — factory fixture; call with **overrides per test
- api_syslog_server_response  — realistic XSOAR API syslog server object (raw API shape)

Notes
-----
Default params target ``state="present"`` with all required direct fields so
that ``validate_direct_fields()`` succeeds without raising ``fail_json``.
Tests that need filter-based params (``state="absent"`` or ``state="gathered"``)
pass ``request_data={"filters": [...]}`` as an override to
``make_syslog_server_manager``.
"""

from __future__ import annotations

import pytest

from plugins.modules.syslog_server import XSOARSyslogServerManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_syslog_server_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``syslog_server`` module.

    Defaults to ``state="present"`` with all required direct fields so that
    ``validate_direct_fields()`` succeeds without raising ``fail_json``.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARSyslogServerManager`.
    """
    params = {
        "provider": provider_params,
        "request_data": {
            "name": "test-syslog",
            "address": "1.2.3.4",
            "port": "514",
            "protocol": "UDP",
            "facility": "FAC_LOCAL0",
        },
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def syslog_server_params(provider_params):
    """
    Default params for the ``syslog_server`` module (``state="present"``).

    ``request_data`` contains all required direct fields so that
    ``validate_direct_fields()`` succeeds out of the box.
    """
    return make_syslog_server_params(provider_params)


@pytest.fixture
def make_syslog_server_manager(mock_connection, syslog_server_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_syslog_server_manager):
            manager = make_syslog_server_manager()                        # present + direct fields
            manager = make_syslog_server_manager(                         # filter-based gathered
                request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
                state="gathered",
            )
    """

    def _factory(**overrides):
        return build_manager(XSOARSyslogServerManager, mock_connection, syslog_server_params, **overrides)

    return _factory


@pytest.fixture
def api_syslog_server_response():
    """
    Realistic XSOAR API response for a single syslog server object (raw API shape).

    Field names match the uppercase keys returned by the real API and consumed
    by ``normalize_server()``.  Values deliberately match the defaults in
    ``syslog_server_params`` so that ``instance_needs_update`` returns False
    (no update needed) out of the box.
    """
    return {
        "SYSLOG_INTEGRATION_ID": "syslog-abc123",
        "SYSLOG_INTEGRATION_NAME": "test-syslog",
        "SYSLOG_INTEGRATION_ADDRESS": "1.2.3.4",
        "SYSLOG_INTEGRATION_PORT": 514,
        "SYSLOG_INTEGRATION_PROTOCOL": "UDP",
        "FACILITY": "FAC_LOCAL0",
        "SYSLOG_INTEGRATION_STATUS": "active",
        "SYSLOG_INTEGRATION_ERROR": None,
        "SYSLOG_INTEGRATION_CERTIFICATE_NAME": None,
        "SYSLOG_INTEGRATION_IGNORE_CERTIFICATE_ERROR": None,
    }
