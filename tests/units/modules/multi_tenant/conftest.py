"""
Support fixtures for the ``multi_tenant`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_multi_tenant_params   — plain builder; importable for cross-module tests via
                               ``from tests.units.modules.multi_tenant.conftest import make_multi_tenant_params``
- multi_tenant_params        — pytest fixture wrapping make_multi_tenant_params
- make_multi_tenant_manager  — factory fixture; call with **overrides per test
- api_tenant_response        — realistic XSOAR API response for a tenant object
"""

from __future__ import annotations

import pytest

from plugins.modules.multi_tenant import XSOARTenantManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_multi_tenant_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``multi_tenant`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARTenantManager`.
    """
    params = {
        "provider": provider_params,
        "cortex_id": None,
        "data_retention": 365,
        "initial_user": "admin@example.com",
        "tenant_id": None,
        "tenant_name": "test-tenant",
        "tenant_subdomain": "test-subdomain",
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_tenant_params(provider_params):
    """
    Default params for the ``multi_tenant`` module.

    Uses ``state="present"`` with all required fields so that
    :class:`XSOARTenantManager` initialises without performing any API calls.
    """
    return make_multi_tenant_params(provider_params)


@pytest.fixture
def make_multi_tenant_manager(mock_connection, multi_tenant_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_multi_tenant_manager):
            manager = make_multi_tenant_manager()                        # defaults
            manager = make_multi_tenant_manager(tenant_name="other")     # override
            manager = make_multi_tenant_manager(
                state="absent",
                cortex_id="cortex-abc123",
                tenant_id="tenant-abc123",
            )  # absent — supply all three identifiers to skip the API lookup in __init__
            manager = make_multi_tenant_manager(state="gathered", tenant_name=None)  # no filter
    """

    def _factory(**overrides):
        return build_manager(XSOARTenantManager, mock_connection, multi_tenant_params, **overrides)

    return _factory


@pytest.fixture
def api_tenant_response():
    """
    Realistic XSOAR API response for a single tenant object.

    Field values deliberately match the defaults in ``multi_tenant_params`` so
    that comparisons and lookups work correctly out of the box.
    """
    return {
        "cortex_id": "cortex-abc123",
        "tenant_id": "tenant-abc123",
        "tenant_name": "test-tenant",
        "tenant_subdomain": "test-subdomain",
        "data_retention": 365,
        "initial_user": "admin@example.com",
        "status": "active",
    }
