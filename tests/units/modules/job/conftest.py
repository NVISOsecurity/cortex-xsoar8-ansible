"""
Support fixtures for the ``job`` module unit tests.

Auto-discovered by pytest as conftest.py — all fixtures are available to
tests in this directory without explicit imports.

Contents
--------
- make_job_params   — plain builder; importable for cross-module tests via
                      ``from tests.units.modules.job.conftest import make_job_params``
- job_params        — pytest fixture wrapping make_job_params
- make_job_manager  — factory fixture; call with **overrides per test
- api_job_response  — realistic XSOAR API response for a job object
"""

from __future__ import annotations

import pytest

from plugins.modules.job import XSOARJobManager
from tests.conftest import build_manager

# ---------------------------------------------------------------------------
# Plain builder — importable without pytest
# ---------------------------------------------------------------------------


def make_job_params(provider_params, **overrides):
    """
    Return a complete params dict for the ``job`` module.

    Usable outside of pytest (e.g. in cross-module test files) by importing
    this function directly and passing a plain provider dict.

    :param provider_params: Provider connection dict.
    :param overrides: Key/value pairs to override in the default params.
    :returns: A complete params dict ready to pass to :class:`XSOARJobManager`.
    """
    params = {
        "provider": provider_params,
        "active": True,
        "close_previous_run": False,
        "cron": "0 6 * * *",
        "custom_fields": {},
        "end_date": None,
        "ending_type": "never",
        "name": "test-job",
        "notify_owner": False,
        "owner": "",
        "playbook_id": "test-playbook",
        "query": None,
        "severity": 0,
        "should_trigger_new": False,
        "start_date": "now",
        "state": "present",
        "tags": [],
        "type": "Unclassified",
    }
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def job_params(provider_params):
    """
    Default params for the ``job`` module.

    Uses ``state="present"`` so that :class:`XSOARJobManager` runs its date
    normalisation and builds ``fields_to_compare`` during ``__init__``.
    """
    return make_job_params(provider_params)


@pytest.fixture
def make_job_manager(mock_connection, job_params):
    """
    Factory fixture.

    Usage::

        def test_something(make_job_manager):
            manager = make_job_manager()                      # defaults
            manager = make_job_manager(name="other-job")      # override one param
            manager = make_job_manager(state="absent")        # absent state
    """

    def _factory(**overrides):
        return build_manager(XSOARJobManager, mock_connection, job_params, **overrides)

    return _factory


@pytest.fixture
def api_job_response():
    """
    Realistic XSOAR API response for a single job object.

    Field values deliberately match the defaults in ``job_params`` so that
    ``instance_needs_update`` returns False (no update needed) out of the box.
    The compared fields are: ``cron``, ``CustomFields``, ``notifyOwner``,
    ``owner``, ``playbookId``, ``severity``, ``shouldTriggerNew``, ``tags``,
    ``type``.
    """
    return {
        "id": "job-abc123",
        "name": "test-job",
        "rawName": "test-job",
        "cron": "0 6 * * *",
        "CustomFields": {"isactive": "true"},
        "closePrevRun": False,
        "endingDate": "2026-05-15T06:00:00.000000Z",
        "endingType": "never",
        "notifyOwner": False,
        "owner": "",
        "playbookId": "test-playbook",
        "rawType": "Unclassified",
        "severity": 0,
        "shouldTriggerNew": False,
        "startDate": "2026-05-15T06:00:00.000000Z",
        "tags": [],
        "type": "Unclassified",
        "version": 1,
    }
