"""
Unit tests for plugins/modules/pre_process_rule.py — XSOARPreProcessRuleManager
and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.pre_process_rule import ensure_absent, ensure_present, gather_pre_process_rules
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARPreProcessRuleManager.get_pre_process_rules
# ===========================================================================


class TestGetPreProcessRules:
    def test_returns_rules_from_api(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        A list response from the API must be returned as-is.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = manager.get_pre_process_rules()

        assert result == [api_pre_process_rule_response]
        manager.connection.request.assert_called_once_with("GET", "/xsoar/preprocess/rules")

    def test_returns_empty_list_when_response_is_not_list(self, make_pre_process_rule_manager):
        """
        Non-list responses (e.g. ``{}`` on an empty result) must be normalised to ``[]``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = {}

        assert manager.get_pre_process_rules() == []

    def test_raises_on_request_failure(self, make_pre_process_rule_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get available pre-process rules"):
            manager.get_pre_process_rules()


# ===========================================================================
# XSOARPreProcessRuleManager.get_pre_process_rule_by_name
# ===========================================================================


class TestGetPreProcessRuleByName:
    def test_returns_matching_rule(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager()
        other = {"id": "other-id", "name": "other-rule"}
        manager.connection.request.return_value = [other, api_pre_process_rule_response]

        result = manager.get_pre_process_rule_by_name("test-rule")

        assert result == api_pre_process_rule_response

    def test_returns_none_when_not_found(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [{"id": "x", "name": "other-rule"}]

        assert manager.get_pre_process_rule_by_name("test-rule") is None

    def test_returns_none_on_empty_response(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = []

        assert manager.get_pre_process_rule_by_name("test-rule") is None


# ===========================================================================
# XSOARPreProcessRuleManager.build_rule_data
# ===========================================================================


class TestBuildRuleData:
    def test_create_payload_contains_required_fields(self, make_pre_process_rule_manager):
        """
        ``build_rule_data()`` with no arguments produces a create payload with
        all fields derived from module params and module-level defaults.
        """
        manager = make_pre_process_rule_manager()

        payload = manager.build_rule_data()

        assert payload["name"] == "test-rule"
        assert payload["action"] == "link"
        assert payload["enabled"]
        assert payload["propagationLabels"] == []
        assert payload["scriptID"] is None
        assert payload["shouldPublish"]
        assert payload["shouldCommit"]
        assert payload["commitMessage"] == "Preprocess rule edited"

    def test_update_payload(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        Verify the core structure of the update payload built from ``raw_rule_data``:

        - ``version`` is forced to ``-1`` to bypass XSOAR optimistic locking.
        - The existing ``id`` is preserved.
        - ``action``, ``enabled``, ``propagationLabels``, and ``scriptID`` are
          overridden from module params.
        """
        manager = make_pre_process_rule_manager(action="drop", propagation_labels=["all"])
        payload = manager.build_rule_data(raw_rule_data=api_pre_process_rule_response)

        assert payload["version"] == -1
        assert payload["id"] == "rule-abc123"
        assert payload["action"] == "drop"
        assert payload["propagationLabels"] == ["all"]
        assert payload["enabled"]

    def test_update_payload_does_not_mutate_input(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        ``build_rule_data`` must not mutate the ``raw_rule_data`` dict that was
        passed in — the caller still needs the original.
        """
        manager = make_pre_process_rule_manager()
        original_version = api_pre_process_rule_response["version"]

        new_rule_data = manager.build_rule_data(raw_rule_data=api_pre_process_rule_response)

        assert api_pre_process_rule_response["version"] == original_version
        assert new_rule_data["version"] == -1


# ===========================================================================
# XSOARPreProcessRuleManager.create_pre_process_rule
# ===========================================================================


class TestCreatePreProcessRule:
    def test_posts_to_correct_endpoint_and_returns_matching_rule(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        rule_data = manager.build_rule_data()
        result = manager.create_pre_process_rule(rule_data)

        assert result == api_pre_process_rule_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/preprocess/rule"

    def test_returns_none_when_rule_not_in_response_list(self, make_pre_process_rule_manager):
        """
        When the API response list does not contain a rule matching ``self.name``,
        ``create_pre_process_rule`` must return ``None``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [{"id": "other-id", "name": "other-rule"}]

        result = manager.create_pre_process_rule(manager.build_rule_data())

        assert result is None

    def test_raises_on_request_failure(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to create pre-process rule"):
            manager.create_pre_process_rule(manager.build_rule_data())


# ===========================================================================
# XSOARPreProcessRuleManager.update_pre_process_rule
# ===========================================================================


class TestUpdatePreProcessRule:
    def test_posts_to_correct_endpoint_and_returns_matching_rule(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = manager.update_pre_process_rule(api_pre_process_rule_response)

        assert result == api_pre_process_rule_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/preprocess/rule"

    def test_posts_built_payload_with_version_minus_one(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        """
        The payload sent to the API must carry ``version: -1`` and preserve
        the existing rule ``id``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        manager.update_pre_process_rule(api_pre_process_rule_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["version"] == -1
        assert payload["id"] == "rule-abc123"

    def test_raises_on_request_failure(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to update pre-process rule"):
            manager.update_pre_process_rule(api_pre_process_rule_response)


# ===========================================================================
# XSOARPreProcessRuleManager.delete_pre_process_rule
# ===========================================================================


class TestDeletePreProcessRule:
    def test_sends_delete_to_correct_endpoint(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="absent")
        manager.connection.request.return_value = {}

        manager.delete_pre_process_rule("rule-abc123")

        manager.connection.request.assert_called_once_with(
            "DELETE",
            "/xsoar/preprocess/rule/rule-abc123",
        )

    def test_calls_fail_json_on_request_failure(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="absent")
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to delete Pre-Process Rule rule-abc123"):
            manager.delete_pre_process_rule("rule-abc123")


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_rule_when_absent(self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module):
        manager = make_pre_process_rule_manager()

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=None),
            patch.object(manager, "create_pre_process_rule", return_value=api_pre_process_rule_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} created successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_updates_rule_when_action_differs(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        stale = {**api_pre_process_rule_response, "action": "drop"}

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=stale),
            patch.object(manager, "update_pre_process_rule", return_value=api_pre_process_rule_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(current_rule_data=stale)
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} updated successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_no_change_when_rule_is_up_to_date(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        """
        ``api_pre_process_rule_response`` matches ``pre_process_rule_params``
        defaults — no update expected.
        """
        manager = make_pre_process_rule_manager()

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "update_pre_process_rule") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} is already up to date"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_check_mode_reports_create_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=None),
            patch.object(manager, "create_pre_process_rule") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} would be created"

    def test_check_mode_reports_update_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)
        stale = {**api_pre_process_rule_response, "action": "drop"}

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=stale),
            patch.object(manager, "update_pre_process_rule") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} would be updated"

    def test_check_mode_no_change_when_up_to_date(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response):
            result = ensure_present(module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} is already up to date (check mode)"


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_existing_rule(self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module):
        manager = make_pre_process_rule_manager(state="absent")

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "delete_pre_process_rule") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_pre_process_rule_response["id"])
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {api_pre_process_rule_response['name']} deleted successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_no_change_when_rule_already_absent(self, make_pre_process_rule_manager, mock_module):
        manager = make_pre_process_rule_manager(state="absent")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=None):
            result = ensure_absent(mock_module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {manager.name} does not exist"
        assert "pre_process_rule" not in result

    def test_check_mode_reports_delete_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "delete_pre_process_rule") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {manager.name} would be deleted"


# ===========================================================================
# gather_pre_process_rules
# ===========================================================================


class TestGatherPreProcessRules:
    def test_returns_named_rule_when_found(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager(state="gathered")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["pre_process_rule"] == api_pre_process_rule_response
        assert result["msg"] == f"Pre-Process Rule '{manager.name}' retrieved successfully."

    def test_reports_not_found_for_missing_named_rule(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="gathered")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=None):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule '{manager.name}' not found."
        assert "pre_process_rule" not in result

    def test_returns_all_rules_when_name_is_none(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager(name=None, state="gathered")

        with patch.object(manager, "get_pre_process_rules", return_value=[api_pre_process_rule_response]) as mock_get:
            result = gather_pre_process_rules(manager)

        mock_get.assert_called_once_with()
        assert not result["changed"]
        assert result["pre_process_rules"] == [api_pre_process_rule_response]
        assert result["msg"] == "Retrieved 1 pre-process rules."

    def test_reports_no_rules_found_when_empty(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(name=None, state="gathered")

        with patch.object(manager, "get_pre_process_rules", return_value=[]):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["msg"] == "No pre-process rules found."
        assert "pre_process_rules" not in result
