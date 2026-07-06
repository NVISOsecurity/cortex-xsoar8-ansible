"""
Unit tests for plugins/modules/credential.py — XSOARCredentialManager and state
functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.credential import ensure_absent, ensure_present, gather_credentials
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# XSOARCredentialManager.__init__ — validation
# ===========================================================================


class TestXSOARCredentialManagerInit:
    @pytest.mark.parametrize("field", ["name", "username", "password", "certificate", "workgroup"])
    def test_fails_when_field_is_empty_string(self, make_credential_manager, field):
        """
        Any param that resolves to ``""`` must cause ``fail_json`` to be called
        immediately during initialisation, before any API call is made.
        """
        with pytest.raises(AnsibleModuleFail, match=f"'{field}' cannot be an empty string"):
            make_credential_manager(**{field: ""})


# ===========================================================================
# XSOARCredentialManager.get_all_credentials
# ===========================================================================


class TestGetAllCredentials:
    def test_returns_credentials_from_response(self, make_credential_manager, api_credential_response):
        """
        API wraps results in a dict with a ``credentials`` key — verify extraction.
        """
        manager = make_credential_manager()
        manager.connection.request.return_value = {"credentials": [api_credential_response]}

        result = manager.get_all_credentials()

        assert result == [api_credential_response]
        manager.connection.request.assert_called_once_with("POST", "/settings/credentials")

    def test_returns_empty_list_when_credentials_key_is_absent(self, make_credential_manager):
        """
        A dict response without a ``credentials`` key should yield an empty list.
        """
        manager = make_credential_manager()
        manager.connection.request.return_value = {}

        assert manager.get_all_credentials() == []

    def test_returns_empty_list_when_response_is_not_dict(self, make_credential_manager):
        """
        Non-dict responses must be normalised to ``[]``.
        """
        manager = make_credential_manager()
        manager.connection.request.return_value = []

        assert manager.get_all_credentials() == []

    def test_raises_on_request_failure(self, make_credential_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`.
        """
        manager = make_credential_manager()
        manager.connection.request.side_effect = RuntimeError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get credentials"):
            manager.get_all_credentials()


# ===========================================================================
# XSOARCredentialManager.get_credential_by_name
# ===========================================================================


class TestGetCredentialByName:
    def test_returns_matching_credential(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager()
        other = {"id": "other-id", "name": "other-credential"}
        manager.connection.request.return_value = {"credentials": [other, api_credential_response]}

        result = manager.get_credential_by_name("test-credential")

        assert result == api_credential_response

    def test_returns_none_when_not_found(self, make_credential_manager):
        manager = make_credential_manager()
        manager.connection.request.return_value = {"credentials": [{"id": "x", "name": "other"}]}

        assert manager.get_credential_by_name("test-credential") is None

    def test_returns_none_on_empty_response(self, make_credential_manager):
        manager = make_credential_manager()
        manager.connection.request.return_value = {"credentials": []}

        assert manager.get_credential_by_name("test-credential") is None


# ===========================================================================
# XSOARCredentialManager.create_credential
# ===========================================================================


class TestCreateCredential:
    def test_puts_to_correct_endpoint(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager()
        manager.connection.request.return_value = api_credential_response

        result = manager.create_credential()

        assert result == api_credential_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "PUT"
        assert args[1] == "/settings/credentials"

    def test_payload_includes_name_and_non_none_fields_only(self, make_credential_manager, api_credential_response):
        """
        Optional secret fields (``sshkey``, ``password``, ``workgroup``) must
        be omitted from the payload when they are ``None`` — only ``name`` and
        the non-``None`` optional fields are sent.
        """
        manager = make_credential_manager(username="test-user", password=None, certificate=None, workgroup=None)
        manager.connection.request.return_value = api_credential_response

        manager.create_credential()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["name"] == "test-credential"
        assert payload["user"] == "test-user"
        assert "password" not in payload
        assert "sshkey" not in payload
        assert "workgroup" not in payload

    def test_payload_includes_password_when_set(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager(password="secret")
        manager.connection.request.return_value = api_credential_response

        manager.create_credential()

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["password"] == "secret"

    def test_raises_on_request_failure(self, make_credential_manager):
        manager = make_credential_manager()
        manager.connection.request.side_effect = Exception("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to create credential"):
            manager.create_credential()


# ===========================================================================
# XSOARCredentialManager.update_credential
# ===========================================================================


class TestUpdateCredential:
    def test_puts_to_correct_endpoint(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager()
        manager.connection.request.return_value = api_credential_response

        result = manager.update_credential(api_credential_response)

        assert result == api_credential_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "PUT"
        assert args[1] == "/settings/credentials"

    def test_payload_structure(self, make_credential_manager, api_credential_response):
        """
        Update payload must carry ``version: -1``, the existing ``id``, and
        merge module params with current credential values as fallbacks.
        """
        manager = make_credential_manager(username="new-user", workgroup="new-group")
        manager.connection.request.return_value = api_credential_response

        manager.update_credential(api_credential_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["version"] == -1
        assert payload["id"] == "cred-abc123"
        assert payload["user"] == "new-user"
        assert payload["workgroup"] == "new-group"
        assert payload["name"] == "test-credential"

    def test_falls_back_to_existing_values_when_params_are_none(self, make_credential_manager, api_credential_response):
        """
        When module params are ``None``, the update payload must fall back to
        whatever the current credential already has.
        """
        existing = {**api_credential_response, "user": "existing-user", "workgroup": "existing-group"}
        manager = make_credential_manager(username=None, workgroup=None)
        manager.connection.request.return_value = api_credential_response

        manager.update_credential(existing)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["user"] == "existing-user"
        assert payload["workgroup"] == "existing-group"
        assert payload["name"] == "test-credential"  # name is not None, so no fallback needed

    def test_raises_on_request_failure(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager()
        manager.connection.request.side_effect = Exception("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to update credential"):
            manager.update_credential(api_credential_response)

    def test_omits_password_and_preserves_has_password_when_not_supplied(
        self, make_credential_manager, api_credential_response
    ):
        """
        When the caller does not supply ``password``, the update payload must
        omit the ``password`` key entirely and derive ``hasPassword`` from the
        current credential — otherwise the server would silently clear the
        existing secret, since the GET response always masks password to
        ``None``.
        """
        existing = {**api_credential_response, "user": "old-user", "hasPassword": True}
        manager = make_credential_manager(username="new-user", password=None, certificate=None)
        manager.connection.request.return_value = api_credential_response

        manager.update_credential(existing)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert "password" not in payload
        assert "sshkey" not in payload
        assert payload["hasPassword"] is True
        assert payload["hasCertificate"] is False

    def test_includes_password_and_sets_has_password_true_when_supplied(
        self, make_credential_manager, api_credential_response
    ):
        """When a new password is supplied, it is sent and hasPassword is set to True."""
        existing = {**api_credential_response, "hasPassword": False}
        manager = make_credential_manager(password="new-secret", certificate=None)
        manager.connection.request.return_value = api_credential_response

        manager.update_credential(existing)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["password"] == "new-secret"
        assert payload["hasPassword"] is True
        assert "sshkey" not in payload
        assert payload["hasCertificate"] is False

    def test_includes_certificate_and_sets_has_certificate_true_when_supplied(
        self, make_credential_manager, api_credential_response
    ):
        existing = {**api_credential_response, "hasCertificate": False}
        manager = make_credential_manager(password=None, certificate="ssh-key-material")
        manager.connection.request.return_value = api_credential_response

        manager.update_credential(existing)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["sshkey"] == "ssh-key-material"
        assert payload["hasCertificate"] is True
        assert "password" not in payload


# ===========================================================================
# XSOARCredentialManager.delete_credential
# ===========================================================================


class TestDeleteCredential:
    def test_posts_to_delete_endpoint_with_id(self, make_credential_manager):
        manager = make_credential_manager(state="absent")
        manager.connection.request.return_value = {}

        manager.delete_credential("cred-abc123")

        manager.connection.request.assert_called_once_with(
            "POST",
            "/settings/credentials/delete",
            {"id": "cred-abc123"},
        )

    def test_returns_true_on_success(self, make_credential_manager):
        manager = make_credential_manager(state="absent")
        manager.connection.request.return_value = {}

        assert manager.delete_credential("cred-abc123")

    def test_raises_on_request_failure(self, make_credential_manager):
        manager = make_credential_manager(state="absent")
        manager.connection.request.side_effect = Exception("forbidden")

        with pytest.raises(XSOARAPIError, match="Failed to delete credential"):
            manager.delete_credential("cred-abc123")


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_credential_when_absent(self, make_credential_manager, api_credential_response, mock_module):
        manager = make_credential_manager()

        with (
            patch.object(manager, "get_credential_by_name", return_value=None),
            patch.object(manager, "create_credential", return_value=api_credential_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == f"Credential {api_credential_response['name']} created successfully"
        assert result["credential"] == api_credential_response

    def test_updates_credential_when_username_differs(
        self, make_credential_manager, api_credential_response, mock_module
    ):
        manager = make_credential_manager()
        stale = {**api_credential_response, "user": "old-user"}

        with (
            patch.object(manager, "get_credential_by_name", return_value=stale),
            patch.object(manager, "update_credential", return_value=api_credential_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(current_credential=stale)
        assert result["changed"]
        assert result["msg"] == f"Credential {api_credential_response['name']} updated successfully"
        assert result["credential"] == api_credential_response

    def test_no_change_when_credential_is_up_to_date(
        self, make_credential_manager, api_credential_response, mock_module
    ):
        """
        ``api_credential_response`` matches ``credential_params`` defaults —
        no update expected.
        """
        manager = make_credential_manager()

        with (
            patch.object(manager, "get_credential_by_name", return_value=api_credential_response),
            patch.object(manager, "update_credential") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"Credential {api_credential_response['name']} is already up to date"
        assert result["credential"] == api_credential_response

    def test_check_mode_reports_create_without_calling_api(
        self, make_credential_manager, api_credential_response, mock_module
    ):
        manager = make_credential_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_credential_by_name", return_value=None),
            patch.object(manager, "create_credential") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Credential {manager.name} would be created"

    def test_check_mode_reports_update_without_calling_api(
        self, make_credential_manager, api_credential_response, mock_module
    ):
        manager = make_credential_manager()
        module = mock_module(check_mode=True)
        stale = {**api_credential_response, "user": "old-user"}

        with (
            patch.object(manager, "get_credential_by_name", return_value=stale),
            patch.object(manager, "update_credential") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Credential {manager.name} would be updated"

    def test_check_mode_no_change_when_up_to_date(self, make_credential_manager, api_credential_response, mock_module):
        manager = make_credential_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_credential_by_name", return_value=api_credential_response):
            result = ensure_present(module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Credential {manager.name} is already up to date (check mode)"


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_existing_credential(self, make_credential_manager, api_credential_response, mock_module):
        manager = make_credential_manager(state="absent")

        with (
            patch.object(manager, "get_credential_by_name", return_value=api_credential_response),
            patch.object(manager, "delete_credential") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_credential_response["id"])
        assert result["changed"]
        assert result["msg"] == (
            f"Credential {api_credential_response['name']} with ID {api_credential_response['id']} deleted successfully"
        )
        assert result["credential"] == api_credential_response

    def test_no_change_when_credential_already_absent(self, make_credential_manager, mock_module):
        manager = make_credential_manager(state="absent")

        with patch.object(manager, "get_credential_by_name", return_value=None):
            result = ensure_absent(mock_module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Credential {manager.name} does not exist"
        assert "credential" not in result

    def test_check_mode_reports_delete_without_calling_api(
        self, make_credential_manager, api_credential_response, mock_module
    ):
        manager = make_credential_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_credential_by_name", return_value=api_credential_response),
            patch.object(manager, "delete_credential") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Credential {manager.name} would be deleted"


# ===========================================================================
# gather_credentials
# ===========================================================================


class TestGatherCredentials:
    def test_returns_named_credential_when_found(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager(state="gathered")

        with patch.object(manager, "get_credential_by_name", return_value=api_credential_response):
            result = gather_credentials(manager)

        assert not result["changed"]
        assert result["credential"] == api_credential_response
        assert result["msg"] == f"Credential {manager.name} found"

    def test_reports_not_found_for_missing_named_credential(self, make_credential_manager):
        manager = make_credential_manager(state="gathered")

        with patch.object(manager, "get_credential_by_name", return_value=None):
            result = gather_credentials(manager)

        assert not result["changed"]
        assert result["msg"] == f"Credential {manager.name} not found"
        assert "credential" not in result

    def test_returns_all_credentials_when_name_is_none(self, make_credential_manager, api_credential_response):
        manager = make_credential_manager(name=None, state="gathered")

        with patch.object(manager, "get_all_credentials", return_value=[api_credential_response]) as mock_get:
            result = gather_credentials(manager)

        mock_get.assert_called_once_with()
        assert not result["changed"]
        assert result["credentials"] == [api_credential_response]
        assert result["msg"] == "Retrieved 1 credentials"

    def test_returns_empty_list_when_no_credentials(self, make_credential_manager):
        """
        ``gather_credentials`` always sets ``result["credentials"]`` even when
        the list is empty — there is no early-exit branch for the all-credentials path.
        """
        manager = make_credential_manager(name=None, state="gathered")

        with patch.object(manager, "get_all_credentials", return_value=[]):
            result = gather_credentials(manager)

        assert not result["changed"]
        assert result["credentials"] == []
        assert result["msg"] == "Retrieved 0 credentials"
