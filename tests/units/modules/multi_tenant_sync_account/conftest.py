"""
Support fixtures for the ``multi_tenant_sync_account`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_multi_tenant_sync_account_params   — plain builder; importable for cross-module tests via
                                            ``from tests.units.modules.multi_tenant_sync_account.conftest
                                            import make_multi_tenant_sync_account_params``
- multi_tenant_sync_account_params        — pytest fixture wrapping make_multi_tenant_sync_account_params
- make_multi_tenant_sync_account_manager  — factory fixture; call with **overrides per test
- account_diff_response                   — realistic XSOAR content diff payload for sync endpoints
"""

from __future__ import annotations

import pytest

from plugins.modules.multi_tenant_sync_account import XSOARSyncAccountManager
from tests.conftest import build_manager


def make_multi_tenant_sync_account_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``multi_tenant_sync_account`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARSyncAccountManager`.
    """
    params = {
        "provider": provider_params,
        "accounts": ["tenant-a", "tenant-b"],
        "all_accounts": False,
        "items": ["BlockedIPs", "AllowedDomains"],
        "all_items": False,
        "state": "present",
    }
    params.update(overrides)
    return params


@pytest.fixture
def multi_tenant_sync_account_params(provider_params):
    """
    Default params for the ``multi_tenant_sync_account`` module.

    Uses ``state="present"`` with explicit account and item lists so that
    :class:`XSOARSyncAccountManager` initialises without performing any API calls.
    """
    return make_multi_tenant_sync_account_params(provider_params)


@pytest.fixture
def make_multi_tenant_sync_account_manager(mock_connection, multi_tenant_sync_account_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_multi_tenant_sync_account_manager):
            manager = make_multi_tenant_sync_account_manager()                     # defaults
            manager = make_multi_tenant_sync_account_manager(all_accounts=True)    # override one param
            manager = make_multi_tenant_sync_account_manager(state="gathered")     # gathered state
    """

    def _factory(**overrides):
        return build_manager(
            XSOARSyncAccountManager,
            mock_connection,
            multi_tenant_sync_account_params,
            **overrides,
        )

    return _factory


@pytest.fixture
def account_diff_response():
    """
    Realistic content diff payload returned by the per-account diff endpoint.

    Field values cover all three action groups (``add``, ``override``, ``remove``)
    so individual tests can slice the fixture as needed.
    """
    return {
        "add": {
            "List": [
                {"id": "list-1", "name": "BlockedIPs", "type": "List"},
                {"id": "list-2", "name": "AllowedDomains", "type": "List"},
            ]
        },
        "override": {
            "Playbook": [
                {"id": "pb-1", "name": "AlertPlaybook", "type": "Playbook"},
            ]
        },
        "remove": {},
    }
