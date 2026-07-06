"""
Unit tests for plugins/modules/integration.py — XSOARIntegrationManager and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from tests/conftest.py.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.integration import ensure_absent, ensure_present, gather_instances
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARIntegrationManager._build_configuration_data
# ===========================================================================


class TestBuildConfigurationData:
    def test_empty_configuration_returns_empty_list(self, make_integration_manager):
        manager = make_integration_manager()
        assert manager.configuration == []

    def test_plain_values_are_preserved(self, make_integration_manager):
        manager = make_integration_manager(configuration={"apikey": "abc123", "threshold": 10})
        assert {"name": "apikey", "value": "abc123"} in manager.configuration
        assert {"name": "threshold", "value": 10} in manager.configuration

    def test_password_dict_becomes_type_9(self, make_integration_manager):
        manager = make_integration_manager(configuration={"auth": {"password": "secret", "identifier": "svc"}})
        item = next(i for i in manager.configuration if i["name"] == "auth")
        assert item["type"] == 9
        assert item["value"]["password"] == "secret"
        assert item["value"]["identifier"] == "svc"

    def test_password_dict_without_identifier(self, make_integration_manager):
        manager = make_integration_manager(configuration={"auth": {"password": "secret"}})
        item = next(i for i in manager.configuration if i["name"] == "auth")
        assert item["type"] == 9
        assert "identifier" not in item["value"]

    def test_credential_reference_becomes_type_9(self, make_integration_manager):
        manager = make_integration_manager(configuration={"creds": {"credential": "my-credential-id"}})
        item = next(i for i in manager.configuration if i["name"] == "creds")
        assert item["type"] == 9
        assert item["value"] == {"credential": "my-credential-id"}

    def test_nested_dict_without_password_or_credential_is_plain(self, make_integration_manager):
        manager = make_integration_manager(configuration={"proxy": {"host": "10.0.0.1", "port": 8080}})
        item = next(i for i in manager.configuration if i["name"] == "proxy")
        assert "type" not in item
        assert item["value"] == {"host": "10.0.0.1", "port": 8080}


# ===========================================================================
# XSOARIntegrationManager.get_available_integrations
# ===========================================================================


class TestGetAvailableIntegrations:
    def test_returns_list_from_api(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = [{"id": "VirusTotal", "name": "VirusTotal"}]

        result = manager.get_available_integrations()

        assert result == [{"id": "VirusTotal", "name": "VirusTotal"}]
        manager.connection.request.assert_called_once_with("GET", "/settings/integration-commands")

    def test_returns_empty_list_when_api_returns_non_list(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {}

        assert manager.get_available_integrations() == []

    def test_raises_on_request_failure(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get available integrations"):
            manager.get_available_integrations()


# ===========================================================================
# XSOARIntegrationManager.get_all_instances
# ===========================================================================


class TestGetAllInstances:
    def test_returns_instances_from_dict_response(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = {"instances": [api_integration_response]}

        result = manager.get_all_instances()

        assert result == [api_integration_response]
        manager.connection.request.assert_called_once_with("POST", "/settings/integration/search", data={})

    def test_returns_empty_list_when_instances_key_missing(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {}

        assert manager.get_all_instances() == []

    def test_returns_empty_list_on_non_dict_response(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = []

        assert manager.get_all_instances() == []

    def test_raises_on_request_failure(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to get integration instances"):
            manager.get_all_instances()


# ===========================================================================
# XSOARIntegrationManager.get_instance_by_name
# ===========================================================================


class TestGetInstanceByName:
    def test_returns_matching_instance(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        other = {"id": "other-id", "name": "OtherIntegration"}
        manager.connection.request.return_value = {"instances": [other, api_integration_response]}

        result = manager.get_instance_by_name("TestIntegration")

        assert result == api_integration_response

    def test_returns_none_when_not_found(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {"instances": [{"id": "x", "name": "Other"}]}

        assert manager.get_instance_by_name("TestIntegration") is None

    def test_returns_none_on_empty_instances(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {"instances": []}

        assert manager.get_instance_by_name("TestIntegration") is None


# ===========================================================================
# XSOARIntegrationManager.get_instance_by_id
# ===========================================================================


class TestGetInstanceById:
    def test_returns_first_instance_when_found(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = {"instances": [api_integration_response]}

        result = manager.get_instance_by_id("integration-abc123")

        assert result == api_integration_response

    def test_returns_none_when_instances_empty(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {"instances": []}

        assert manager.get_instance_by_id("integration-abc123") is None

    def test_returns_none_when_instances_key_missing(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {}

        assert manager.get_instance_by_id("integration-abc123") is None

    def test_raises_on_request_failure(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("not found")

        with pytest.raises(XSOARAPIError, match="Failed to get integration instance by ID"):
            manager.get_instance_by_id("integration-abc123")


# ===========================================================================
# XSOARIntegrationManager.create_instance
# ===========================================================================


class TestCreateInstance:
    def test_uses_put_to_correct_endpoint(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = api_integration_response

        result = manager.create_instance()

        assert result == api_integration_response
        args, kwargs = manager.connection.request.call_args
        assert args[0] == "PUT"
        assert args[1] == "/settings/integration"

    def test_payload_contains_required_fields(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = api_integration_response

        manager.create_instance()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["brand"] == "VirusTotal"
        assert payload["name"] == "TestIntegration"
        assert payload["enabled"] == "true"
        assert payload["defaultIgnore"] is False
        assert payload["propagationLabels"] == ["all"]
        assert payload["version"] == 0

    def test_optional_fields_excluded_when_none(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(engine=None, engine_group=None, incoming_mapper_id=None)
        manager.connection.request.return_value = api_integration_response

        manager.create_instance()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert "engine" not in payload
        assert "engineGroup" not in payload
        assert "incomingMapperId" not in payload

    def test_optional_fields_included_when_set(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(engine="my-engine", engine_group="group-1")
        manager.connection.request.return_value = api_integration_response

        manager.create_instance()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["engine"] == "my-engine"
        assert payload["engineGroup"] == "group-1"

    def test_raises_on_request_failure(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("server error")

        with pytest.raises(XSOARAPIError, match="Failed to create integration instance"):
            manager.create_instance()


# ===========================================================================
# XSOARIntegrationManager.update_instance
# ===========================================================================


class TestUpdateInstance:
    def test_uses_brand_from_current_instance(self, make_integration_manager, api_integration_response):
        """update_instance takes brand from current_instance, not self.brand."""
        manager = make_integration_manager(brand="NewBrand")
        manager.connection.request.return_value = api_integration_response

        manager.update_instance(api_integration_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["brand"] == "VirusTotal"  # from current_instance, not "NewBrand"

    def test_uses_id_from_current_instance_when_instance_id_not_set(
        self, make_integration_manager, api_integration_response
    ):
        manager = make_integration_manager(instance_id=None)
        manager.connection.request.return_value = api_integration_response

        manager.update_instance(api_integration_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["id"] == "integration-abc123"

    def test_instance_id_on_manager_takes_precedence(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(instance_id="override-id")
        manager.connection.request.return_value = api_integration_response

        manager.update_instance(api_integration_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["id"] == "override-id"

    def test_uses_put_to_correct_endpoint(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = api_integration_response

        manager.update_instance(api_integration_response)

        args, _ = manager.connection.request.call_args
        assert args[0] == "PUT"
        assert args[1] == "/settings/integration"

    def test_version_is_minus_one(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.return_value = api_integration_response

        manager.update_instance(api_integration_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["version"] == -1

    def test_raises_on_request_failure(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("forbidden")

        with pytest.raises(XSOARAPIError, match="Failed to update integration instance"):
            manager.update_instance(api_integration_response)

    def test_data_payload_preserves_schema_type_for_existing_fields(self, make_integration_manager):
        manager = make_integration_manager(configuration={"isFetch": True})
        manager.connection.request.return_value = {}

        current_instance = {
            "id": "integration-abc123",
            "name": "TestIntegration",
            "brand": "VirusTotal",
            "engine": None,
            "engineGroup": None,
            "incomingMapperId": None,
            "data": [
                {
                    "name": "isFetch",
                    "type": 8,
                    "section": "Collect",
                    "display": "Fetch incidents",
                    "value": False,
                }
            ],
        }

        manager.update_instance(current_instance)

        payload = manager.connection.request.call_args.kwargs["data"]
        expected_data = [
            {
                "name": "isFetch",
                "type": 8,
                "section": "Collect",
                "display": "Fetch incidents",
                "value": True,
            }
        ]
        assert payload["data"] == expected_data

    def test_data_payload_uses_desired_item_when_field_not_in_current_schema(self, make_integration_manager):
        manager = make_integration_manager(configuration={"new_toggle": True})
        manager.connection.request.return_value = {}

        current_instance = {
            "id": "integration-abc123",
            "name": "TestIntegration",
            "brand": "VirusTotal",
            "engine": None,
            "engineGroup": None,
            "incomingMapperId": None,
            "data": [],
        }

        manager.update_instance(current_instance)

        payload = manager.connection.request.call_args.kwargs["data"]
        expected_data = [{"name": "new_toggle", "value": True}]
        assert payload["data"] == expected_data


# ===========================================================================
# XSOARIntegrationManager.delete_instance
# ===========================================================================


class TestDeleteInstance:
    def test_uses_delete_to_correct_endpoint(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.return_value = {}

        result = manager.delete_instance("integration-abc123")

        assert result is True
        manager.connection.request.assert_called_once_with("DELETE", "/settings/integration/integration-abc123")

    def test_raises_on_request_failure(self, make_integration_manager):
        manager = make_integration_manager()
        manager.connection.request.side_effect = RuntimeError("forbidden")

        with pytest.raises(XSOARAPIError, match="Failed to delete integration instance"):
            manager.delete_instance("integration-abc123")


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_fails_when_name_and_instance_id_both_missing(self, make_integration_manager, mock_module):
        manager = make_integration_manager(name=None, instance_id=None)

        with pytest.raises(AnsibleModuleFail, match="name.*instance_id|instance_id.*name"):
            ensure_present(mock_module, manager)

    def test_creates_instance_when_absent(self, make_integration_manager, api_integration_response, mock_module):
        manager = make_integration_manager()

        with (
            patch.object(manager, "instance_exists", return_value=(False, None)),
            patch.object(manager, "create_instance", return_value=api_integration_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"] is True
        assert "created" in result["msg"]
        assert result["integration"] == api_integration_response

    def test_fails_when_creating_without_brand(self, make_integration_manager, mock_module):
        manager = make_integration_manager(brand=None)

        with (
            patch.object(manager, "instance_exists", return_value=(False, None)),
            pytest.raises(AnsibleModuleFail, match="brand"),
        ):
            ensure_present(mock_module, manager)

    def test_updates_instance_when_field_differs(self, make_integration_manager, api_integration_response, mock_module):
        manager = make_integration_manager(enabled=False)

        # api_integration_response has "enabled": "true"; desired is "false" → values differ → update triggered
        updated = {**api_integration_response, "enabled": "false"}

        with (
            patch.object(manager, "instance_exists", return_value=(True, api_integration_response)),
            patch.object(manager, "update_instance", return_value=updated) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(api_integration_response)
        assert result["changed"] is True
        assert "updated" in result["msg"]

    def test_no_change_when_instance_is_up_to_date(
        self, make_integration_manager, api_integration_response, mock_module
    ):
        """api_integration_response matches integration_params defaults — no update."""
        manager = make_integration_manager()

        with (
            patch.object(manager, "instance_exists", return_value=(True, api_integration_response)),
            patch.object(manager, "update_instance") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is False
        assert result["integration"] == api_integration_response

    def test_check_mode_reports_create_without_calling_api(self, make_integration_manager, mock_module):
        manager = make_integration_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "instance_exists", return_value=(False, None)),
            patch.object(manager, "create_instance") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"] is True
        assert "would be created" in result["msg"]

    def test_check_mode_reports_update_without_calling_api(
        self, make_integration_manager, api_integration_response, mock_module
    ):
        manager = make_integration_manager(enabled=False)
        module = mock_module(check_mode=True)

        stale = {**api_integration_response, "enabled": "true"}  # current=true, desired=false → update needed

        with (
            patch.object(manager, "instance_exists", return_value=(True, stale)),
            patch.object(manager, "update_instance") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is True
        assert "would be updated" in result["msg"]

    def test_check_mode_no_change_when_up_to_date(
        self, make_integration_manager, api_integration_response, mock_module
    ):
        manager = make_integration_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "instance_exists", return_value=(True, api_integration_response)):
            result = ensure_present(module, manager)

        assert result["changed"] is False

    def test_lookup_uses_instance_id_when_set(self, make_integration_manager, api_integration_response, mock_module):
        manager = make_integration_manager(instance_id="integration-abc123")

        with (
            patch.object(manager, "instance_exists", return_value=(True, api_integration_response)) as mock_exists,
            patch.object(manager, "update_instance", return_value=api_integration_response),
        ):
            ensure_present(mock_module, manager)

        mock_exists.assert_called_once_with(instance_id="integration-abc123")


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_fails_when_name_and_instance_id_both_missing(self, make_integration_manager, mock_module):
        manager = make_integration_manager(name=None, instance_id=None, state="absent")

        with pytest.raises(AnsibleModuleFail, match="name.*instance_id|instance_id.*name"):
            ensure_absent(mock_module, manager)

    def test_deletes_existing_instance(self, make_integration_manager, api_integration_response, mock_module):
        manager = make_integration_manager(state="absent")

        with (
            patch.object(manager, "instance_exists", return_value=(True, api_integration_response)),
            patch.object(manager, "delete_instance") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_integration_response["id"])
        assert result["changed"] is True
        assert "deleted" in result["msg"]

    def test_no_change_when_instance_already_absent(self, make_integration_manager, mock_module):
        manager = make_integration_manager(state="absent")

        with patch.object(manager, "instance_exists", return_value=(False, None)):
            result = ensure_absent(mock_module, manager)

        assert result["changed"] is False
        assert "does not exist" in result["msg"]

    def test_check_mode_reports_delete_without_calling_api(
        self, make_integration_manager, api_integration_response, mock_module
    ):
        manager = make_integration_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "instance_exists", return_value=(True, api_integration_response)),
            patch.object(manager, "delete_instance") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"] is True
        assert "would be deleted" in result["msg"]


# ===========================================================================
# gather_instances
# ===========================================================================


class TestGatherInstances:
    def test_returns_available_integrations_when_get_available_true(self, make_integration_manager):
        manager = make_integration_manager(get_available=True, state="gathered")
        available = [{"id": "VirusTotal", "name": "VirusTotal"}]

        with patch.object(manager, "get_available_integrations", return_value=available):
            result = gather_instances(manager)

        assert result["changed"] is False
        assert result["available_integrations"] == available
        assert "1" in result["msg"]

    def test_returns_named_instance_when_found(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(state="gathered")

        with patch.object(manager, "get_instance_by_name", return_value=api_integration_response):
            result = gather_instances(manager)

        assert result["changed"] is False
        assert result["integration"] == api_integration_response
        assert "found" in result["msg"]

    def test_reports_not_found_for_missing_named_instance(self, make_integration_manager):
        manager = make_integration_manager(state="gathered")

        with patch.object(manager, "get_instance_by_name", return_value=None):
            result = gather_instances(manager)

        assert result["changed"] is False
        assert "not found" in result["msg"]

    def test_returns_instance_by_id_when_found(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(name=None, instance_id="integration-abc123", state="gathered")

        with patch.object(manager, "get_instance_by_id", return_value=api_integration_response):
            result = gather_instances(manager)

        assert result["changed"] is False
        assert result["integration"] == api_integration_response
        assert "found" in result["msg"]

    def test_returns_all_instances_when_no_identifier(self, make_integration_manager, api_integration_response):
        manager = make_integration_manager(name=None, instance_id=None, state="gathered")

        with patch.object(manager, "get_all_instances", return_value=[api_integration_response]):
            result = gather_instances(manager)

        assert result["changed"] is False
        assert result["integrations"] == [api_integration_response]
        assert "1" in result["msg"]
