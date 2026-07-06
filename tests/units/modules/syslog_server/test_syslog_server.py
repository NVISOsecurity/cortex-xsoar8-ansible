"""
Unit tests for plugins/modules/syslog_server.py — XSOARSyslogServerManager
and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.

Key notes
---------
- ``state=present`` requires direct fields in ``request_data``; filters are rejected.
- ``state=absent`` / ``state=gathered`` require ``request_data.filters``; direct
  fields are rejected.  An empty filters list (``[]``) is rejected.
# TODO: Update this is the future if the API ever supports a fetch-all for syslog servers.
- ``get_syslog_servers`` always uses ``self.prepared_request_data``; the
  empty-``request_data`` fallback was removed because the API rejects it.
- API response objects use uppercase field names (e.g. ``SYSLOG_INTEGRATION_NAME``);
  ``normalize_server`` maps these to lowercase module-facing keys.
- ``ensure_present`` idempotency is checked via ``instance_needs_update`` on
  the normalised current server; ``port`` is always compared as a string.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.syslog_server import XSOARSyslogServerManager, ensure_absent, ensure_present, gather_syslog_servers
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARSyslogServerManager — validation in __init__
# ===========================================================================


class TestValidation:
    def test_fails_when_present_state_receives_filters(self, make_syslog_server_manager):
        """``state=present`` must reject ``request_data.filters``."""
        with pytest.raises(AnsibleModuleFail, match="state=present does not support request_data.filters"):
            make_syslog_server_manager(
                request_data={"filters": [{"field": "name", "operator": "eq", "value": "x"}]},
                state="present",
            )

    def test_fails_when_absent_state_receives_direct_fields(self, make_syslog_server_manager):
        """``state=absent`` must reject direct fields in ``request_data``."""
        with pytest.raises(
            AnsibleModuleFail,
            match="state=absent or state=gathered do not support direct request_data fields",
        ):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "514",
                    "protocol": "UDP",
                    "facility": "FAC_LOCAL0",
                },
                state="absent",
            )

    def test_fails_when_gathered_state_receives_direct_fields(self, make_syslog_server_manager):
        """``state=gathered`` also rejects direct fields — same rule as absent."""
        with pytest.raises(
            AnsibleModuleFail,
            match="state=absent or state=gathered do not support direct request_data fields",
        ):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "514",
                    "protocol": "UDP",
                    "facility": "FAC_LOCAL0",
                },
                state="gathered",
            )

    def test_fails_when_both_filters_and_direct_fields_provided(self, make_syslog_server_manager):
        """Mixing filters with direct fields must be rejected regardless of state."""
        with pytest.raises(AnsibleModuleFail, match="request_data must contain either"):
            make_syslog_server_manager(
                request_data={
                    "filters": [{"field": "name", "operator": "eq", "value": "x"}],
                    "name": "test-syslog",
                },
                state="present",
            )

    def test_fails_when_required_direct_fields_missing(self, make_syslog_server_manager):
        """``state=present`` must fail when required fields are absent."""
        with pytest.raises(AnsibleModuleFail, match="Missing:"):
            make_syslog_server_manager(
                request_data={"name": "test-syslog"},
                state="present",
            )

    def test_fails_when_unsupported_direct_field_provided(self, make_syslog_server_manager):
        """Unknown keys in ``request_data`` direct fields must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="Unsupported request_data field"):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "514",
                    "protocol": "UDP",
                    "facility": "FAC_LOCAL0",
                    "nonexistent_key": "value",
                },
                state="present",
            )

    def test_fails_when_invalid_protocol_provided(self, make_syslog_server_manager):
        """Protocol values outside TCP/UDP/TLS must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="Invalid request_data.protocol"):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "514",
                    "protocol": "INVALID",
                    "facility": "FAC_LOCAL0",
                },
                state="present",
            )

    def test_fails_when_invalid_facility_provided(self, make_syslog_server_manager):
        """Facility values outside the allowed list must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="Invalid request_data.facility"):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "514",
                    "protocol": "UDP",
                    "facility": "FAC_INVALID",
                },
                state="present",
            )

    def test_accepts_integer_port_and_normalizes_to_string(self, make_syslog_server_manager):
        """Integer ``request_data.port`` must be accepted and normalized to string in prepared payload."""
        manager = make_syslog_server_manager(
            request_data={
                "name": "test-syslog",
                "address": "1.2.3.4",
                "port": 514,
                "protocol": "UDP",
                "facility": "FAC_LOCAL0",
            },
            state="present",
        )

        assert manager.prepared_request_data["request_data"]["port"] == "514"

    def test_rejects_boolean_port(self, make_syslog_server_manager):
        """Boolean values must not be accepted as port even though bool is a subclass of int."""
        with pytest.raises(AnsibleModuleFail, match="Invalid request_data.port"):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": True,
                    "protocol": "UDP",
                    "facility": "FAC_LOCAL0",
                },
                state="present",
            )

    def test_fails_when_filter_field_is_invalid(self, make_syslog_server_manager):
        """Filter objects with unsupported ``field`` values must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="Supported values:"):
            make_syslog_server_manager(
                request_data={"filters": [{"field": "invalid_field", "operator": "eq", "value": "x"}]},
                state="gathered",
            )

    def test_fails_when_filter_operator_is_invalid(self, make_syslog_server_manager):
        """Filter objects with unsupported ``operator`` values must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="Supported values:"):
            make_syslog_server_manager(
                request_data={"filters": [{"field": "name", "operator": "ne", "value": "x"}]},
                state="gathered",
            )

    def test_fails_when_filter_value_is_none(self, make_syslog_server_manager):
        """Filter objects with a ``None`` value must be rejected."""
        with pytest.raises(AnsibleModuleFail, match="A value is required"):
            make_syslog_server_manager(
                request_data={"filters": [{"field": "name", "operator": "eq", "value": None}]},
                state="gathered",
            )

    def test_empty_filters_list_is_rejected(self, make_syslog_server_manager):
        """An empty ``filters`` list must be rejected — the API requires at least one filter."""
        with pytest.raises(AnsibleModuleFail, match="Expected a non-empty array of filter objects"):
            make_syslog_server_manager(
                request_data={"filters": []},
                state="gathered",
            )

    def test_prepared_request_data_set_after_valid_direct_fields(self, make_syslog_server_manager):
        """A valid ``state=present`` manager must expose correct ``prepared_request_data``."""
        manager = make_syslog_server_manager()
        expected = {
            "request_data": {
                "name": "test-syslog",
                "address": "1.2.3.4",
                "port": "514",
                "protocol": "UDP",
                "facility": "FAC_LOCAL0",
            }
        }
        assert manager.prepared_request_data == expected

    def test_prepared_request_data_set_after_valid_filters(self, make_syslog_server_manager):
        """A valid filter-based manager must expose correct ``prepared_request_data``."""
        filters = [{"field": "name", "operator": "eq", "value": "test-syslog"}]
        manager = make_syslog_server_manager(
            request_data={"filters": filters},
            state="gathered",
        )
        assert manager.prepared_request_data == {"request_data": {"filters": filters}}

    def test_fails_when_tls_protocol_has_no_security_info(self, make_syslog_server_manager):
        """TLS must include ``security_info`` with ``ignore_cert_errors``."""
        with pytest.raises(
            AnsibleModuleFail,
            match="requires request_data.security_info including request_data.security_info.ignore_cert_errors",
        ):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "6514",
                    "protocol": "TLS",
                    "facility": "FAC_LOCAL0",
                },
                state="present",
            )

    def test_fails_when_tls_security_info_missing_ignore_cert_errors(self, make_syslog_server_manager):
        """For TLS, ``security_info.ignore_cert_errors`` is required even when certificate fields are set."""
        with pytest.raises(
            AnsibleModuleFail,
            match="request_data.security_info.ignore_cert_errors is required when request_data.protocol=TLS",
        ):
            make_syslog_server_manager(
                request_data={
                    "name": "test-syslog",
                    "address": "1.2.3.4",
                    "port": "6514",
                    "protocol": "TLS",
                    "facility": "FAC_LOCAL0",
                    "security_info": {"certificate_name": "syslog-cert"},
                },
                state="present",
            )

    def test_accepts_tls_with_only_ignore_cert_errors(self, make_syslog_server_manager):
        """For TLS, certificate fields are optional when ``ignore_cert_errors`` is provided."""
        manager = make_syslog_server_manager(
            request_data={
                "name": "test-syslog",
                "address": "1.2.3.4",
                "port": "6514",
                "protocol": "TLS",
                "facility": "FAC_LOCAL0",
                "security_info": {"ignore_cert_errors": False},
            },
            state="present",
        )

        expected_security_info = {"ignore_cert_errors": False}
        assert manager.prepared_request_data["request_data"]["security_info"] == expected_security_info


# ===========================================================================
# XSOARSyslogServerManager.normalize_server
# ===========================================================================


class TestNormalizeServer:
    def test_maps_api_fields_to_module_fields(self, api_syslog_server_response):
        """All expected module-facing keys must be present with correct values."""
        result = XSOARSyslogServerManager.normalize_server(api_syslog_server_response)

        assert result["syslog_id"] == "syslog-abc123"
        assert result["name"] == "test-syslog"
        assert result["address"] == "1.2.3.4"
        assert result["port"] == "514"
        assert result["protocol"] == "UDP"
        assert result["facility"] == "FAC_LOCAL0"
        assert result["status"] == "active"

    def test_port_is_always_a_string(self, api_syslog_server_response):
        """``SYSLOG_INTEGRATION_PORT`` is an integer in the API; must be str in output."""
        result = XSOARSyslogServerManager.normalize_server(api_syslog_server_response)
        assert isinstance(result["port"], str)

    def test_security_info_absent_when_certificate_fields_are_empty(self, api_syslog_server_response):
        """When TLS certificate fields are None, ``security_info`` must not appear."""
        result = XSOARSyslogServerManager.normalize_server(api_syslog_server_response)
        assert "security_info" not in result

    def test_security_info_present_when_certificate_name_set(self, api_syslog_server_response):
        """When ``SYSLOG_INTEGRATION_CERTIFICATE_NAME`` is set, it must appear in ``security_info``."""
        api_syslog_server_response["SYSLOG_INTEGRATION_CERTIFICATE_NAME"] = "my-cert"
        result = XSOARSyslogServerManager.normalize_server(api_syslog_server_response)
        assert result["security_info"]["certificate_name"] == "my-cert"

    def test_returns_empty_dict_for_falsy_input(self):
        """``normalize_server(None)`` and ``normalize_server({})`` must return ``{}``."""
        assert XSOARSyslogServerManager.normalize_server(None) == {}
        assert XSOARSyslogServerManager.normalize_server({}) == {}


# ===========================================================================
# XSOARSyslogServerManager.get_fields_to_compare
# ===========================================================================


class TestGetFieldsToCompare:
    def test_returns_core_fields_for_non_tls_protocol(self, make_syslog_server_manager):
        """For UDP/TCP protocols, only the 5 core fields must be returned."""
        manager = make_syslog_server_manager()
        fields = dict(manager.get_fields_to_compare())

        assert set(fields.keys()) == {"name", "address", "port", "protocol", "facility"}

    def test_includes_security_info_for_tls_protocol(self, make_syslog_server_manager):
        """For TLS protocol, ``security_info`` (minus ``certificate_content``) must be included."""
        manager = make_syslog_server_manager(
            request_data={
                "name": "test-syslog",
                "address": "1.2.3.4",
                "port": "514",
                "protocol": "TLS",
                "facility": "FAC_LOCAL0",
                "security_info": {
                    "certificate_name": "my-cert",
                    "ignore_cert_errors": False,
                    "certificate_content": "pem-data",
                },
            }
        )
        fields = dict(manager.get_fields_to_compare())

        assert "security_info" in fields
        expected_security_info = {
            "certificate_name": "my-cert",
            "ignore_cert_errors": False,
        }
        assert fields["security_info"] == expected_security_info


# ===========================================================================
# XSOARSyslogServerManager.get_syslog_servers
# ===========================================================================


class TestGetSyslogServers:
    def test_posts_to_correct_endpoint(self, make_syslog_server_manager):
        """Must POST to the syslog get endpoint."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )
        manager.connection.request.return_value = {"objects": []}

        manager.get_syslog_servers()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/integrations/syslog/get"

    def test_returns_objects_from_response(self, make_syslog_server_manager, api_syslog_server_response):
        """Objects in the API response must be returned as a list."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )
        manager.connection.request.return_value = {"objects": [api_syslog_server_response]}

        result = manager.get_syslog_servers()

        assert result == [api_syslog_server_response]

    def test_returns_empty_list_when_response_is_not_dict(self, make_syslog_server_manager):
        """Non-dict API response must be normalised to ``[]``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )
        manager.connection.request.return_value = []

        assert manager.get_syslog_servers() == []

    def test_uses_prepared_request_data_by_default(self, make_syslog_server_manager):
        """When called without arguments, must forward ``self.prepared_request_data``."""
        filters = [{"field": "name", "operator": "eq", "value": "test-syslog"}]
        manager = make_syslog_server_manager(
            request_data={"filters": filters},
            state="gathered",
        )
        manager.connection.request.return_value = {"objects": []}

        manager.get_syslog_servers()

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == manager.prepared_request_data

    def test_uses_explicit_data_argument_when_provided(self, make_syslog_server_manager):
        """An explicit ``data`` argument must override ``self.prepared_request_data``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )
        manager.connection.request.return_value = {"objects": []}
        explicit_data = {"request_data": {"filters": [{"field": "id", "operator": "eq", "value": "abc"}]}}

        manager.get_syslog_servers(data=explicit_data)

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == explicit_data

    def test_calls_fail_json_on_request_failure(self, make_syslog_server_manager):
        """API errors must surface as ``fail_json``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(AnsibleModuleFail, match="Failed to retrieve syslog servers"):
            manager.get_syslog_servers()


# ===========================================================================
# XSOARSyslogServerManager.get_syslog_server_by_name
# ===========================================================================


class TestGetSyslogServerByName:
    def test_builds_name_filter_and_returns_list(self, make_syslog_server_manager, api_syslog_server_response):
        """Must construct a name-eq filter and return the matching objects list."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"objects": [api_syslog_server_response]}

        result = manager.get_syslog_server_by_name("test-syslog")

        assert result == [api_syslog_server_response]
        _, kwargs = manager.connection.request.call_args
        filters = kwargs["data"]["request_data"]["filters"]
        assert filters == [{"field": "name", "operator": "eq", "value": "test-syslog"}]

    def test_returns_empty_list_when_no_match(self, make_syslog_server_manager):
        """Must return ``[]`` when the API returns an empty objects list."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"objects": []}

        assert manager.get_syslog_server_by_name("nonexistent") == []


# ===========================================================================
# XSOARSyslogServerManager.create_syslog_server
# ===========================================================================


class TestCreateSyslogServer:
    def test_posts_to_correct_endpoint(self, make_syslog_server_manager):
        """Must POST to the syslog create endpoint."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"SYSLOG_INTEGRATION_NAME": "test-syslog"}

        manager.create_syslog_server()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/integrations/syslog/create"

    def test_sends_prepared_request_data(self, make_syslog_server_manager):
        """Must send ``self.prepared_request_data`` as the request body."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {}

        manager.create_syslog_server()

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == manager.prepared_request_data

    def test_returns_response_dict(self, make_syslog_server_manager, api_syslog_server_response):
        """Must return the dict response from the API."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = api_syslog_server_response

        result = manager.create_syslog_server()

        assert result == api_syslog_server_response

    def test_calls_fail_json_on_request_failure(self, make_syslog_server_manager):
        """API errors must surface as ``fail_json``."""
        manager = make_syslog_server_manager()
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to create syslog server"):
            manager.create_syslog_server()


# ===========================================================================
# XSOARSyslogServerManager.update_syslog_server
# ===========================================================================


class TestUpdateSyslogServer:
    def test_posts_to_correct_endpoint(self, make_syslog_server_manager, api_syslog_server_response):
        """Must POST to the syslog update endpoint."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"reply": True}

        manager.update_syslog_server(api_syslog_server_response)

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/integrations/syslog/update"

    def test_injects_syslog_id_from_current_server(self, make_syslog_server_manager, api_syslog_server_response):
        """The ``syslog_id`` field in the payload must be taken from the current server's ID."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"reply": True}

        manager.update_syslog_server(api_syslog_server_response)

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"]["request_data"]["syslog_id"] == "syslog-abc123"

    def test_returns_true_when_reply_is_truthy(self, make_syslog_server_manager, api_syslog_server_response):
        """Must return ``True`` when the API ``reply`` value is truthy."""
        manager = make_syslog_server_manager()
        manager.connection.request.return_value = {"reply": True}

        assert manager.update_syslog_server(api_syslog_server_response) is True

    def test_fails_when_syslog_id_missing_from_current_server(self, make_syslog_server_manager):
        """Must call ``fail_json`` when the current server has no ``SYSLOG_INTEGRATION_ID``."""
        manager = make_syslog_server_manager()

        with pytest.raises(AnsibleModuleFail, match="SYSLOG_INTEGRATION_ID is missing"):
            manager.update_syslog_server({})

    def test_calls_fail_json_on_request_failure(self, make_syslog_server_manager, api_syslog_server_response):
        """API errors must surface as ``fail_json``."""
        manager = make_syslog_server_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(AnsibleModuleFail, match="Failed to update syslog server"):
            manager.update_syslog_server(api_syslog_server_response)


# ===========================================================================
# XSOARSyslogServerManager.delete_syslog_servers
# ===========================================================================


class TestDeleteSyslogServers:
    def test_posts_to_correct_endpoint(self, make_syslog_server_manager):
        """Must POST to the syslog delete endpoint."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="absent",
        )
        manager.connection.request.return_value = {}

        manager.delete_syslog_servers()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/integrations/syslog/delete"

    def test_sends_prepared_request_data(self, make_syslog_server_manager):
        """Must send ``self.prepared_request_data`` as the request body."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="absent",
        )
        manager.connection.request.return_value = {}

        manager.delete_syslog_servers()

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == manager.prepared_request_data

    def test_calls_fail_json_on_request_failure(self, make_syslog_server_manager):
        """API errors must surface as ``fail_json``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="absent",
        )
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to delete syslog server"):
            manager.delete_syslog_servers()


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_server_when_absent(self, make_syslog_server_manager, api_syslog_server_response, mock_module):
        """When no server exists, must call ``create_syslog_server`` and report changed."""
        manager = make_syslog_server_manager()

        with (
            patch.object(manager, "get_syslog_server_by_name", return_value=[]),
            patch.object(manager, "create_syslog_server", return_value=api_syslog_server_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"] is True
        assert result["syslog_server"] == XSOARSyslogServerManager.normalize_server(api_syslog_server_response)

    def test_updates_server_when_fields_differ(
        self, make_syslog_server_manager, api_syslog_server_response, mock_module
    ):
        """When the current server differs from desired state, must update and report changed."""
        manager = make_syslog_server_manager()
        stale = {**api_syslog_server_response, "SYSLOG_INTEGRATION_ADDRESS": "9.9.9.9"}

        with (
            patch.object(
                manager,
                "get_syslog_server_by_name",
                side_effect=[[stale], [api_syslog_server_response]],
            ),
            patch.object(manager, "update_syslog_server") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(stale)
        assert result["changed"] is True

    def test_no_change_when_server_is_up_to_date(
        self, make_syslog_server_manager, api_syslog_server_response, mock_module
    ):
        """When the current server matches desired state, must report no change."""
        manager = make_syslog_server_manager()

        with (
            patch.object(manager, "get_syslog_server_by_name", return_value=[api_syslog_server_response]),
            patch.object(manager, "update_syslog_server") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is False
        assert result["msg"] == "Syslog server is already up to date"

    def test_check_mode_reports_create_without_api_call(self, make_syslog_server_manager, mock_module):
        """In check mode, ``create_syslog_server`` must not be called."""
        manager = make_syslog_server_manager()
        mock_module.check_mode = True

        with (
            patch.object(manager, "get_syslog_server_by_name", return_value=[]),
            patch.object(manager, "create_syslog_server") as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_not_called()
        assert result["changed"] is True
        assert "would be created" in result["msg"]

    def test_check_mode_reports_update_without_api_call(
        self, make_syslog_server_manager, api_syslog_server_response, mock_module
    ):
        """In check mode, ``update_syslog_server`` must not be called."""
        manager = make_syslog_server_manager()
        mock_module.check_mode = True
        stale = {**api_syslog_server_response, "SYSLOG_INTEGRATION_ADDRESS": "9.9.9.9"}

        with (
            patch.object(manager, "get_syslog_server_by_name", return_value=[stale]),
            patch.object(manager, "update_syslog_server") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is True
        assert "would be updated" in result["msg"]

    def test_check_mode_no_change_when_up_to_date(
        self, make_syslog_server_manager, api_syslog_server_response, mock_module
    ):
        """In check mode, must report no change when server already matches."""
        manager = make_syslog_server_manager()
        mock_module.check_mode = True

        with patch.object(manager, "get_syslog_server_by_name", return_value=[api_syslog_server_response]):
            result = ensure_present(mock_module, manager)

        assert result["changed"] is False
        assert "already up to date" in result["msg"]


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_matching_servers(self, make_syslog_server_manager, api_syslog_server_response, mock_module):
        """When matching servers exist, must delete them and report changed."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="absent",
        )

        with (
            patch.object(manager, "get_syslog_servers", return_value=[api_syslog_server_response]),
            patch.object(manager, "delete_syslog_servers") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once()
        assert result["changed"] is True
        assert "1 syslog server(s)" in result["msg"]

    def test_no_change_when_no_servers_match(self, make_syslog_server_manager, mock_module):
        """When no matching servers exist, must report no change and skip delete."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "nonexistent"}]},
            state="absent",
        )

        with (
            patch.object(manager, "get_syslog_servers", return_value=[]),
            patch.object(manager, "delete_syslog_servers") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_not_called()
        assert result["changed"] is False
        assert "do not exist" in result["msg"]

    def test_check_mode_reports_delete_without_api_call(
        self, make_syslog_server_manager, api_syslog_server_response, mock_module
    ):
        """In check mode, ``delete_syslog_servers`` must not be called."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="absent",
        )
        mock_module.check_mode = True

        with (
            patch.object(manager, "get_syslog_servers", return_value=[api_syslog_server_response]),
            patch.object(manager, "delete_syslog_servers") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_not_called()
        assert result["changed"] is True
        assert "would be deleted" in result["msg"]

    def test_check_mode_no_change_when_no_match(self, make_syslog_server_manager, mock_module):
        """In check mode with no matching servers, must report no change."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "nonexistent"}]},
            state="absent",
        )
        mock_module.check_mode = True

        with patch.object(manager, "get_syslog_servers", return_value=[]):
            result = ensure_absent(mock_module, manager)

        assert result["changed"] is False
        assert "do not exist" in result["msg"]


# ===========================================================================
# gather_syslog_servers
# ===========================================================================


class TestGatherSyslogServers:
    def test_returns_normalised_servers(self, make_syslog_server_manager, api_syslog_server_response):
        """Must return a list of normalised server dicts under ``syslog_servers``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )

        with patch.object(manager, "get_syslog_servers", return_value=[api_syslog_server_response]):
            result = gather_syslog_servers(manager)

        assert result["changed"] is False
        assert len(result["syslog_servers"]) == 1
        expected_server = XSOARSyslogServerManager.normalize_server(api_syslog_server_response)
        assert result["syslog_servers"][0] == expected_server

    def test_reports_no_servers_found_when_empty(self, make_syslog_server_manager):
        """When the API returns no servers, must report a descriptive message."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "nonexistent"}]},
            state="gathered",
        )

        with patch.object(manager, "get_syslog_servers", return_value=[]):
            result = gather_syslog_servers(manager)

        assert result["changed"] is False
        assert result["msg"] == "No syslog servers found."
        assert "syslog_servers" not in result

    def test_never_reports_changed(self, make_syslog_server_manager, api_syslog_server_response):
        """Gather operations must never set ``changed=True``."""
        manager = make_syslog_server_manager(
            request_data={"filters": [{"field": "name", "operator": "eq", "value": "test-syslog"}]},
            state="gathered",
        )

        with patch.object(manager, "get_syslog_servers", return_value=[api_syslog_server_response]):
            result = gather_syslog_servers(manager)

        assert result["changed"] is False
