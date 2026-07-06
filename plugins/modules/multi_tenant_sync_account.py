#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: multi_tenant_sync_account
short_description: Sync content to XSOAR child tenants
description:
        - Synchronize selected content items (or all pending items) to one or more Cortex XSOAR child tenants.
        - Can target explicit tenant account names or all running tenant accounts.
        - Supports a dry-run flow through check mode.
version_added: "1.0.0"
author:
        - Palo Alto Networks (@PaloAltoNetworks)
requirements:
        - requests
notes:
        - Check mode is supported.
        - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
        - Some multi-tenant sync endpoints MAY NOT be compatible with the Global Management Key feature.
        - If Global Management Key authentication fails for this module, use a standard tenant API key with
            sufficient MSSP and content sync permissions.
        - Uses C(/public_api/v1/mssp/get_tenants) to discover running accounts when I(all_accounts=true).
        - Uses C(/xsoar/account/content/diff/{account}) to retrieve pending content differences.
        - Uses C(/xsoar/account/content/sync/acc_{account}) to execute synchronization.
        - I(all_accounts) and I(accounts) are mutually exclusive.
        - I(all_items) and I(items) are mutually exclusive.
extends_documentation_fragment:
        - cortex.xsoar8.xsoar.PROVIDER
options:
        accounts:
                description:
                        - Explicit tenant account names to evaluate or sync.
                        - Mutually exclusive with I(all_accounts).
                type: list
                elements: str
                required: false
        all_accounts:
                description:
                        - If C(true), evaluates all running tenant accounts discovered from the API.
                        - Mutually exclusive with I(accounts).
                type: bool
                required: false
        items:
                description:
                        - Content item names to include for sync evaluation.
                        - Only matching item names from C(add) and C(override) groups are selected.
                        - Mutually exclusive with I(all_items).
                type: list
                elements: str
                required: false
        all_items:
                description:
                        - If C(true), includes all pending diff items for each target account.
                        - Mutually exclusive with I(items).
                type: bool
                required: false
        state:
                description:
                        - Desired operation mode.
                        - C(present) evaluates and performs sync for matching pending items.
                        - C(gathered) evaluates and reports accounts/items that can be synced.
                type: str
                choices: ['present', 'gathered']
                default: 'present'
"""

EXAMPLES = """
- name: Sync selected items for specific accounts
  cortex.xsoar8.multi_tenant_sync_account:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    accounts:
      - "tenant-a"
      - "tenant-b"
    items:
      - "BlockedIPs"
      - "AllowedDomains"
    state: present

- name: Sync all pending items for all running accounts
  cortex.xsoar8.multi_tenant_sync_account:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    all_accounts: true
    all_items: true
    state: present

- name: Check mode preview for all accounts
  cortex.xsoar8.multi_tenant_sync_account:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    all_accounts: true
    all_items: true
    state: present
  check_mode: true
  register: sync_preview

- name: Gather accounts/items that can be synced
  cortex.xsoar8.multi_tenant_sync_account:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    accounts:
      - "tenant-a"
    items:
      - "BlockedIPs"
    state: gathered
  register: sync_candidates
"""

RETURN = """
changed:
        description: Whether a sync action was performed.
        returned: always
        type: bool
        sample: true
accounts_items_to_sync:
        description:
                - Map of accounts to pending sync items grouped by action (C(add), C(override), C(remove)).
                - Returned by state C(present) and state C(gathered) when matching items exist.
        returned: when matching items exist
        type: dict
        sample:
                tenant-a:
                        add:
                            List:
                                - name: "BlockedIPs"
                                  type: "List"
                        override: {}
                        remove: {}
sync_responses:
        description: Per-account API responses keyed by account identifier.
        returned: when state is present, not check mode, and matching items exist
        type: dict
msg:
        description: A message describing the result.
        returned: always
        type: str
        sample: "All accounts synced successfully."
"""

import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_text

try:
    from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import (
        XSOARAPIError,
        get_connection,
        xsoar_argument_spec,
    )

    HAS_LIB = True
except ImportError:
    HAS_LIB = False


class XSOARSyncAccountManager:
    """
    Manager class for XSOAR Sync Account operations.
    """

    def __init__(self, connection):
        """
        Initialize the Sync Account manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module

        self.accounts = connection.module.params["accounts"]
        self.all_accounts = connection.module.params["all_accounts"]
        self.items = connection.module.params["items"]
        self.all_items = connection.module.params["all_items"]
        self.state = connection.module.params["state"]

        self.accounts_items_to_sync = {}

    def get_running_accounts_list(self):
        """
        Retrieve running Accounts from XSOAR.

        Returns:
            list: Current running Accounts
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/mssp/get_tenants",
                data={"request_data": {}},
            )
            tenants = response.get("reply", []) if isinstance(response, dict) else []
            return [tenant.get("tenant_name") for tenant in tenants if tenant.get("status") == "running"]
        except Exception as e:
            raise XSOARAPIError(f"Failed to get running accounts: {to_text(e)}") from e

    def get_account_items_to_sync(self, account):
        """
        Get account items that can be synced.

        Args:
            account (str): Account identifier

        Returns:
            dict: Account items that can be synced
        """
        try:
            response = self.connection.request(
                method="POST",
                endpoint=f"/xsoar/account/content/diff/{account}",
            )
            return response
        except Exception as e:
            raise XSOARAPIError(f"Failed to get account items to sync for account: {account}, {to_text(e)}") from e

    def sync_account(self, account, data):
        """
        Sync a single account to XSOAR.

        Args:
            account (str): Account identifier
            data (dict): Account data to sync

        Returns:
            dict: API response from sync operation
        """
        try:
            response = self.connection.request(
                method="POST",
                endpoint=f"/xsoar/account/content/sync/acc_{account}",
                data=data,
            )
            return response
        except Exception as e:
            raise XSOARAPIError(f"Failed to sync account: {account}, {to_text(e)}") from e

    def add_to_accounts_items_to_sync(self, account, action, item):
        """
        Add a matched item to the pending sync payload for an account.

        Args:
            account (str): Account identifier
            action (str): Sync action type
            item (dict): Item to sync
        """
        if not (item_type := item.get("type")):
            return

        account_items = self.accounts_items_to_sync.setdefault(
            account,
            {"add": {}, "override": {}, "remove": {}},
        )
        action_items = account_items.setdefault(action, {})
        action_items.setdefault(item_type, []).append(item)

    def needs_sync(self):
        """
        Determine if an account needs to be synced based on items to sync.

        Returns:
            bool: True if sync is needed, False otherwise
        """
        if not (accounts := self.get_running_accounts_list() if self.all_accounts else self.accounts):
            return False

        if self.all_items:
            for account in accounts:
                diff = self.get_account_items_to_sync(account)
                if any(diff.get(key) for key in ("add", "override", "remove")):
                    self.accounts_items_to_sync[account] = diff
        else:
            wanted_items = set(self.items or [])
            if not wanted_items:
                return False

            for account in accounts:
                account_items_to_sync = self.get_account_items_to_sync(account)

                for action in ("add", "override"):
                    available_items = account_items_to_sync.get(action)
                    if not isinstance(available_items, dict):
                        continue

                    for items_by_type in available_items.values():
                        if not isinstance(items_by_type, list):
                            continue

                        for item in items_by_type:
                            if item.get("name") in wanted_items:
                                self.add_to_accounts_items_to_sync(account=account, action=action, item=item)

        return bool(self.accounts_items_to_sync)


def ensure_present(module, sync_account_manager):
    """
    Ensure Sync Accounts are present.

    Args:
        module: AnsibleModule instance
        sync_account_manager: XSOARSyncAccountManager instance

    Returns:
        dict: Result information
    """
    result = {}

    if sync_account_manager.needs_sync():
        if sync_account_manager.all_accounts:
            if module.check_mode:
                result = {
                    "changed": True,
                    "msg": "Sync would be performed for all accounts.",
                    "accounts_items_to_sync": sync_account_manager.accounts_items_to_sync,
                }
            else:
                sync_responses = {}
                for account, items in sync_account_manager.accounts_items_to_sync.items():
                    sync_responses[account] = sync_account_manager.sync_account(account, items)

                result = {
                    "changed": True,
                    "msg": "All accounts synced successfully.",
                    "accounts_items_to_sync": sync_account_manager.accounts_items_to_sync,
                    "sync_responses": sync_responses,
                }
        else:
            if module.check_mode:
                result = {
                    "changed": True,
                    "msg": f"Sync would be performed for {sync_account_manager.accounts} accounts.",
                    "accounts_items_to_sync": sync_account_manager.accounts_items_to_sync,
                }
            else:
                sync_responses = {}
                for account, items in sync_account_manager.accounts_items_to_sync.items():
                    sync_responses[account] = sync_account_manager.sync_account(account, items)

                result = {
                    "changed": True,
                    "msg": f"{sync_account_manager.accounts} account(s) synced successfully.",
                    "accounts_items_to_sync": sync_account_manager.accounts_items_to_sync,
                    "sync_responses": sync_responses,
                }
    else:
        result = {
            "changed": False,
            "msg": "No accounts need to be synced.",
        }

    return result


def gather_sync_accounts(sync_account_manager):
    """
    Gather Sync Accounts configuration.

    Args:
        sync_account_manager: XSOARSyncAccountManager instance

    Returns:
        dict: Result configuration
    """
    result = {"changed": False}

    if sync_account_manager.needs_sync():
        result = {
            "changed": False,
            "msg": "Accounts have items that can be synced.",
            "accounts_items_to_sync": sync_account_manager.accounts_items_to_sync,
        }
    else:
        result["msg"] = "No accounts have items that can be synced."

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            accounts=dict(type="list", elements="str"),
            all_accounts=dict(type="bool"),
            items=dict(type="list", elements="str"),
            all_items=dict(type="bool"),
            state=dict(type="str", choices=["present", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[
            ("all_items", "items"),
            ("all_accounts", "accounts"),
        ],
        required_one_of=[
            ("accounts", "all_accounts"),
            ("items", "all_items"),
        ],
        supports_check_mode=True,
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create sync account manager
    try:
        connection = get_connection(module)
        sync_account_manager = XSOARSyncAccountManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if sync_account_manager.state == "present":
            result = ensure_present(module, sync_account_manager)
        else:  # gathered
            result = gather_sync_accounts(sync_account_manager)
    except Exception as e:
        module.fail_json(
            msg=f"Module execution failed: {to_text(e)}",
            exception=traceback.format_exc(),
        )
    finally:
        try:
            connection.close()
        except Exception:
            pass

    # Return result
    module.exit_json(**result)


if __name__ == "__main__":
    main()
