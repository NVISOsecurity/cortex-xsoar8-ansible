"""
Support fixtures for the ``api_key`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_api_key_params   — plain builder; importable for cross-module tests
- api_key_params        — pytest fixture wrapping make_api_key_params
- make_api_key_manager  — factory fixture; call with **overrides per test
- api_key_response      — realistic XSOAR API key object (element of DATA list)

Notes
-----
Default params target ``state="present"`` with direct fields (``roles``,
``security_level``).  Tests that need filter-based params (``state="absent"``
or ``state="gathered"``) pass ``request_data={"filters": [...]}`` as an
override to ``make_api_key_manager``.  Tests that need no ``request_data``
at all (default-filter gather) pass ``request_data=None``.
"""

from __future__ import annotations

import pytest

from plugins.modules.api_key import XSOARApiKeyManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_api_key_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``api_key`` module.

    Defaults to ``state="present"`` with minimal valid direct fields so that
    ``validate_direct_fields()`` succeeds without raising ``fail_json``.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARApiKeyManager`.
    """
    params = {
        "provider": provider_params,
        "request_data": {
            "roles": ["Admin"],
            "security_level": "standard",
        },
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_key_params(provider_params):
    """
    Default params for the ``api_key`` module (``state="present"``).

    ``request_data`` contains the minimal direct fields required by
    ``validate_direct_fields()`` to succeed: ``roles`` and ``security_level``.
    """
    return make_api_key_params(provider_params)


@pytest.fixture
def make_api_key_manager(mock_connection, api_key_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_api_key_manager):
            manager = make_api_key_manager()                    # present + direct fields
            manager = make_api_key_manager(                     # filter-based absent
                request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
                state="absent",
            )
            manager = make_api_key_manager(request_data=None, state="gathered")  # no-filter gather
    """

    def _factory(**overrides):
        return build_manager(XSOARApiKeyManager, mock_connection, api_key_params, **overrides)

    return _factory


@pytest.fixture
def api_key_response():
    """
    Realistic single API key object as returned inside ``reply.DATA``.

    Use this as an element in ``{"reply": {"DATA": [api_key_response]}}`` when
    mocking the response to ``get_api_keys()``.
    """
    return {
        "id": 1,
        "name": "test-api-key",
        "roles": ["Admin"],
        "security_level": "standard",
        "expiration": 1893456000000,
        "comment": "",
    }
