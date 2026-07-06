"""
Support fixtures for the ``pre_process_rule`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_pre_process_rule_params   — plain builder; importable for cross-module tests via
                                   ``from tests.units.modules.pre_process_rule.conftest
                                   import make_pre_process_rule_params``
- pre_process_rule_params        — pytest fixture wrapping make_pre_process_rule_params
- make_pre_process_rule_manager  — factory fixture; call with **overrides per test
- api_pre_process_rule_response  — realistic XSOAR API response for a pre-process rule object
"""

from __future__ import annotations

import pytest

from plugins.modules.pre_process_rule import XSOARPreProcessRuleManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_pre_process_rule_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``pre_process_rule`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARPreProcessRuleManager`.
    """
    params = {
        "provider": provider_params,
        "action": "link",
        "enabled": True,
        "name": "test-rule",
        "propagation_labels": [],
        "script_id": None,
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pre_process_rule_params(provider_params):
    """
    Default params for the ``pre_process_rule`` module.

    ``action`` uses ``"link"`` — a valid module choice — so that
    ``instance_needs_update`` comparisons against ``api_pre_process_rule_response``
    return False by default (no spurious update).
    """
    return make_pre_process_rule_params(provider_params)


@pytest.fixture
def make_pre_process_rule_manager(mock_connection, pre_process_rule_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_pre_process_rule_manager):
            manager = make_pre_process_rule_manager()                       # defaults
            manager = make_pre_process_rule_manager(action="drop")          # override one param
            manager = make_pre_process_rule_manager(state="absent")         # absent state
    """

    def _factory(**overrides):
        return build_manager(XSOARPreProcessRuleManager, mock_connection, pre_process_rule_params, **overrides)

    return _factory


@pytest.fixture
def api_pre_process_rule_response():
    """
    Realistic XSOAR API response for a single pre-process rule object.

    Field values deliberately match the defaults in ``pre_process_rule_params``
    so that ``instance_needs_update`` returns False (no update needed) out of
    the box.  The compared fields are: ``action``, ``enabled``,
    ``propagationLabels``, ``scriptID``.
    """
    return {
        "id": "rule-abc123",
        "name": "test-rule",
        "action": "link",
        "commitMessage": "Preprocess rule edited",
        "enabled": True,
        "existingEventsFilters": [],
        "linkTo": "oldest",
        "newEventFilters": [],
        "period": {"fromValue": 30, "by": "days"},
        "propagationLabels": [],
        "scriptID": None,
        "searchClosed": False,
        "shouldCommit": True,
        "shouldPublish": True,
        "version": 1,
    }
