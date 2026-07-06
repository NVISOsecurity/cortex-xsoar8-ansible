"""
Shared pytest fixtures for the cortex.xsoar8 Ansible collection unit tests.

Structure
---------
1. Helpers (importable classes, not fixtures)
   - AnsibleModuleFail  — exception raised by mock fail_json(); import via
                           ``from tests.conftest import AnsibleModuleFail``.
   - AnsibleModuleExit  — exception raised by mock exit_json(); same import.
   With tests/__init__.py present, pytest loads this file as ``tests.conftest``
   so the import above references the same class object — no double-load.

2. Core fixtures
   - provider_params    — minimal valid provider dict
   - mock_module        — MagicMock AnsibleModule; fail_json raises AnsibleModuleFail,
                           exit_json raises AnsibleModuleExit.
   - mock_connection    — MagicMock XSOARConnection wrapping mock_module.

3. Shared helpers
   - build_manager — builds any manager class from a mock connection and
                          a params dict with optional overrides. Used by all
                          per-module support files so the logic is not repeated.

Module-specific fixtures (params, manager factories, API responses) live in
per-module conftest files under ``tests/units/modules/<module>/``
e.g. ``tests/units/modules/list/conftest.py``
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1. Helpers
# ---------------------------------------------------------------------------


class AnsibleModuleFail(Exception):
    """Raised when module.fail_json() is called."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super().__init__(kwargs.get("msg", str(kwargs)))


class AnsibleModuleExit(Exception):
    """Raised when module.exit_json() is called."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super().__init__(str(kwargs))


# ---------------------------------------------------------------------------
# 2. Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider_params():
    """Minimal valid provider dictionary accepted by XSOARConnection."""
    return {
        "server": "https://api-test.xdr.paloaltonetworks.com",
        "api_key": "test-api-key-value",
        "api_key_id": "42",
        "security_level": "standard",
        "verify_ssl": True,
        "timeout": 30,
    }


@pytest.fixture
def mock_module(provider_params, check_mode=False):
    """
    A MagicMock that behaves like AnsibleModule for testing purposes.

    - ``params`` is pre-populated with provider defaults.
    - ``check_mode`` defaults to False.
    - ``fail_json`` raises ``AnsibleModuleFail`` so tests can assert on it.
    - ``exit_json`` raises ``AnsibleModuleExit`` so tests can assert on it.
    - Calling the fixture like a factory (``mock_module(check_mode=True)``) returns
      a fresh, fully configured mock with the requested ``check_mode`` value.
    """

    def _build_module(*, check_mode=False):
        m = MagicMock()
        m.params = {"provider": provider_params}
        m.check_mode = check_mode
        m.fail_json.side_effect = lambda **kw: (_ for _ in ()).throw(AnsibleModuleFail(**kw))
        m.exit_json.side_effect = lambda **kw: (_ for _ in ()).throw(AnsibleModuleExit(**kw))
        return m

    module = _build_module(check_mode=check_mode)
    # Allow tests to call mock_module(check_mode=True) as a factory.
    # MagicMock.side_effect (not __call__.side_effect) is what intercepts calls
    # to the mock instance itself; __call__ on a MagicMock is a bound method and
    # does not expose .side_effect.
    module.side_effect = lambda *args, **kwargs: _build_module(check_mode=kwargs.get("check_mode", False))
    return module


@pytest.fixture
def mock_connection(mock_module):
    """
    A MagicMock that behaves like XSOARConnection.

    - ``module`` points to the shared mock_module fixture.
    - ``request`` is a plain MagicMock; configure its return_value or
      side_effect inside each individual test.
    """
    connection = MagicMock()
    connection.module = mock_module
    return connection


# ---------------------------------------------------------------------------
# 3. Shared helpers
# ---------------------------------------------------------------------------


def build_manager(manager_cls, mock_connection, base_params, **overrides):
    """
    Build a manager instance with a mock connection and merged params.

    Used by every per-module conftest so the construction logic lives
    in exactly one place.  Not a fixture — call it directly.

    :param manager_cls: The manager class to instantiate.
    :param mock_connection: A MagicMock connection whose ``module.params`` will
        be set to the merged params dict.
    :param base_params: Default params dict (will be deep-copied).
    :param overrides: Key/value pairs to override on top of ``base_params``.
    :returns: An instance of ``manager_cls`` connected to ``mock_connection``.
    """
    params = copy.deepcopy(base_params)
    params.update(overrides)
    mock_connection.module.params = params
    return manager_cls(mock_connection)
