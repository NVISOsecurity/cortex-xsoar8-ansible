"""
Unit tests for plugins/modules/server_settings.py — XSOARServerSettingsManager
and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.server_settings import ensure_absent, ensure_present, gather_server_settings

# ===========================================================================
# XSOARServerSettingsManager.prepare_server_settings_data
# ===========================================================================


class TestPrepareServerSettingsData:
    def test_wraps_data_with_version_minus_one(self, make_server_settings_manager):
        """The payload must be wrapped in {data: ..., version: -1} for the API."""
        manager = make_server_settings_manager()

        result = manager.prepare_server_settings_data({"http.proxy": "http://proxy:8080"})

        assert result == {"data": {"http.proxy": "http://proxy:8080"}, "version": -1}


# ===========================================================================
# XSOARServerSettingsManager.merge_server_settings
# ===========================================================================


class TestMergeServerSettings:
    def test_adds_new_key_when_missing_from_current(self, make_server_settings_manager):
        """A key present in server_settings but absent from current must be added."""
        manager = make_server_settings_manager(server_settings={"mail.transport": "smtp"})
        current_settings = {"http.proxy": "http://proxy:8080"}

        result = manager.merge_server_settings(current_settings)

        expected_merged_settings = {
            "http.proxy": "http://proxy:8080",
            "mail.transport": "smtp",
        }
        assert result == expected_merged_settings

    def test_updates_existing_key_when_value_differs(self, make_server_settings_manager):
        """A key present in both dicts with different values must be updated."""
        manager = make_server_settings_manager(server_settings={"http.proxy": "http://proxy.new:8080"})
        current_settings = {
            "http.proxy": "http://proxy.old:8080",
            "mail.from": "xsoar@example.com",
        }

        result = manager.merge_server_settings(current_settings)

        expected_merged_settings = {
            "http.proxy": "http://proxy.new:8080",
            "mail.from": "xsoar@example.com",
        }
        assert result == expected_merged_settings

    def test_preserves_existing_key_when_value_matches(self, make_server_settings_manager):
        """A key with an identical value must be preserved unchanged."""
        manager = make_server_settings_manager(server_settings={"http.proxy": "http://proxy.company.local:8080"})
        current_settings = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.from": "xsoar@example.com",
        }

        result = manager.merge_server_settings(current_settings)

        assert result == current_settings


# ===========================================================================
# XSOARServerSettingsManager.get_server_settings
# ===========================================================================


class TestGetServerSettings:
    def test_strips_versn_from_sysconf(self, make_server_settings_manager, api_server_settings_response):
        """
        ``versn`` must be removed from the returned dict so that callers never
        see it in comparisons or playbook output.
        """
        manager = make_server_settings_manager()
        manager.connection.request.return_value = api_server_settings_response

        result = manager.get_server_settings()

        expected_result = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
            "mail.from": "xsoar@example.com",
        }
        assert result == expected_result

    def test_does_not_mutate_shared_api_response(self, make_server_settings_manager, api_server_settings_response):
        """
        Calling get_server_settings twice with the same underlying response object
        must yield identical results; the original sysConf dict must retain versn.
        """
        manager = make_server_settings_manager()
        manager.connection.request.return_value = api_server_settings_response

        first_result = manager.get_server_settings()
        second_result = manager.get_server_settings()

        assert first_result == second_result
        assert api_server_settings_response["sysConf"]["versn"] == 7

    def test_returns_empty_dict_when_response_is_not_dict(self, make_server_settings_manager):
        """Non-dict responses must be normalised to an empty dict."""
        manager = make_server_settings_manager()
        manager.connection.request.return_value = None

        result = manager.get_server_settings()

        assert result == {}

    def test_raises_xsoar_api_error_on_request_failure(self, make_server_settings_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`.
        """
        manager = make_server_settings_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get available server settings"):
            manager.get_server_settings()


# ===========================================================================
# XSOARServerSettingsManager.update_server_setting
# ===========================================================================


class TestUpdateServerSetting:
    def test_posts_to_correct_endpoint_and_strips_versn(self, make_server_settings_manager):
        """
        The update must POST to /xsoar/system/config and strip versn from the
        sysConf before returning.
        """
        manager = make_server_settings_manager()
        _results = {
            "sysConf": {
                "versn": 9,
                "http.proxy": "http://proxy.company.local:8080",
            }
        }
        manager.connection.request.return_value = _results
        payload = {"data": {"http.proxy": "http://proxy.company.local:8080"}, "version": -1}

        result = manager.update_server_setting(payload)

        manager.connection.request.assert_called_once_with(
            method="POST",
            endpoint="/xsoar/system/config",
            data=payload,
        )
        assert result == {"http.proxy": "http://proxy.company.local:8080"}

    def test_raises_xsoar_api_error_on_request_failure(self, make_server_settings_manager):
        """Any exception from the connection must be re-raised as XSOARAPIError."""
        manager = make_server_settings_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to update server setting"):
            manager.update_server_setting({"data": {}, "version": -1})


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_check_mode_update_returns_merged_settings_shape(
        self,
        make_server_settings_manager,
        mock_module,
    ):
        """
        Check-mode must return the merged settings dict (not the API envelope)
        without calling update_server_setting.
        """
        manager = make_server_settings_manager(server_settings={"http.proxy": "http://proxy.new:8080"})
        module = mock_module(check_mode=True)
        _results = {
            "http.proxy": "http://proxy.old:8080",
            "mail.from": "xsoar@example.com",
        }

        with (
            patch("plugins.modules.server_settings.instance_needs_update", return_value=True),
            patch.object(manager, "get_server_settings", return_value=_results),
            patch.object(manager, "update_server_setting") as mock_update,
        ):
            result = ensure_present(module, manager)

        expected_server_settings = {
            "http.proxy": "http://proxy.new:8080",
            "mail.from": "xsoar@example.com",
        }
        mock_update.assert_not_called()
        assert result["changed"] is True
        assert result["msg"] == "Server settings would be updated."
        assert result["server_settings"] == expected_server_settings

    def test_create_in_check_mode_returns_input_settings(self, make_server_settings_manager, mock_module):
        """
        When no current settings exist, check-mode must return the module's
        server_settings dict unchanged and report changed=True.
        """
        manager = make_server_settings_manager(server_settings={"mail.transport": "smtp"})
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_server_settings", return_value={}):
            result = ensure_present(module, manager)

        assert result["changed"] is True
        assert result["msg"] == "Server settings would be created."
        assert result["server_settings"] == {"mail.transport": "smtp"}

    def test_returns_no_change_when_settings_are_already_up_to_date(
        self,
        make_server_settings_manager,
        mock_module,
    ):
        """Idempotency: no update call when existing values already match."""
        manager = make_server_settings_manager()
        _results = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
        }

        with (
            patch("plugins.modules.server_settings.instance_needs_update", return_value=False),
            patch.object(manager, "get_server_settings", return_value=_results),
            patch.object(manager, "update_server_setting") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is False
        assert result["msg"] == "Server settings are already up to date."
        assert result["server_settings"] == _results


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_returns_changed_false_when_requested_keys_are_not_present(
        self,
        make_server_settings_manager,
        mock_module,
    ):
        """
        When none of the delete_settings keys exist in the current configuration,
        changed must be False and update_server_setting must not be called.
        """
        manager = make_server_settings_manager(
            delete_settings=["mail.password", "smtp.token"],
            state="absent",
        )
        _results = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
        }

        with (
            patch.object(manager, "get_server_settings", return_value=_results),
            patch.object(manager, "update_server_setting") as mock_update,
        ):
            result = ensure_absent(mock_module, manager)

        mock_update.assert_not_called()
        assert result["changed"] is False
        assert result["msg"] == "Server settings are already absent."
        assert result["server_settings"] == _results
        assert result["deleted_keys"] == []

    def test_check_mode_reports_keys_that_would_be_deleted(self, make_server_settings_manager, mock_module):
        """
        Check-mode must report the intersection of delete_settings with current
        keys in deleted_keys and return the projected post-deletion settings.
        """
        manager = make_server_settings_manager(
            delete_settings=["http.proxy", "mail.password"],
            state="absent",
        )
        module = mock_module(check_mode=True)
        _results = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
            "mail.from": "xsoar@example.com",
        }

        with (
            patch.object(manager, "get_server_settings", return_value=_results),
            patch.object(manager, "update_server_setting") as mock_update,
        ):
            result = ensure_absent(module, manager)

        expected_server_settings = {
            "mail.transport": "smtp",
            "mail.from": "xsoar@example.com",
        }
        mock_update.assert_not_called()
        assert result["changed"] is True
        assert result["msg"] == "Server settings would be deleted."
        assert result["deleted_keys"] == ["http.proxy"]
        assert result["server_settings"] == expected_server_settings

    def test_real_mode_deletes_intersecting_keys_and_calls_update(
        self,
        make_server_settings_manager,
        mock_module,
    ):
        """
        In real mode, only the intersection of delete_settings and current keys
        must be removed; update_server_setting must be called with the remainder.
        """
        manager = make_server_settings_manager(
            delete_settings=["http.proxy", "mail.password"],
            state="absent",
        )
        _results = {
            "mail.transport": "smtp",
            "mail.from": "xsoar@example.com",
        }

        with (
            patch.object(
                manager,
                "get_server_settings",
                return_value={
                    "http.proxy": "http://proxy.company.local:8080",
                    "mail.transport": "smtp",
                    "mail.from": "xsoar@example.com",
                },
            ),
            patch.object(
                manager,
                "prepare_server_settings_data",
                return_value={"data": _results, "version": -1},
            ),
            patch.object(manager, "update_server_setting", return_value=_results) as mock_update,
        ):
            result = ensure_absent(mock_module, manager)

        mock_update.assert_called_once_with({"data": _results, "version": -1})
        assert result["changed"] is True
        assert result["msg"] == "Server settings deleted successfully."
        assert result["deleted_keys"] == ["http.proxy"]
        assert result["server_settings"] == _results

    def test_returns_no_change_when_no_current_settings_exist(self, make_server_settings_manager, mock_module):
        """When get_server_settings returns empty, changed must be False."""
        manager = make_server_settings_manager(state="absent")

        with patch.object(manager, "get_server_settings", return_value={}):
            result = ensure_absent(mock_module, manager)

        assert result["changed"] is False
        assert result["msg"] == "No server settings available to delete."


# ===========================================================================
# gather_server_settings
# ===========================================================================


class TestGatherServerSettings:
    def test_returns_server_settings_and_changed_false(self, make_server_settings_manager):
        """Gather must return changed=False and the current settings dict."""
        manager = make_server_settings_manager(state="gathered")
        _results = {
            "http.proxy": "http://proxy.company.local:8080",
            "mail.transport": "smtp",
        }

        with patch.object(manager, "get_server_settings", return_value=_results):
            result = gather_server_settings(manager)

        assert result["changed"] is False
        assert result["server_settings"] == _results

    def test_returns_not_found_message_when_settings_are_empty(self, make_server_settings_manager):
        """When get_server_settings returns empty, a descriptive message must be set."""
        manager = make_server_settings_manager(state="gathered")

        with patch.object(manager, "get_server_settings", return_value={}):
            result = gather_server_settings(manager)

        assert result["changed"] is False
        assert result["msg"] == "No server settings found."
