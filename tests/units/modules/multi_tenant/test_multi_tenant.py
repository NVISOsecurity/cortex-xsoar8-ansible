"""
Unit tests for plugins/modules/multi_tenant.py — XSOARTenantManager and state
functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.multi_tenant import XSOARTenantManager, ensure_absent, ensure_present, gather_tenants
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARTenantManager.__init__ — validation
# ===========================================================================


class TestXSOARTenantManagerInit:
    @pytest.mark.parametrize("field", ["tenant_name", "tenant_subdomain", "initial_user"])
    def test_fails_when_string_field_is_empty_for_present(self, make_multi_tenant_manager, field):
        """
        Any string param set to ``""`` for state=present must cause ``fail_json``
        to be called immediately during initialisation.
        """
        with pytest.raises(AnsibleModuleFail, match=f"Invalid {field}"):
            make_multi_tenant_manager(**{field: ""})

    def test_fails_when_data_retention_is_zero(self, make_multi_tenant_manager):
        """data_retention=0 is not a positive integer and must fail validation."""
        with pytest.raises(AnsibleModuleFail, match="Invalid data_retention"):
            make_multi_tenant_manager(data_retention=0)

    def test_fails_when_data_retention_is_negative(self, make_multi_tenant_manager):
        """Negative data_retention values must fail validation."""
        with pytest.raises(AnsibleModuleFail, match="Invalid data_retention"):
            make_multi_tenant_manager(data_retention=-5)

    def test_fails_when_required_field_is_none_for_present(self, make_multi_tenant_manager):
        """
        Omitting a required present-state field (None) must trigger fail_json
        reporting the missing field.
        """
        with pytest.raises(AnsibleModuleFail, match="state=present is missing required fields"):
            make_multi_tenant_manager(tenant_name=None)

    def test_fails_when_no_identifier_provided_for_absent(self, make_multi_tenant_manager):
        """
        state=absent without any of cortex_id, tenant_name, or tenant_id must
        fail immediately.
        """
        with pytest.raises(AnsibleModuleFail, match="state=absent requires at least one of"):
            make_multi_tenant_manager(
                state="absent",
                cortex_id=None,
                tenant_name=None,
                tenant_id=None,
            )

    def test_fails_when_identifier_is_empty_string_for_absent(self, make_multi_tenant_manager):
        """
        An empty-string identifier for state=absent must fail validation even
        if the other identifiers are also supplied to avoid the API lookup path.
        """
        with pytest.raises(AnsibleModuleFail, match="Invalid cortex_id"):
            make_multi_tenant_manager(
                state="absent",
                cortex_id="",
                tenant_id="tenant-abc123",
            )

    def test_present_builds_correct_prepared_request_data(self, make_multi_tenant_manager):
        """
        After successful initialisation for state=present, prepared_request_data
        must contain all four required fields under the ``request_data`` key.
        """
        manager = make_multi_tenant_manager()
        rd = manager.prepared_request_data["request_data"]

        assert rd["tenant_name"] == "test-tenant"
        assert rd["tenant_subdomain"] == "test-subdomain"
        assert rd["initial_user"] == "admin@example.com"
        assert rd["data_retention"] == 365

    def test_gathered_with_no_identifiers_builds_empty_request_data(self, make_multi_tenant_manager):
        """
        state=gathered with no identifier params must produce an empty
        ``request_data`` dict (no filter — returns all tenants).
        """
        manager = make_multi_tenant_manager(state="gathered", tenant_name=None)
        assert manager.prepared_request_data["request_data"] == {}

    def test_gathered_with_cortex_id_builds_filtered_request_data(self, make_multi_tenant_manager):
        """
        state=gathered with cortex_id must include it in request_data.
        """
        manager = make_multi_tenant_manager(
            state="gathered",
            tenant_name=None,
            cortex_id="cortex-abc123",
        )
        assert manager.prepared_request_data["request_data"] == {"cortex_id": "cortex-abc123"}

    def test_absent_resolves_missing_identifiers_via_api_lookup(
        self, mock_connection, multi_tenant_params, api_tenant_response
    ):
        """
        When only tenant_name is supplied for state=absent, the missing
        cortex_id and tenant_id must be resolved via the API lookup that
        __init__ performs, and the result stored in prepared_request_data.
        """
        mock_connection.request.return_value = {"reply": [api_tenant_response]}
        params = {**multi_tenant_params, "state": "absent"}
        mock_connection.module.params = params

        manager = XSOARTenantManager(mock_connection)

        rd = manager.prepared_request_data["request_data"]
        assert rd["cortex_id"] == "cortex-abc123"
        assert rd["tenant_id"] == "tenant-abc123"
        assert rd["tenant_name"] == "test-tenant"

    def test_absent_stores_partial_data_when_lookup_finds_nothing(self, mock_connection, multi_tenant_params):
        """
        If the API lookup during absent-state init finds no matching tenant,
        __init__ must still succeed and store the partial identifier(s) in
        prepared_request_data so that ensure_absent can handle it with
        changed=False instead of failing here.
        """
        mock_connection.request.return_value = {"reply": []}
        params = {**multi_tenant_params, "state": "absent"}
        mock_connection.module.params = params

        manager = XSOARTenantManager(mock_connection)

        rd = manager.prepared_request_data["request_data"]
        assert rd == {"tenant_name": "test-tenant"}


# ===========================================================================
# XSOARTenantManager.get_tenants
# ===========================================================================


class TestGetTenants:
    def test_returns_tenants_list_from_reply_key(self, make_multi_tenant_manager, api_tenant_response):
        """
        API wraps results in a dict with a ``reply`` key — verify extraction.
        """
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": [api_tenant_response]}

        result = manager.get_tenants()

        assert result == [api_tenant_response]
        manager.connection.request.assert_called_once_with(
            "POST",
            "/public_api/v1/mssp/get_tenants",
            data={"request_data": {}},
        )

    def test_uses_provided_data_argument(self, make_multi_tenant_manager, api_tenant_response):
        """
        When data is explicitly provided, it must be forwarded to the request
        instead of the default ``{"request_data": {}}``.
        """
        manager = make_multi_tenant_manager()
        custom_data = {"request_data": {"tenant_name": "test-tenant"}}
        manager.connection.request.return_value = {"reply": [api_tenant_response]}

        manager.get_tenants(data=custom_data)

        manager.connection.request.assert_called_once_with(
            "POST",
            "/public_api/v1/mssp/get_tenants",
            data=custom_data,
        )

    def test_get_tenants_returns_list_when_not_dict(self, make_multi_tenant_manager, api_tenant_response):
        """
        Non-dict responses (e.g. a raw list) are returned as-is without
        attempting to extract a ``reply`` key.
        """
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = [api_tenant_response]

        result = manager.get_tenants()

        assert result == [api_tenant_response]

    def test_get_tenants_raises_on_request_failure(self, make_multi_tenant_manager):
        """
        Any exception from the connection must be re-raised as XSOARAPIError.
        """
        manager = make_multi_tenant_manager()
        manager.connection.request.side_effect = RuntimeError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to retrieve tenants"):
            manager.get_tenants()


# ===========================================================================
# XSOARTenantManager.get_tenant_by_cortex_id
# ===========================================================================


class TestGetTenantByCortexId:
    def test_finds_tenant_by_cortex_id(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        other = {"cortex_id": "cortex-other", "tenant_name": "other-tenant"}
        manager.connection.request.return_value = {"reply": [other, api_tenant_response]}

        result = manager.get_tenant_by_cortex_id("cortex-abc123")

        assert result == api_tenant_response

    def test_returns_none_when_cortex_id_not_found(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": [{"cortex_id": "cortex-other", "tenant_name": "other"}]}

        assert manager.get_tenant_by_cortex_id("cortex-abc123") is None

    def test_returns_none_on_empty_list_for_cortex_id(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": []}

        assert manager.get_tenant_by_cortex_id("cortex-abc123") is None

    def test_returns_none_when_get_tenants_returns_falsy(self, make_multi_tenant_manager):
        """
        When get_tenants() returns a falsy value (e.g. None or empty list
        passed through a non-dict response path), the lookup must return None.
        """
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": None}

        assert manager.get_tenant_by_cortex_id("cortex-abc123") is None


# ===========================================================================
# XSOARTenantManager.get_tenant_by_tenant_id
# ===========================================================================


class TestGetTenantByTenantId:
    def test_finds_tenant_by_tenant_id(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": [api_tenant_response]}

        result = manager.get_tenant_by_tenant_id("tenant-abc123")

        assert result == api_tenant_response

    def test_returns_none_when_tenant_id_not_found(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": [{"tenant_id": "tenant-other", "tenant_name": "other"}]}

        assert manager.get_tenant_by_tenant_id("tenant-abc123") is None

    def test_returns_none_on_empty_list_for_tenant_id(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": []}

        assert manager.get_tenant_by_tenant_id("tenant-abc123") is None


# ===========================================================================
# XSOARTenantManager.get_tenant_by_name
# ===========================================================================


class TestGetTenantByName:
    def test_finds_tenant_by_name(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        other = {"tenant_id": "tenant-other", "tenant_name": "other-tenant"}
        manager.connection.request.return_value = {"reply": [other, api_tenant_response]}

        result = manager.get_tenant_by_name("test-tenant")

        assert result == api_tenant_response

    def test_returns_none_when_name_not_found(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": [{"tenant_id": "x", "tenant_name": "other"}]}

        assert manager.get_tenant_by_name("test-tenant") is None

    def test_returns_none_on_empty_response(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": []}

        assert manager.get_tenant_by_name("test-tenant") is None


# ===========================================================================
# XSOARTenantManager.create_tenant
# ===========================================================================


class TestCreateTenant:
    def test_create_posts_to_correct_endpoint(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": api_tenant_response}

        manager.create_tenant()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/mssp/create_child"

    def test_create_payload_matches_prepared_request_data(self, make_multi_tenant_manager, api_tenant_response):
        """
        The full ``prepared_request_data`` dict (including the ``request_data``
        wrapper key) must be forwarded verbatim as the request payload.
        """
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": api_tenant_response}

        manager.create_tenant()

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == manager.prepared_request_data

    def test_returns_created_tenant_from_reply_key(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = {"reply": api_tenant_response}

        result = manager.create_tenant()

        assert result == api_tenant_response

    def test_create_returns_response_when_not_dict(self, make_multi_tenant_manager, api_tenant_response):
        manager = make_multi_tenant_manager()
        manager.connection.request.return_value = [api_tenant_response]

        result = manager.create_tenant()

        assert result == [api_tenant_response]

    def test_create_raises_on_request_failure(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager()
        manager.connection.request.side_effect = Exception("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to create Tenant"):
            manager.create_tenant()


# ===========================================================================
# XSOARTenantManager.delete_tenant
# ===========================================================================


class TestDeleteTenant:
    def test_delete_posts_to_correct_endpoint(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        manager.connection.request.return_value = {"reply": True}

        manager.delete_tenant()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/mssp/delete_child"

    def test_delete_payload_matches_prepared_request_data(self, make_multi_tenant_manager):
        """
        The full ``prepared_request_data`` dict must be forwarded to the
        delete endpoint, containing all resolved identifiers.
        """
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        manager.connection.request.return_value = {"reply": True}

        manager.delete_tenant()

        _, kwargs = manager.connection.request.call_args
        assert kwargs["data"] == manager.prepared_request_data

    def test_returns_delete_result_from_reply_key(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        manager.connection.request.return_value = {"reply": True}

        result = manager.delete_tenant()

        assert result

    def test_delete_returns_response_when_not_dict(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        manager.connection.request.return_value = True

        result = manager.delete_tenant()

        assert result

    def test_delete_raises_on_request_failure(self, make_multi_tenant_manager):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        manager.connection.request.side_effect = Exception("forbidden")

        with pytest.raises(XSOARAPIError, match="Failed to delete Tenant"):
            manager.delete_tenant()


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_tenant_when_absent(self, make_multi_tenant_manager, api_tenant_response, mock_module):
        manager = make_multi_tenant_manager()

        with (
            patch.object(manager, "get_tenant_by_name", return_value=None),
            patch.object(manager, "create_tenant", return_value=api_tenant_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Tenant created successfully."

    def test_no_change_when_tenant_already_exists(self, make_multi_tenant_manager, api_tenant_response, mock_module):
        """
        When get_tenant_by_name returns an existing tenant, no create call
        must be made and changed must be False.
        """
        manager = make_multi_tenant_manager()

        with (
            patch.object(manager, "get_tenant_by_name", return_value=api_tenant_response),
            patch.object(manager, "create_tenant") as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_not_called()
        assert not result["changed"]
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Tenant already exists with the provided name."

    def test_check_mode_reports_create_without_calling_api(self, make_multi_tenant_manager, mock_module):
        manager = make_multi_tenant_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_tenant_by_name", return_value=None),
            patch.object(manager, "create_tenant") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["tenant"] == manager.prepared_request_data["request_data"]
        assert result["msg"] == "Tenant would be created with the provided information."

    def test_check_mode_no_change_when_tenant_already_exists(
        self, make_multi_tenant_manager, api_tenant_response, mock_module
    ):
        """
        In check mode, when the tenant already exists, the result is identical
        to the non-check-mode path — no create and changed=False.
        """
        manager = make_multi_tenant_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_tenant_by_name", return_value=api_tenant_response),
            patch.object(manager, "create_tenant") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert not result["changed"]
        assert result["tenant"] == api_tenant_response


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_tenant(self, make_multi_tenant_manager, api_tenant_response, mock_module):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )

        with (
            patch.object(manager, "get_tenant_by_cortex_id", return_value=api_tenant_response),
            patch.object(manager, "delete_tenant", return_value=True) as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once()
        assert result["changed"]
        assert result["deleted"]
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Tenant deleted successfully."

    def test_check_mode_reports_would_delete_without_calling_api(
        self, make_multi_tenant_manager, api_tenant_response, mock_module
    ):
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_tenant_by_cortex_id", return_value=api_tenant_response),
            patch.object(manager, "delete_tenant") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == "Tenant would be deleted."
        assert result["tenant"] == api_tenant_response

    def test_no_change_when_tenant_does_not_exist(self, make_multi_tenant_manager, mock_module):
        """
        When the existence check in ensure_absent finds no matching tenant,
        changed must be False and delete_tenant must never be called.
        """
        manager = make_multi_tenant_manager(
            state="absent",
            cortex_id="cortex-abc123",
            tenant_id="tenant-abc123",
        )

        with (
            patch.object(manager, "get_tenant_by_cortex_id", return_value=None),
            patch.object(manager, "delete_tenant") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_not_called()
        assert not result["changed"]
        assert "does not exist" in result["msg"]


# ===========================================================================
# gather_tenants
# ===========================================================================


class TestGatherTenants:
    def test_returns_all_tenants_when_no_filter(self, make_multi_tenant_manager, api_tenant_response):
        """
        When no identifier params are provided, filter_data is empty and
        get_tenants() is called without a filter, returning all tenants.
        """
        manager = make_multi_tenant_manager(state="gathered", tenant_name=None)

        with patch.object(manager, "get_tenants", return_value=[api_tenant_response]) as mock_get:
            result = gather_tenants(manager)

        mock_get.assert_called_once()
        assert result["tenants"] == [api_tenant_response]
        assert result["msg"] == "No filter provided, returning all tenants."

    def test_returns_tenant_by_cortex_id_filter(self, make_multi_tenant_manager, api_tenant_response):
        """
        cortex_id is checked first in the lookup priority order.
        """
        manager = make_multi_tenant_manager(
            state="gathered",
            tenant_name=None,
            cortex_id="cortex-abc123",
        )

        with patch.object(manager, "get_tenant_by_cortex_id", return_value=api_tenant_response) as mock_lookup:
            result = gather_tenants(manager)

        mock_lookup.assert_called_once_with("cortex-abc123")
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Retrieved tenant by cortex_id filter."

    def test_returns_tenant_by_tenant_name_filter(self, make_multi_tenant_manager, api_tenant_response):
        """
        tenant_name lookup is used when cortex_id is absent from the filter.
        """
        manager = make_multi_tenant_manager(state="gathered", tenant_name="test-tenant")

        with patch.object(manager, "get_tenant_by_name", return_value=api_tenant_response) as mock_lookup:
            result = gather_tenants(manager)

        mock_lookup.assert_called_once_with("test-tenant")
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Retrieved tenant by tenant_name filter."

    def test_returns_tenant_by_tenant_id_filter(self, make_multi_tenant_manager, api_tenant_response):
        """
        tenant_id lookup is used when neither cortex_id nor tenant_name is in
        the filter.
        """
        manager = make_multi_tenant_manager(
            state="gathered",
            tenant_name=None,
            tenant_id="tenant-abc123",
        )

        with patch.object(manager, "get_tenant_by_tenant_id", return_value=api_tenant_response) as mock_lookup:
            result = gather_tenants(manager)

        mock_lookup.assert_called_once_with("tenant-abc123")
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Retrieved tenant by tenant_id filter."

    def test_returns_none_when_no_tenant_matches_filter(self, make_multi_tenant_manager):
        """
        When a filter is supplied but no tenant matches any lookup, the result
        must carry ``tenant=None`` with an appropriate message.
        """
        manager = make_multi_tenant_manager(
            state="gathered",
            tenant_name=None,
            cortex_id="cortex-abc123",
        )

        with patch.object(manager, "get_tenant_by_cortex_id", return_value=None):
            result = gather_tenants(manager)

        assert result["tenant"] is None
        assert "No tenant found" in result["msg"]

    def test_cortex_id_takes_priority_over_tenant_name(self, make_multi_tenant_manager, api_tenant_response):
        """
        When both cortex_id and tenant_name are provided, cortex_id lookup
        must be performed first and tenant_name must never be called.
        """
        manager = make_multi_tenant_manager(
            state="gathered",
            cortex_id="cortex-abc123",
            tenant_name="test-tenant",
        )

        with (
            patch.object(manager, "get_tenant_by_cortex_id", return_value=api_tenant_response) as mock_cortex,
            patch.object(manager, "get_tenant_by_name") as mock_name,
        ):
            result = gather_tenants(manager)

        mock_cortex.assert_called_once_with("cortex-abc123")
        mock_name.assert_not_called()
        assert result["tenant"] == api_tenant_response
        assert result["msg"] == "Retrieved tenant by cortex_id filter."
