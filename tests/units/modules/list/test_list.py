"""
Unit tests for plugins/modules/list.py — XSOARListManager and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.list import ensure_absent, ensure_present, gather_lists

# ===========================================================================
# XSOARListManager.get_all_lists
# ===========================================================================


class TestGetAllLists:
    def test_returns_list_from_api(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.return_value = [{"id": "1", "name": "foo"}]

        result = manager.get_all_lists()

        assert result == [{"id": "1", "name": "foo"}]
        manager.connection.request.assert_called_once_with("GET", "/lists")

    def test_returns_empty_list_when_api_returns_empty(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.return_value = []

        assert manager.get_all_lists() == []

    def test_returns_empty_list_when_api_returns_non_list(self, make_list_manager):
        """API occasionally returns {} on empty result — should be normalised to []."""
        manager = make_list_manager()
        manager.connection.request.return_value = {}

        assert manager.get_all_lists() == []

    def test_raises_on_request_failure(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.side_effect = RuntimeError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get available lists"):
            manager.get_all_lists()


# ===========================================================================
# XSOARListManager.get_list_by_name
# ===========================================================================


class TestGetListByName:
    def test_returns_matching_list(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        other = {"id": "other-id", "name": "other-list"}
        manager.connection.request.return_value = [other, api_list_response]

        result = manager.get_list_by_name("test-list")

        assert result == api_list_response

    def test_returns_none_when_not_found(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.return_value = [{"id": "x", "name": "other"}]

        assert manager.get_list_by_name("test-list") is None

    def test_returns_none_on_empty_response(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.return_value = []

        assert manager.get_list_by_name("test-list") is None


# ===========================================================================
# XSOARListManager.create_list
# ===========================================================================


class TestCreateList:
    def test_posts_to_correct_endpoint(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        manager.connection.request.return_value = api_list_response

        result = manager.create_list()

        assert result == api_list_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/lists/save"

    def test_plain_text_payload(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        manager.connection.request.return_value = api_list_response

        manager.create_list()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["name"] == "test-list"
        assert payload["data"] == "line1\nline2"
        assert payload["type"] == "Text"
        assert payload["description"] == "A test list"
        assert payload["propagationLabels"] == []
        assert payload["version"] == -1

    def test_json_content_is_serialised(self, make_list_manager, api_list_response):
        manager = make_list_manager(content_type="JSON", json_content={"key": "value"})
        manager.connection.request.return_value = api_list_response

        manager.create_list()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["data"] == json.dumps({"key": "value"}, indent=2)

    def test_json_list_content_is_serialised(self, make_list_manager, api_list_response):
        json_list = [{"key": "value"}, {"key": "value2"}]
        manager = make_list_manager(content_type="JSON", json_content=json_list)
        manager.connection.request.return_value = api_list_response

        manager.create_list()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["data"] == json.dumps(json_list, indent=2)

    def test_read_roles_sets_allRead_false(self, make_list_manager, api_list_response):
        manager = make_list_manager(read_roles=["readonly_role"])
        manager.connection.request.return_value = api_list_response

        manager.create_list()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["xsoarReadOnlyRoles"] == ["readonly_role"]
        assert payload["allRead"] is False

    def test_edit_roles_sets_allReadWrite_false(self, make_list_manager, api_list_response):
        manager = make_list_manager(edit_roles=["admin_role"])
        manager.connection.request.return_value = api_list_response

        manager.create_list()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["roles"] == ["admin_role"]
        assert payload["allReadWrite"] is False

    def test_raises_on_request_failure(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.side_effect = RuntimeError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to create list"):
            manager.create_list()


# ===========================================================================
# XSOARListManager.update_list
# ===========================================================================


class TestUpdateList:
    def test_includes_existing_id_in_payload(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        manager.connection.request.return_value = api_list_response

        result = manager.update_list(api_list_response)

        assert result == api_list_response
        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["id"] == "list-abc123"
        assert payload["name"] == "test-list"

    def test_posts_to_save_endpoint(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        manager.connection.request.return_value = api_list_response

        manager.update_list(api_list_response)

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/lists/save"

    def test_raises_on_request_failure(self, make_list_manager, api_list_response):
        manager = make_list_manager()
        manager.connection.request.side_effect = RuntimeError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to update list"):
            manager.update_list(api_list_response)


# ===========================================================================
# XSOARListManager.delete_list
# ===========================================================================


class TestDeleteList:
    def test_posts_id_to_delete_endpoint(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.return_value = {}

        result = manager.delete_list("list-abc123")

        assert result is True
        manager.connection.request.assert_called_once_with("POST", "/lists/delete", {"id": "list-abc123"})

    def test_raises_on_request_failure(self, make_list_manager):
        manager = make_list_manager()
        manager.connection.request.side_effect = RuntimeError("forbidden")

        with pytest.raises(XSOARAPIError, match="Failed to delete list"):
            manager.delete_list("list-abc123")


# ===========================================================================
# XSOARListManager.data_differs
# ===========================================================================


class TestDataDiffers:
    def test_json_content_is_compared_as_parsed_structure(self, make_list_manager, api_list_response):
        """
        Re-running ``present`` against an API ``data`` string whose whitespace
        and key-ordering differ from ``json.dumps(json_content, indent=2)`` must
        report no change, because the comparison must be performed on the parsed
        structures rather than on the raw serialised string.
        """
        desired = {"a": 1, "b": [1, 2, 3]}
        manager = make_list_manager(content_type="JSON", json_content=desired, content=None)
        # Same structure, but serialised differently from json.dumps(..., indent=2)
        current_list = {**api_list_response, "type": "JSON", "data": '{"b":[1,2,3],"a":1}'}

        assert manager.data_differs(current_list) is False

    def test_json_content_change_is_detected(self, make_list_manager, api_list_response):
        manager = make_list_manager(content_type="JSON", json_content={"a": 1}, content=None)
        current_list = {**api_list_response, "type": "JSON", "data": '{"a": 2}'}

        assert manager.data_differs(current_list) is True

    def test_json_content_malformed_current_data_reports_change(self, make_list_manager, api_list_response):
        """If the server returned an invalid JSON blob, treat it as differing to force a rewrite."""
        manager = make_list_manager(content_type="JSON", json_content={"a": 1}, content=None)
        current_list = {**api_list_response, "type": "JSON", "data": "not json"}

        assert manager.data_differs(current_list) is True

    def test_text_content_compared_as_string(self, make_list_manager, api_list_response):
        manager = make_list_manager(content="line1\nline2")
        current_list = {**api_list_response, "data": "line1\nline2"}

        assert manager.data_differs(current_list) is False

    def test_text_content_change_is_detected(self, make_list_manager, api_list_response):
        manager = make_list_manager(content="line1\nline2")
        current_list = {**api_list_response, "data": "different"}

        assert manager.data_differs(current_list) is True

    def test_text_content_none_normalised_to_empty_string(self, make_list_manager, api_list_response):
        """A ``None`` ``content`` and an empty ``data`` field must compare equal."""
        manager = make_list_manager(content=None)
        current_list = {**api_list_response, "data": ""}

        assert manager.data_differs(current_list) is False


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_list_when_absent(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager()

        with (
            patch.object(manager, "get_list_by_name", return_value=None),
            patch.object(manager, "create_list", return_value=api_list_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} created successfully"
        assert result["list"] == api_list_response

    def test_updates_list_when_description_differs(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager()

        stale = {**api_list_response, "description": "old description"}

        with (
            patch.object(manager, "get_list_by_name", return_value=stale),
            patch.object(manager, "update_list", return_value=api_list_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(stale)
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} updated successfully"
        assert result["list"] == api_list_response

    def test_no_change_when_list_is_up_to_date(self, make_list_manager, api_list_response, mock_module):
        """api_list_response matches list_params defaults — no update expected."""
        manager = make_list_manager()

        with (
            patch.object(manager, "get_list_by_name", return_value=api_list_response),
            patch.object(manager, "update_list") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"List {api_list_response['name']} is already up to date"
        assert result["list"] == api_list_response

    def test_check_mode_reports_create_without_calling_api(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_list_by_name", return_value=None),
            patch.object(manager, "create_list") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} would be created"

        expected_result = {
            "name": manager.name,
            "description": manager.description,
            "type": manager.content_type,
            "propagationLabels": manager.propagation_labels,
            "roles": manager.edit_roles,
            "xsoarReadOnlyRoles": manager.read_roles,
            "data": manager.content,
        }
        assert result["list"] == expected_result

    def test_check_mode_create_projects_json_data(self, make_list_manager, mock_module):
        desired_json = {"ioc": "1.1.1.1", "kind": "ip"}
        manager = make_list_manager(content_type="JSON", json_content=desired_json, content=None)
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_list_by_name", return_value=None),
            patch.object(manager, "create_list") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} would be created"
        assert result["list"]["data"] == json.dumps(desired_json, indent=2)

    def test_check_mode_reports_update_without_calling_api(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager()
        module = mock_module(check_mode=True)

        stale = {**api_list_response, "description": "old description"}

        with (
            patch.object(manager, "get_list_by_name", return_value=stale),
            patch.object(manager, "update_list") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} would be updated"
        assert result["list"] == stale

    def test_check_mode_no_change_when_up_to_date(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_list_by_name", return_value=api_list_response):
            result = ensure_present(module, manager)

        assert not result["changed"]
        assert result["msg"] == f"List {api_list_response['name']} is already up to date (check mode)"

    def test_no_change_when_json_content_matches_after_parse(self, make_list_manager, api_list_response, mock_module):
        """
        End-to-end JSON idempotency: when the API returns ``data`` whose JSON
        whitespace and key-ordering differ from the locally-serialised form, a
        re-run with the same ``json_content`` must report no change.
        """
        desired = {"a": 1, "b": [1, 2, 3]}
        manager = make_list_manager(content_type="JSON", json_content=desired, content=None)
        existing = {**api_list_response, "type": "JSON", "data": '{"b": [1, 2, 3], "a": 1}'}

        with (
            patch.object(manager, "get_list_by_name", return_value=existing),
            patch.object(manager, "update_list") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"List {manager.name} is already up to date"


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_existing_list(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager(state="absent")

        with (
            patch.object(manager, "get_list_by_name", return_value=api_list_response),
            patch.object(manager, "delete_list") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_list_response["id"])
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} deleted successfully"

    def test_no_change_when_list_already_absent(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager(state="absent")

        with patch.object(manager, "get_list_by_name", return_value=None):
            result = ensure_absent(mock_module, manager)

        assert not result["changed"]
        assert result["msg"] == f"List {api_list_response['name']} does not exist"

    def test_check_mode_reports_delete_without_calling_api(self, make_list_manager, api_list_response, mock_module):
        manager = make_list_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_list_by_name", return_value=api_list_response),
            patch.object(manager, "delete_list") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"List {manager.name} would be deleted"
        assert result["list"] == api_list_response


# ===========================================================================
# gather_lists
# ===========================================================================


class TestGatherLists:
    def test_returns_named_list_when_found(self, make_list_manager, api_list_response):
        manager = make_list_manager(state="gathered")

        with patch.object(manager, "get_list_by_name", return_value=api_list_response):
            result = gather_lists(manager)

        assert not result["changed"]
        assert result["list"] == api_list_response
        assert result["msg"] == f"List {manager.name} found"

    def test_reports_not_found_for_missing_named_list(self, make_list_manager):
        manager = make_list_manager(state="gathered")

        with patch.object(manager, "get_list_by_name", return_value=None):
            result = gather_lists(manager)

        assert not result["changed"]
        assert result["msg"] == f"List {manager.name} not found"

    def test_returns_all_lists_when_name_is_none(self, make_list_manager, api_list_response):
        manager = make_list_manager(name=None, state="gathered")

        with patch.object(manager, "get_all_lists", return_value=[api_list_response]):
            result = gather_lists(manager)

        assert not result["changed"]
        assert result["lists"] == [api_list_response]
        assert result["msg"] == "Retrieved 1 lists"
