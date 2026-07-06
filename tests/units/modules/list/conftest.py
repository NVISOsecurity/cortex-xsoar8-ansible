"""
Support fixtures for the ``list`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_list_params  — plain builder; importable for cross-module tests via
                      ``from tests.units.modules.list.conftest import make_list_params``
- list_params       — pytest fixture wrapping make_list_params
- make_list_manager — factory fixture; call with **overrides per test
- api_list_response — realistic XSOAR API response for a list object
"""

from __future__ import annotations

import pytest

from plugins.modules.list import XSOARListManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_list_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``list`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARListManager`.
    """
    params = {
        "provider": provider_params,
        "name": "test-list",
        "content": "line1\nline2",
        "content_type": "Text",
        "description": "A test list",
        "json_content": None,
        "propagation_labels": [],
        "edit_roles": [],
        "read_roles": [],
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def list_params(provider_params):
    """
    Default params for the ``list`` module.

    ``content_type`` uses "Text" — a valid module choice — so that
    ``instance_needs_update`` comparisons against ``api_list_response``
    return False by default (no spurious update).
    """
    return make_list_params(provider_params)


@pytest.fixture
def make_list_manager(mock_connection, list_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_list_manager):
            manager = make_list_manager()                    # defaults
            manager = make_list_manager(name="other-list")   # override one param
    """

    def _factory(**overrides):
        return build_manager(XSOARListManager, mock_connection, list_params, **overrides)

    return _factory


@pytest.fixture
def api_list_response():
    """
    Realistic XSOAR API response for a single list object.

    Field values deliberately match the defaults in ``list_params`` so that
    ``instance_needs_update`` returns False (no update needed) out of the box.
    """
    return {
        "id": "list-abc123",
        "name": "test-list",
        "data": "line1\nline2",
        "type": "Text",
        "description": "A test list",
        "propagationLabels": [],
        "roles": [],
        "xsoarReadOnlyRoles": [],
        "version": 1,
    }
