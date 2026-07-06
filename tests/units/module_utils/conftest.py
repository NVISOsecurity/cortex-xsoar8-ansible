"""
Shared fixtures for the module_utils unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Global fixtures (``mock_module``, ``provider_params``) are inherited from
``tests/conftest.py`` via pytest's conftest discovery chain.

Contents
--------
- xsoar_connection — real :class:`XSOARConnection` with ``requests.Session``
                      mocked out
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from plugins.module_utils.xsoar import XSOARConnection


@pytest.fixture
def xsoar_connection(mock_module):
    """
    A real :class:`XSOARConnection` with ``requests.Session`` mocked out.

    ``connection.session`` is a :class:`~unittest.mock.MagicMock`.  Configure
    ``session.get.return_value`` etc. inside each test.
    """
    with patch("plugins.module_utils.xsoar.requests.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        yield XSOARConnection(mock_module)
