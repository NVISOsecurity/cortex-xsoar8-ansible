"""
Unit tests for plugins/modules/multi_tenant_sync_account.py — XSOARSyncAccountManager
and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.multi_tenant_sync_account import ensure_present, gather_sync_accounts

# ===========================================================================
# XSOARSyncAccountManager.get_running_accounts_list
# ===========================================================================


class TestGetRunningAccountsList:
    def test_returns_only_running_tenants(self, make_multi_tenant_sync_account_manager):
        """
        Only tenants with ``status == "running"`` must be included; all other
        statuses (e.g. ``"active"``) must be silently excluded.
        """
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.return_value = {
            "reply": [
                {"tenant_name": "tenant-a", "status": "running"},
                {"tenant_name": "tenant-b", "status": "running"},
                {"tenant_name": "tenant-c", "status": "active"},
            ]
        }

        result = manager.get_running_accounts_list()

        manager.connection.request.assert_called_once_with(
            "POST",
            "/public_api/v1/mssp/get_tenants",
            data={"request_data": {}},
        )
        assert result == ["tenant-a", "tenant-b"]

    def test_returns_empty_list_when_reply_has_no_running_accounts(self, make_multi_tenant_sync_account_manager):
        """When no tenants are in running state the result must be an empty list."""
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.return_value = {"reply": [{"tenant_name": "tenant-a", "status": "active"}]}

        result = manager.get_running_accounts_list()

        assert result == []

    def test_returns_empty_list_when_response_is_not_dict(self, make_multi_tenant_sync_account_manager):
        """Non-dict responses must be tolerated and yield an empty list."""
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.return_value = []

        result = manager.get_running_accounts_list()

        assert result == []

    def test_raises_xsoar_api_error_on_request_failure(self, make_multi_tenant_sync_account_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`.
        """
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get running accounts"):
            manager.get_running_accounts_list()


# ===========================================================================
# XSOARSyncAccountManager.get_account_items_to_sync
# ===========================================================================


class TestGetAccountItemsToSync:
    def test_returns_diff_payload_for_account(self, make_multi_tenant_sync_account_manager, account_diff_response):
        """The response must be returned as-is without any transformation."""
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.return_value = account_diff_response

        result = manager.get_account_items_to_sync("tenant-a")

        manager.connection.request.assert_called_once_with(
            method="POST",
            endpoint="/xsoar/account/content/diff/tenant-a",
        )
        assert result == account_diff_response

    def test_raises_xsoar_api_error_on_request_failure(self, make_multi_tenant_sync_account_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`
        that identifies the failing account.
        """
        manager = make_multi_tenant_sync_account_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to get account items to sync"):
            manager.get_account_items_to_sync("tenant-a")


# ===========================================================================
# XSOARSyncAccountManager.add_to_accounts_items_to_sync
# ===========================================================================


class TestAddToAccountsItemsToSync:
    def test_ignores_item_without_type(self, make_multi_tenant_sync_account_manager):
        """An item without a ``type`` key must not be added to the sync payload."""
        manager = make_multi_tenant_sync_account_manager()

        manager.add_to_accounts_items_to_sync("tenant-a", "add", {"id": "list-1", "name": "BlockedIPs"})

        assert manager.accounts_items_to_sync == {}

    def test_adds_item_under_correct_account_action_and_type(self, make_multi_tenant_sync_account_manager):
        """An item with a ``type`` key must be appended under account/action/type."""
        manager = make_multi_tenant_sync_account_manager()
        item = {"id": "list-1", "name": "BlockedIPs", "type": "List"}

        manager.add_to_accounts_items_to_sync("tenant-a", "add", item)

        expected_accounts_items_to_sync = {
            "tenant-a": {
                "add": {"List": [item]},
                "override": {},
                "remove": {},
            }
        }
        assert manager.accounts_items_to_sync == expected_accounts_items_to_sync


# ===========================================================================
# XSOARSyncAccountManager.needs_sync
# ===========================================================================


class TestNeedsSync:
    def test_collects_all_diff_items_when_all_items_is_true(
        self, make_multi_tenant_sync_account_manager, account_diff_response
    ):
        """
        With ``all_items=True``, every account's full diff payload must be stored
        in ``accounts_items_to_sync`` without filtering.
        """
        manager = make_multi_tenant_sync_account_manager(all_accounts=True, all_items=True)
        _results = {
            "tenant-a": account_diff_response,
            "tenant-b": account_diff_response,
        }

        with (
            patch.object(manager, "get_running_accounts_list", return_value=["tenant-a", "tenant-b"]),
            patch.object(manager, "get_account_items_to_sync", side_effect=lambda account: _results[account]),
        ):
            needs_sync = manager.needs_sync()

        expected_accounts_items_to_sync = {
            "tenant-a": account_diff_response,
            "tenant-b": account_diff_response,
        }
        assert needs_sync is True
        assert manager.accounts_items_to_sync == expected_accounts_items_to_sync

    def test_filters_selected_items_from_add_and_override_groups(self, make_multi_tenant_sync_account_manager):
        """
        With explicit ``items``, only matching names from ``add`` and ``override``
        must be collected; ``remove`` group items are excluded even when the name matches.
        """
        manager = make_multi_tenant_sync_account_manager(
            accounts=["tenant-a"],
            all_accounts=False,
            items=["BlockedIPs"],
            all_items=False,
        )
        manager.connection.request.return_value = {
            "add": {
                "List": [
                    {"id": "list-1", "name": "BlockedIPs", "type": "List"},
                    {"id": "list-2", "name": "Ignored", "type": "List"},
                ]
            },
            "override": {
                "Playbook": [
                    {"id": "pb-1", "name": "AlsoIgnored", "type": "Playbook"},
                ]
            },
            "remove": {
                "List": [
                    {"id": "list-3", "name": "BlockedIPs", "type": "List"},
                ]
            },
        }

        with patch.object(
            manager,
            "get_account_items_to_sync",
            return_value=manager.connection.request.return_value,
        ):
            needs_sync = manager.needs_sync()

        expected_accounts_items_to_sync = {
            "tenant-a": {
                "add": {"List": [{"id": "list-1", "name": "BlockedIPs", "type": "List"}]},
                "override": {},
                "remove": {},
            }
        }
        assert needs_sync is True
        assert manager.accounts_items_to_sync == expected_accounts_items_to_sync

    def test_returns_false_when_items_list_is_empty(self, make_multi_tenant_sync_account_manager):
        """Without a wanted-items list there is nothing to match; needs_sync must be False."""
        manager = make_multi_tenant_sync_account_manager(items=[], all_items=False)

        assert manager.needs_sync() is False
        assert manager.accounts_items_to_sync == {}

    def test_returns_false_when_no_accounts_are_provided(self, make_multi_tenant_sync_account_manager):
        """
        When ``all_accounts=False`` and ``accounts`` is empty, needs_sync must
        return False without making any API calls.
        """
        manager = make_multi_tenant_sync_account_manager(accounts=[], all_accounts=False)

        assert manager.needs_sync() is False


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_returns_no_change_when_no_accounts_need_sync(self, make_multi_tenant_sync_account_manager, mock_module):
        """When needs_sync returns False the result must be changed=False with no sync key."""
        manager = make_multi_tenant_sync_account_manager()

        with patch.object(manager, "needs_sync", return_value=False):
            result = ensure_present(mock_module, manager)

        assert result["changed"] is False
        assert result["msg"] == "No accounts need to be synced."
        assert "accounts_items_to_sync" not in result

    def test_check_mode_all_accounts_reports_would_sync(self, make_multi_tenant_sync_account_manager, mock_module):
        """
        In check mode with ``all_accounts=True``, no sync call must be made and
        the result must populate ``accounts_items_to_sync``.
        """
        manager = make_multi_tenant_sync_account_manager(all_accounts=True)
        module = mock_module(check_mode=True)
        _results = {
            "tenant-a": {
                "add": {"List": [{"name": "BlockedIPs", "type": "List"}]},
                "override": {},
                "remove": {},
            }
        }

        with (
            patch.object(manager, "needs_sync", return_value=True),
            patch.object(manager, "sync_account") as mock_sync,
        ):
            manager.accounts_items_to_sync = _results
            result = ensure_present(module, manager)

        mock_sync.assert_not_called()
        assert result["changed"] is True
        assert result["msg"] == "Sync would be performed for all accounts."
        assert result["accounts_items_to_sync"] == _results
        assert "sync_responses" not in result

    def test_real_mode_returns_per_account_sync_responses(self, make_multi_tenant_sync_account_manager, mock_module):
        """
        In real mode, ``sync_account`` must be called once per account and
        each response stored in ``sync_responses`` keyed by account identifier.
        """
        manager = make_multi_tenant_sync_account_manager(
            accounts=["tenant-a", "tenant-b"],
            all_accounts=False,
        )
        manager.accounts_items_to_sync = {
            "tenant-a": {"add": {"List": [{"name": "BlockedIPs", "type": "List"}]}, "override": {}, "remove": {}},
            "tenant-b": {"add": {"List": [{"name": "AllowedDomains", "type": "List"}]}, "override": {}, "remove": {}},
        }
        _results = {
            "tenant-a": {"status": "ok", "count": 1},
            "tenant-b": {"status": "ok", "count": 1},
        }

        with (
            patch.object(manager, "needs_sync", return_value=True),
            patch.object(manager, "sync_account", side_effect=lambda account, _: _results[account]) as mock_sync,
        ):
            result = ensure_present(mock_module, manager)

        assert mock_sync.call_count == 2
        assert result["changed"] is True
        assert result["accounts_items_to_sync"] == manager.accounts_items_to_sync
        assert result["sync_responses"] == _results


# ===========================================================================
# gather_sync_accounts
# ===========================================================================


class TestGatherSyncAccounts:
    def test_returns_changed_false_when_sync_is_needed(self, make_multi_tenant_sync_account_manager):
        """
        gather must always return changed=False even when accounts_items_to_sync
        is populated — gathering is a read-only operation.
        """
        manager = make_multi_tenant_sync_account_manager(state="gathered")
        _results = {
            "tenant-a": {
                "add": {"List": [{"name": "BlockedIPs", "type": "List"}]},
                "override": {},
                "remove": {},
            }
        }

        with patch.object(manager, "needs_sync", return_value=True):
            manager.accounts_items_to_sync = _results
            result = gather_sync_accounts(manager)

        assert result["changed"] is False
        assert result["msg"] == "Accounts have items that can be synced."
        assert result["accounts_items_to_sync"] == _results

    def test_returns_no_sync_message_when_nothing_to_sync(self, make_multi_tenant_sync_account_manager):
        """When needs_sync is False the result must not include accounts_items_to_sync."""
        manager = make_multi_tenant_sync_account_manager(state="gathered")

        with patch.object(manager, "needs_sync", return_value=False):
            result = gather_sync_accounts(manager)

        assert result["changed"] is False
        assert result["msg"] == "No accounts have items that can be synced."
        assert "accounts_items_to_sync" not in result
