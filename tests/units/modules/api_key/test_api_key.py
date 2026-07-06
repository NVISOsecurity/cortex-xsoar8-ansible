"""
Unit tests for plugins/modules/api_key.py — XSOARApiKeyManager and state
functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.

Key differences from other modules
-----------------------------------
- All method-level errors call ``fail_json`` (not raise ``XSOARAPIError``).
  Trigger: ``connection.request.side_effect = XSOARAPIError(...)``
  Expect:  ``pytest.raises(AnsibleModuleFail, match=...)``
- ``update_api_key`` is intentionally excluded from tests (left for later).
- ``ensure_present`` may report no change when a key with the same comment already exists.
- ``ensure_absent`` reports changes based on the count returned by
  ``delete_api_key()``, not by querying existing state first (except in check mode).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.api_key import XSOARApiKeyManager, ensure_absent, ensure_present, gather_api_keys
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARApiKeyManager — validation in __init__
# ===========================================================================


class TestXSOARApiKeyManagerValidation:
    def test_fails_when_present_state_receives_filters(self, make_api_key_manager):
        """
        ``state=present`` supports only direct fields; supplying ``filters``
        must trigger ``fail_json`` immediately during initialisation.
        """
        with pytest.raises(AnsibleModuleFail, match="state=present does not support request_data.filters"):
            make_api_key_manager(
                request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
                state="present",
            )

    def test_fails_when_absent_state_receives_direct_fields(self, make_api_key_manager):
        """
        ``state=absent`` supports only filters; supplying direct fields
        must trigger ``fail_json``.
        """
        with pytest.raises(
            AnsibleModuleFail,
            match="state=absent or state=gathered do not support direct request_data fields",
        ):
            make_api_key_manager(request_data={"roles": ["Admin"]}, state="absent")

    def test_fails_when_gathered_state_receives_direct_fields(self, make_api_key_manager):
        """``state=gathered`` also rejects direct fields — same rule as absent."""
        with pytest.raises(
            AnsibleModuleFail,
            match="state=absent or state=gathered do not support direct request_data fields",
        ):
            make_api_key_manager(request_data={"security_level": "standard"}, state="gathered")

    def test_fails_when_both_filters_and_direct_fields_provided(self, make_api_key_manager):
        """
        Mixing ``filters`` with direct fields in a single ``request_data``
        dict must be rejected regardless of state.
        """
        with pytest.raises(AnsibleModuleFail, match="request_data must contain either"):
            make_api_key_manager(
                request_data={
                    "filters": [{"field": "id", "operator": "in", "value": [1]}],
                    "roles": ["Admin"],
                },
                state="present",
            )

    def test_prepared_request_data_set_after_valid_direct_fields(self, make_api_key_manager):
        """
        A valid ``state=present`` manager must expose ``prepared_request_data``
        wrapping the normalised direct fields.
        """
        manager = make_api_key_manager()

        assert manager.prepared_request_data == {"request_data": {"roles": ["Admin"], "security_level": "standard"}}

    def test_prepared_request_data_set_after_valid_filters(self, make_api_key_manager):
        """
        A valid filter-based manager must expose ``prepared_request_data``
        wrapping the normalised filters.
        """
        filters = [{"field": "id", "operator": "in", "value": [1, 2]}]
        manager = make_api_key_manager(request_data={"filters": filters}, state="absent")

        assert manager.prepared_request_data == {"request_data": {"filters": filters}}

    def test_no_prepared_request_data_when_request_data_is_none(self, make_api_key_manager):
        """
        When ``request_data`` is ``None`` (or empty), ``validate_request_data``
        is skipped and ``prepared_request_data`` is never set on the manager.
        """
        manager = make_api_key_manager(request_data=None, state="gathered")

        assert not hasattr(manager, "prepared_request_data")


# ===========================================================================
# Static helpers
# ===========================================================================


class TestStaticHelpers:
    def test_get_today_epoch_ms_returns_midnight_utc(self):
        """
        ``get_today_epoch_ms`` must return today's date at exactly 00:00:00 UTC
        expressed as epoch milliseconds.
        """
        result = XSOARApiKeyManager.get_today_epoch_ms()
        today_midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        expected = int(today_midnight.timestamp() * 1000)
        assert result == expected


# ===========================================================================
# XSOARApiKeyManager.get_api_keys
# ===========================================================================


class TestGetApiKeys:
    def test_posts_to_correct_endpoint(self, make_api_key_manager, api_key_response):
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"DATA": [api_key_response]}}

        manager.get_api_keys()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/api_keys/get_api_keys"

    def test_returns_api_keys_from_data_key(self, make_api_key_manager, api_key_response):
        """
        API wraps results in ``reply.DATA`` — verify correct extraction.
        """
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"DATA": [api_key_response]}}

        result = manager.get_api_keys()

        assert result == [api_key_response]

    def test_returns_empty_list_when_response_is_not_dict(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.return_value = []

        assert manager.get_api_keys() == []

    def test_uses_default_expiration_filter_when_no_request_data(self, make_api_key_manager):
        """
        When ``request_data`` is ``None``, ``get_api_keys`` must fall back to
        a default filter on the ``expiration`` field (``gte`` today).  The
        filter value is pinned via a patched ``get_today_epoch_ms`` so the
        assertion is deterministic.
        """
        manager = make_api_key_manager(request_data=None, state="gathered")
        manager.connection.request.return_value = {"reply": {"DATA": []}}
        fixed_epoch_ms = 1_747_267_200_000

        with patch.object(XSOARApiKeyManager, "get_today_epoch_ms", return_value=fixed_epoch_ms):
            manager.get_api_keys()

        call_data = manager.connection.request.call_args.kwargs["data"]
        filters = call_data["request_data"]["filters"]
        assert len(filters) == 1
        assert filters[0]["field"] == "expiration"
        assert filters[0]["operator"] == "gte"
        assert filters[0]["value"] == fixed_epoch_ms

    def test_uses_prepared_request_data_when_request_data_provided(self, make_api_key_manager, api_key_response):
        """
        When manager-level ``request_data`` exists, callers should pass
        ``prepared_request_data`` explicitly to ``get_api_keys`` and that
        payload must be forwarded unchanged to the API request.
        """
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"DATA": [api_key_response]}}

        manager.get_api_keys(manager.prepared_request_data)

        call_data = manager.connection.request.call_args.kwargs["data"]
        assert call_data == manager.prepared_request_data

    def test_calls_fail_json_on_request_failure(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(AnsibleModuleFail, match="Failed to retrieve API keys"):
            manager.get_api_keys()

    def test_explicit_request_data_argument_overrides_manager_request_data(
        self, make_api_key_manager, api_key_response
    ):
        """
        If an explicit ``request_data`` argument is provided, it must take
        precedence over manager-level ``prepared_request_data``.
        """
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"DATA": [api_key_response]}}
        explicit_request_data = {
            "request_data": {
                "filters": [
                    {
                        "field": "id",
                        "operator": "in",
                        "value": [999],
                    }
                ]
            }
        }

        manager.get_api_keys(explicit_request_data)

        call_data = manager.connection.request.call_args.kwargs["data"]
        assert call_data == explicit_request_data


# ===========================================================================
# XSOARApiKeyManager.create_api_key
# ===========================================================================


class TestCreateApiKey:
    def test_posts_to_correct_endpoint(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"id": 1, "key": "abc123"}}

        manager.create_api_key()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/api_keys/generate"

    def test_sends_prepared_request_data_as_payload(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.return_value = {"reply": {"id": 1, "key": "abc123"}}

        manager.create_api_key()

        call_data = manager.connection.request.call_args.kwargs["data"]
        assert call_data == manager.prepared_request_data

    def test_returns_reply_dict_from_response(self, make_api_key_manager):
        """
        ``create_api_key`` must extract and return ``response["reply"]``
        which contains the new key's ``id`` and plaintext ``key`` value.
        """
        manager = make_api_key_manager()
        created = {"id": 1, "key": "abc123"}
        manager.connection.request.return_value = {"reply": created}

        result = manager.create_api_key()

        assert result == created

    def test_returns_empty_dict_when_response_is_not_dict(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.return_value = []

        assert manager.create_api_key() == {}

    def test_calls_fail_json_on_request_failure(self, make_api_key_manager):
        manager = make_api_key_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(AnsibleModuleFail, match="Failed to create API key"):
            manager.create_api_key()


# ===========================================================================
# XSOARApiKeyManager.delete_api_key
# ===========================================================================


class TestDeleteApiKey:
    def test_posts_to_delete_endpoint(self, make_api_key_manager):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="absent",
        )
        manager.connection.request.return_value = {"reply": {"update_count": 1}}

        manager.delete_api_key()

        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/public_api/v1/api_keys/delete"

    def test_sends_prepared_request_data_as_payload(self, make_api_key_manager):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="absent",
        )
        manager.connection.request.return_value = {"reply": {"update_count": 1}}

        manager.delete_api_key()

        call_data = manager.connection.request.call_args.kwargs["data"]
        assert call_data == manager.prepared_request_data

    def test_returns_update_count_from_response(self, make_api_key_manager):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1, 2]}]},
            state="absent",
        )
        manager.connection.request.return_value = {"reply": {"update_count": 2}}

        assert manager.delete_api_key() == 2

    def test_calls_fail_json_on_request_failure(self, make_api_key_manager):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="absent",
        )
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to delete API key"):
            manager.delete_api_key()


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_api_key(self, make_api_key_manager, mock_module):
        manager = make_api_key_manager()
        created = {"id": 5, "key": "secret-value"}

        with patch.object(manager, "create_api_key", return_value=created) as mock_create:
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == "Api key with ID 5 created"
        assert result["api_key"] == created

    def test_check_mode_reports_create_without_calling_api(self, make_api_key_manager, mock_module):
        """
        Check mode must project an API-shaped result (flat dict with ``id`` and
        ``key`` placeholders alongside the requested direct fields) so callers
        see the same keys as in real mode.
        """
        manager = make_api_key_manager()
        module = mock_module(check_mode=True)
        expected_api_key = {
            "id": None,
            "key": None,
            **manager.prepared_request_data["request_data"],
        }

        with patch.object(manager, "create_api_key") as mock_create:
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == "Api key would be created"
        assert result["api_key"] == expected_api_key

    def test_reports_no_change_when_comment_already_exists(self, make_api_key_manager, mock_module):
        manager = make_api_key_manager(
            request_data={"roles": ["Admin"], "security_level": "standard", "comment": "dup"}
        )

        with (
            patch.object(manager, "get_api_keys", return_value=[{"comment": "dup"}]) as mock_get,
            patch.object(manager, "create_api_key") as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_get.assert_called_once_with()
        mock_create.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == 'Api key with comment "dup" already exists'


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_api_keys_and_reports_count(self, make_api_key_manager, api_key_response, mock_module):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1, 2]}]},
            state="absent",
        )

        with (
            patch.object(manager, "get_api_keys", return_value=[api_key_response, api_key_response]),
            patch.object(manager, "delete_api_key", return_value=2) as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once()
        assert result["changed"]
        assert result["msg"] == "2 Api key(s) with ID(s) [1, 2] deleted"

    def test_reports_no_change_when_delete_count_is_zero(self, make_api_key_manager, mock_module):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [99]}]},
            state="absent",
        )

        with (
            patch.object(manager, "get_api_keys", return_value=[]),
            patch.object(manager, "delete_api_key") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == "Api key(s) with ID(s) [99] do not exist"

    def test_check_mode_reports_delete_when_keys_exist(self, make_api_key_manager, api_key_response, mock_module):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="absent",
        )
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_api_keys", return_value=[api_key_response]),
            patch.object(manager, "delete_api_key") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == "Api key(s) with ID(s) [1] would be deleted"

    def test_check_mode_reports_no_change_when_keys_absent(self, make_api_key_manager, mock_module):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="absent",
        )
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_api_keys", return_value=[]),
            patch.object(manager, "delete_api_key") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == "Api key(s) with ID(s) [1] do not exist"


# ===========================================================================
# gather_api_keys
# ===========================================================================


class TestGatherApiKeys:
    def test_uses_prepared_request_data_when_filters_provided(self, make_api_key_manager, api_key_response):
        manager = make_api_key_manager(
            request_data={"filters": [{"field": "id", "operator": "in", "value": [1]}]},
            state="gathered",
        )

        with patch.object(manager, "get_api_keys", return_value=[api_key_response]) as mock_get:
            result = gather_api_keys(manager)

        mock_get.assert_called_once_with(manager.prepared_request_data)
        assert not result["changed"]
        assert result["api_keys"] == [api_key_response]
        assert result["msg"] == "Retrieved 1 API keys."

    def test_returns_api_keys_when_found(self, make_api_key_manager, api_key_response):
        manager = make_api_key_manager(request_data=None, state="gathered")

        with patch.object(manager, "get_api_keys", return_value=[api_key_response]) as mock_get:
            result = gather_api_keys(manager)

        mock_get.assert_called_once_with()
        assert not result["changed"]
        assert result["api_keys"] == [api_key_response]
        assert result["msg"] == "Retrieved 1 API keys."

    def test_reports_no_keys_found_when_list_is_empty(self, make_api_key_manager):
        """
        When ``get_api_keys`` returns an empty list the result must not include
        an ``api_keys`` key — only the "not found" message.
        """
        manager = make_api_key_manager(request_data=None, state="gathered")

        with patch.object(manager, "get_api_keys", return_value=[]):
            result = gather_api_keys(manager)

        assert not result["changed"]
        assert result["msg"] == "No API keys found."
        assert "api_keys" not in result
