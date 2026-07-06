"""
Support fixtures for the ``credential`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_credential_params   — plain builder; importable for cross-module tests via
                             ``from tests.units.modules.credential.conftest import make_credential_params``
- credential_params        — pytest fixture wrapping make_credential_params
- make_credential_manager  — factory fixture; call with **overrides per test
- api_credential_response  — realistic XSOAR API response for a credential object
"""

from __future__ import annotations

import pytest

from plugins.modules.credential import XSOARCredentialManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_credential_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``credential`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARCredentialManager`.
    """
    params = {
        "provider": provider_params,
        "certificate": None,
        "name": "test-credential",
        "password": None,
        "username": "test-user",
        "workgroup": None,
        "state": "present",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def credential_params(provider_params):
    """
    Default params for the ``credential`` module.

    ``username`` is set to ``"test-user"`` and all other optional secrets
    default to ``None`` so that ``instance_needs_update`` comparisons against
    ``api_credential_response`` return False by default (no spurious update).
    The compared fields are ``user`` and ``workgroup``.
    """
    return make_credential_params(provider_params)


@pytest.fixture
def make_credential_manager(mock_connection, credential_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_credential_manager):
            manager = make_credential_manager()                         # defaults
            manager = make_credential_manager(username="other-user")    # override one param
            manager = make_credential_manager(state="absent")           # absent state
    """

    def _factory(**overrides):
        return build_manager(XSOARCredentialManager, mock_connection, credential_params, **overrides)

    return _factory


@pytest.fixture
def api_credential_response():
    """
    Realistic XSOAR API response for a single credential object.

    Field values deliberately match the defaults in ``credential_params`` so
    that ``instance_needs_update`` returns False (no update needed) out of
    the box.  The compared fields are: ``user``, ``workgroup``.
    """
    return {
        "id": "cred-abc123",
        "name": "test-credential",
        "user": "test-user",
        "workgroup": None,
        "hasPassword": False,
        "hasCertificate": False,
        "sshkey": None,
        "password": None,
        "version": 1,
    }
