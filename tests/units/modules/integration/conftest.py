"""
Support fixtures for the ``integration`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_integration_params  — plain builder; importable for cross-module tests via
                             ``from tests.units.modules.integration.conftest import make_integration_params``
- integration_params       — pytest fixture wrapping make_integration_params
- make_integration_manager — factory fixture; call with **overrides per test
- api_integration_response — realistic XSOAR API response for an integration instance
"""

from __future__ import annotations

import pytest

from plugins.modules.integration import XSOARIntegrationManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_integration_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``integration`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARIntegrationManager`.
    """
    params = {
        "provider": provider_params,
        "name": "TestIntegration",
        "instance_id": None,
        "brand": "VirusTotal",
        "enabled": True,
        "configuration": {},
        "default_ignore": False,
        "engine": None,
        "engine_group": None,
        "incoming_mapper_id": None,
        "propagation_labels": ["all"],
        "get_available": False,
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_params(provider_params):
    """
    Default params for the ``integration`` module.

    ``engine``, ``engine_group``, and ``incoming_mapper_id`` are set to None
    to match what the API returns for unset optional fields, preventing
    spurious update detection in the "no change" test scenario.

    ``configuration`` is empty so ``_build_configuration_data`` produces []
    which matches ``api_integration_response["data"]``.
    """
    return make_integration_params(provider_params)


@pytest.fixture
def make_integration_manager(mock_connection, integration_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_integration_manager):
            manager = make_integration_manager()
            manager = make_integration_manager(name="OtherIntegration", enabled=False)
    """

    def _factory(**overrides):
        return build_manager(XSOARIntegrationManager, mock_connection, integration_params, **overrides)

    return _factory


@pytest.fixture
def api_integration_response():
    """
    Realistic XSOAR API response for a single integration instance.

    Field values match the defaults in ``integration_params``:
    - ``data`` is [] (empty configuration)
    - ``enabled`` is "true" (str, as XSOAR returns it)
    - ``engine``/``engineGroup``/``incomingMapperId`` are None
    - ``propagationLabels`` is ["all"]

    This alignment ensures ``instance_needs_update`` returns False by default,
    so tests do not trigger spurious updates unless a field is explicitly
    changed.
    """
    return {
        "id": "integration-abc123",
        "name": "TestIntegration",
        "brand": "VirusTotal",
        "enabled": "true",
        "defaultIgnore": False,
        "engine": None,
        "engineGroup": None,
        "incomingMapperId": None,
        "propagationLabels": ["all"],
        "data": [],
        "category": "Data Enrichment & Threat Intelligence",
        "version": 5,
        "modified": "2024-11-17T10:30:00.000Z",
    }
