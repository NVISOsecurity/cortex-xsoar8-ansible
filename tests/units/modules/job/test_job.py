"""
Unit tests for plugins/modules/job.py — XSOARJobManager and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.job import ensure_absent, ensure_present, gather_jobs
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARJobManager.get_jobs
# ===========================================================================


class TestGetJobs:
    def test_returns_jobs_from_data_key(self, make_job_manager, api_job_response):
        """
        API wraps results in a dict with a ``data`` key — verify extraction.
        """
        manager = make_job_manager()
        manager.connection.request.return_value = {"data": [api_job_response]}

        result = manager.get_jobs()

        assert result == [api_job_response]
        manager.connection.request.assert_called_once_with(
            "POST",
            "/xsoar/public/v1/jobs/search",
            data={},
        )

    def test_returns_empty_list_when_data_key_is_absent(self, make_job_manager):
        """
        A dict response without a ``data`` key should yield an empty list.
        """
        manager = make_job_manager()
        manager.connection.request.return_value = {}

        assert manager.get_jobs() == []

    def test_returns_empty_list_when_response_is_not_dict(self, make_job_manager):
        """
        Non-dict responses (e.g. ``None``, ``[]``) should yield an empty list.
        """
        manager = make_job_manager()
        manager.connection.request.return_value = []

        assert manager.get_jobs() == []

    def test_passes_query_in_request_body(self, make_job_manager, api_job_response):
        """
        When ``query`` is provided it must be sent inside the request payload.
        """
        manager = make_job_manager()
        manager.connection.request.return_value = {"data": [api_job_response]}

        manager.get_jobs(query='name:"test-job"')

        manager.connection.request.assert_called_once_with(
            "POST",
            "/xsoar/public/v1/jobs/search",
            data={"query": 'name:"test-job"'},
        )

    def test_calls_fail_json_on_request_failure(self, make_job_manager):
        """
        An :class:`XSOARAPIError` from the connection must surface as
        ``fail_json``, which in tests raises :class:`AnsibleModuleFail`.
        """
        manager = make_job_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(AnsibleModuleFail, match="Failed to retrieve Jobs"):
            manager.get_jobs()


# ===========================================================================
# XSOARJobManager.get_job_by_name
# ===========================================================================


class TestGetJobByName:
    def test_returns_matching_job(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = {"data": [api_job_response]}

        result = manager.get_job_by_name("test-job")

        assert result == api_job_response

    def test_uses_name_query_syntax(self, make_job_manager, api_job_response):
        """
        The search query must use the ``name:"<name>"`` syntax expected by XSOAR.
        """
        manager = make_job_manager()
        manager.connection.request.return_value = {"data": [api_job_response]}

        manager.get_job_by_name("test-job")

        _, _, kwargs = manager.connection.request.mock_calls[0]
        assert kwargs["data"]["query"] == 'name:"test-job"'

    def test_returns_none_when_not_found(self, make_job_manager):
        manager = make_job_manager()
        manager.connection.request.return_value = {"data": []}

        assert manager.get_job_by_name("test-job") is None

    def test_returns_none_on_empty_response(self, make_job_manager):
        manager = make_job_manager()
        manager.connection.request.return_value = {}

        assert manager.get_job_by_name("test-job") is None


# ===========================================================================
# XSOARJobManager.build_job_data
# ===========================================================================


class TestBuildJobData:
    def test_create_payload_contains_required_fields(self, make_job_manager):
        """
        ``build_job_data()`` with no arguments produces a create payload with
        all fields derived from module params.
        """
        manager = make_job_manager()

        payload = manager.build_job_data()

        assert payload["name"] == "test-job"
        assert payload["cron"] == "0 6 * * *"
        assert payload["playbookId"] == "test-playbook"
        assert payload["type"] == "Unclassified"
        assert not payload["closePrevRun"]
        assert not payload["shouldTriggerNew"]
        assert not payload["notifyOwner"]
        assert payload["owner"] == ""
        assert payload["severity"] == 0
        assert payload["tags"] == []

    @pytest.mark.parametrize(
        "active, custom_fields, expected_custom_fields",
        [
            (True, {}, {"isactive": "true"}),
            (False, {"incident_type": "phishing"}, {"isactive": "false", "incident_type": "phishing"}),
        ],
    )
    def test_create_payload_custom_fields(self, make_job_manager, active, custom_fields, expected_custom_fields):
        """
        ``CustomFields["isactive"]`` reflects the ``active`` param (``"true"``/``"false"``).
        Caller-supplied ``custom_fields`` must also appear in the payload alongside
        the ``isactive`` key injected by the module.
        """
        manager = make_job_manager(active=active, custom_fields=custom_fields)

        payload = manager.build_job_data()

        assert payload["CustomFields"] == expected_custom_fields

    def test_update_payload(self, make_job_manager, api_job_response):
        """
        Verify the core structure of the update payload built from ``raw_job_data``:

        - ``version`` is forced to ``-1`` and the existing ``id`` is preserved.
        - ``cron`` from params overrides the API value.
        - ``custom_fields`` are merged with whatever the existing job already
          has, including the ``isactive`` key injected by the module.
        """
        manager = make_job_manager(cron="30 8 * * *", custom_fields={"extra_key": "extra_val"})
        existing = {**api_job_response, "CustomFields": {"isactive": "true", "old_key": "old_val"}}
        payload = manager.build_job_data(raw_job_data=existing)

        assert payload["version"] == -1
        assert payload["id"] == "job-abc123"
        assert payload["cron"] == "30 8 * * *"
        assert payload["CustomFields"]["old_key"] == "old_val"
        assert payload["CustomFields"]["extra_key"] == "extra_val"
        assert payload["CustomFields"]["isactive"] == "true"

    def test_update_payload_cron_falls_back_to_existing_when_none(self, make_job_manager, api_job_response):
        """
        When ``cron`` is ``None`` on the manager, ``build_job_data`` must keep
        the cron value already present in the existing job dict.
        """
        manager = make_job_manager()
        manager.cron = None

        payload = manager.build_job_data(raw_job_data=api_job_response)

        assert payload["cron"] == api_job_response["cron"]

    def test_update_payload_does_not_mutate_input(self, make_job_manager, api_job_response):
        """
        ``build_job_data`` must not mutate the ``raw_job_data`` dict that was
        passed in — the caller still needs the original.
        """
        manager = make_job_manager()
        original_version = api_job_response["version"]

        manager.build_job_data(raw_job_data=api_job_response)

        assert api_job_response["version"] == original_version


# ===========================================================================
# XSOARJobManager.create_job
# ===========================================================================


class TestCreateJob:
    def test_posts_to_correct_endpoint(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response

        job_data = manager.build_job_data()
        result = manager.create_job(job_data)

        assert result == api_job_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/public/v1/jobs"

    def test_sends_job_data_as_payload(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response

        job_data = manager.build_job_data()
        manager.create_job(job_data)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["name"] == "test-job"
        assert payload["playbookId"] == "test-playbook"

    def test_calls_fail_json_on_request_failure(self, make_job_manager):
        manager = make_job_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(AnsibleModuleFail, match="Failed to create Job"):
            manager.create_job(manager.build_job_data())


# ===========================================================================
# XSOARJobManager.update_job
# ===========================================================================


class TestUpdateJob:
    def test_posts_to_correct_endpoint(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response

        result = manager.update_job(api_job_response)

        assert result == api_job_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/public/v1/jobs"

    def test_payload_includes_version_minus_one(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response

        manager.update_job(api_job_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["version"] == -1

    def test_payload_preserves_existing_id(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response

        manager.update_job(api_job_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["id"] == "job-abc123"

    def test_update_payload_omits_calculated_run_times(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.return_value = api_job_response
        api_job_response.update(
            {
                "nextRunTime": "2026-10-13T12:00:00Z",
                "displayNextRunTime": "2026-10-13T12:00:00Z",
                "disabledNextRunTime": "2026-10-13T12:00:00Z",
                "scheduledEntryGuid": "scheduler-entry-id",
                "jobSchedulingKey": "scheduler-key",
            }
        )

        manager.update_job(api_job_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert "nextRunTime" not in payload
        assert "displayNextRunTime" not in payload
        assert "disabledNextRunTime" not in payload
        assert payload["scheduledEntryGuid"] == "scheduler-entry-id"
        assert payload["jobSchedulingKey"] == "scheduler-key"

    def test_calls_fail_json_on_request_failure(self, make_job_manager, api_job_response):
        manager = make_job_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(AnsibleModuleFail, match="Failed to update Job"):
            manager.update_job(api_job_response)


# ===========================================================================
# XSOARJobManager.delete_job
# ===========================================================================


class TestDeleteJob:
    def test_sends_delete_to_correct_endpoint(self, make_job_manager):
        manager = make_job_manager(state="absent")
        manager.connection.request.return_value = {}

        manager.delete_job("job-abc123")

        manager.connection.request.assert_called_once_with(
            "DELETE",
            "/xsoar/public/v1/jobs/job-abc123",
        )

    def test_calls_fail_json_on_request_failure(self, make_job_manager):
        manager = make_job_manager(state="absent")
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to delete Job job-abc123"):
            manager.delete_job("job-abc123")


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_job_when_absent(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()

        with (
            patch.object(manager, "get_job_by_name", return_value=None),
            patch.object(manager, "create_job", return_value=api_job_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == f"Job {api_job_response['name']} created successfully"
        assert result["job"] == api_job_response

    def test_updates_job_when_cron_differs(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()
        manager.validate_and_normalize()
        stale = {**api_job_response, "cron": "0 12 * * *"}

        with (
            patch.object(manager, "get_job_by_name", return_value=stale),
            patch.object(manager, "update_job", return_value=api_job_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(current_job=stale)
        assert result["changed"]
        assert result["msg"] == f"Job {api_job_response['name']} updated successfully"
        assert result["job"] == api_job_response

    def test_updates_job_when_playbook_id_differs(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()
        manager.validate_and_normalize()
        stale = {**api_job_response, "playbookId": "old-playbook"}

        with (
            patch.object(manager, "get_job_by_name", return_value=stale),
            patch.object(manager, "update_job", return_value=api_job_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once()
        assert result["changed"]

    def test_no_change_when_job_is_up_to_date(self, make_job_manager, api_job_response, mock_module):
        """
        ``api_job_response`` matches ``job_params`` defaults — no update expected.
        """
        manager = make_job_manager()

        with (
            patch.object(manager, "get_job_by_name", return_value=api_job_response),
            patch.object(manager, "update_job") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"Job {api_job_response['name']} is already up to date"
        assert result["job"] == api_job_response

    def test_check_mode_reports_create_without_calling_api(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_job_by_name", return_value=None),
            patch.object(manager, "create_job") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Job {manager.name} would be created"

    def test_check_mode_reports_update_without_calling_api(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()
        manager.validate_and_normalize()
        module = mock_module(check_mode=True)
        stale = {**api_job_response, "cron": "0 12 * * *"}

        with (
            patch.object(manager, "get_job_by_name", return_value=stale),
            patch.object(manager, "update_job") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Job {manager.name} would be updated"

    def test_check_mode_no_change_when_up_to_date(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_job_by_name", return_value=api_job_response):
            result = ensure_present(module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Job {manager.name} is already up to date (check mode)"


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_existing_job(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager(state="absent")

        with (
            patch.object(manager, "get_job_by_name", return_value=api_job_response),
            patch.object(manager, "delete_job") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_job_response["id"])
        assert result["changed"]
        assert result["msg"] == (
            f"Job {api_job_response['name']} with ID {api_job_response['id']} deleted successfully"
        )
        assert result["job"] == api_job_response

    def test_no_change_when_job_already_absent(self, make_job_manager, mock_module):
        manager = make_job_manager(state="absent")

        with patch.object(manager, "get_job_by_name", return_value=None):
            result = ensure_absent(mock_module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Job {manager.name} does not exist"
        assert "job" not in result

    def test_check_mode_reports_delete_without_calling_api(self, make_job_manager, api_job_response, mock_module):
        manager = make_job_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_job_by_name", return_value=api_job_response),
            patch.object(manager, "delete_job") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Job {manager.name} would be deleted"


# ===========================================================================
# gather_jobs
# ===========================================================================


class TestGatherJobs:
    def test_returns_named_job_when_found(self, make_job_manager, api_job_response):
        manager = make_job_manager(state="gathered")

        with patch.object(manager, "get_job_by_name", return_value=api_job_response):
            result = gather_jobs(manager)

        assert not result["changed"]
        assert result["job"] == api_job_response
        assert result["msg"] == f"Job {manager.name} found"

    def test_reports_not_found_for_missing_named_job(self, make_job_manager):
        manager = make_job_manager(state="gathered")

        with patch.object(manager, "get_job_by_name", return_value=None):
            result = gather_jobs(manager)

        assert not result["changed"]
        assert result["msg"] == f"Job {manager.name} not found"
        assert "job" not in result

    def test_returns_jobs_matching_query(self, make_job_manager, api_job_response):
        manager = make_job_manager(name=None, query="type:Unclassified", state="gathered")

        with patch.object(manager, "get_jobs", return_value=[api_job_response]) as mock_get:
            result = gather_jobs(manager)

        mock_get.assert_called_once_with(query="type:Unclassified")
        assert not result["changed"]
        assert result["jobs"] == [api_job_response]
        assert result["msg"] == "Retrieved 1 jobs matching query"

    def test_reports_no_jobs_found_for_empty_query_result(self, make_job_manager):
        manager = make_job_manager(name=None, query="type:NonExistent", state="gathered")

        with patch.object(manager, "get_jobs", return_value=[]):
            result = gather_jobs(manager)

        assert not result["changed"]
        assert result["msg"] == "No jobs found matching query"
        assert "jobs" not in result

    def test_returns_all_jobs_when_name_and_query_are_none(self, make_job_manager, api_job_response):
        manager = make_job_manager(name=None, query=None, state="gathered")

        with patch.object(manager, "get_jobs", return_value=[api_job_response]) as mock_get:
            result = gather_jobs(manager)

        mock_get.assert_called_once_with()
        assert not result["changed"]
        assert result["jobs"] == [api_job_response]
        assert result["msg"] == "Retrieved 1 jobs"

    def test_reports_no_jobs_found_when_all_empty(self, make_job_manager):
        manager = make_job_manager(name=None, query=None, state="gathered")

        with patch.object(manager, "get_jobs", return_value=[]):
            result = gather_jobs(manager)

        assert not result["changed"]
        assert result["msg"] == "No jobs found"
        assert "jobs" not in result
