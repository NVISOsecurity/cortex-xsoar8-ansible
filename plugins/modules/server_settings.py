#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


# TODO: Update when requested features are implemented in the API.

DOCUMENTATION = """
---
module: server_settings
short_description: Manage XSOAR 8 SaaS global server settings
description:
    - Update, delete, and gather global server configuration settings in Cortex XSOAR 8 SaaS.
    - Settings are key/value pairs stored in the XSOAR system configuration (C(/xsoar/system/config)).
    - For C(state=present), the provided settings are merged into the current configuration;
      any keys not mentioned are left unchanged.
    - For C(state=absent), the provided key names are removed from the current configuration.
    - Uses the XSOAR 8 SaaS REST API C(/xsoar/system/config) endpoint.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 SaaS instance with appropriate API permissions.
    - C(state=present) performs a merge, not a replacement; existing keys not in C(server_settings)
      are preserved.
    - The C(versn) key returned by the API is automatically stripped before comparison and output.
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    server_settings:
        description:
            - Dictionary of server setting key/value pairs to create or update.
            - Required when C(state=present).
            - Keys and values must match XSOAR system configuration field names exactly.
        type: dict
        required: false
    delete_settings:
        description:
            - List of server setting key names to remove from the configuration.
            - Required when C(state=absent).
            - Keys not present in the current configuration are silently ignored.
        type: list
        elements: str
        required: false
    state:
        description:
            - The desired state of the server settings.
            - C(present) - Merge the provided C(server_settings) into the current configuration.
            - C(absent) - Remove the keys listed in C(delete_settings) from the current configuration.
            - C(gathered) - Retrieve the current server configuration without making any changes.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Gather current server settings
  cortex.xsoar8.server_settings:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: current_settings

- name: Update server settings
  cortex.xsoar8.server_settings:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    server_settings:
      http.proxy: "http://proxy.company.com:8080"
      http.proxyUsername: "proxyuser"
    state: present
  register: update_result

- name: Update email notification settings
  cortex.xsoar8.server_settings:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    server_settings:
      mail.from: "xsoar-notifications@company.com"
      mail.transport: "smtp"
      mail.transport.host: "smtp.company.com"
    state: present

- name: Remove specific server settings
  cortex.xsoar8.server_settings:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    delete_settings:
      - http.proxy
      - http.proxyUsername
    state: absent
"""

RETURN = """
changed:
    description: Whether the server settings were changed.
    returned: always
    type: bool
    sample: true
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Server settings updated successfully."
server_settings:
    description: The server settings after the operation.
    returned: when state is C(present), C(absent), or C(gathered) and settings exist
    type: dict
    sample:
        http.proxy: "http://proxy.company.com:8080"
        mail.from: "xsoar-notifications@company.com"
        mail.transport: "smtp"
deleted_keys:
    description: List of server-settings keys that were targeted for removal.
    returned: when state is C(absent) and settings existed
    type: list
    elements: str
    sample:
        - "http.proxy"
        - "http.proxyUsername"
"""

import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_text

try:
    from ansible_collections.cortex.xsoar8.plugins.module_utils.utils import instance_needs_update
    from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import (
        XSOARAPIError,
        get_connection,
        xsoar_argument_spec,
    )

    HAS_LIB = True
except ImportError:
    HAS_LIB = False


class XSOARServerSettingsManager:
    """
    Manager class for XSOAR Server Settings operations.
    """

    def __init__(self, connection):
        """
        Initialize the Server Settings manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module

        self.delete_settings = connection.module.params["delete_settings"]
        self.server_settings = connection.module.params["server_settings"]
        self.state = connection.module.params["state"]

    def prepare_server_settings_data(self, data):
        """
        Prepare server settings data for update.

        Returns:
            dict: Prepared server settings data
        """
        return {"data": data, "version": -1}

    def merge_server_settings(self, current_settings):
        """
        Merge provided server settings into current settings.

        Any key present in ``self.server_settings`` but missing from
        ``current_settings`` is added. Any key present in both dictionaries
        with a different value is updated to the value from
        ``self.server_settings``.

        Args:
            current_settings (dict): Current server settings.

        Returns:
            dict: Updated settings dictionary.
        """
        merged_settings = dict(current_settings or {})

        for key, value in (self.server_settings or {}).items():
            if key not in merged_settings or merged_settings.get(key) != value:
                merged_settings[key] = value

        return merged_settings

    def get_server_settings(self):
        """
        Retrieve current Server Settings from XSOAR.

        Returns:
            dict: Current Server Settings information
        """
        try:
            response = self.connection.request(
                method="GET",
                endpoint="/xsoar/system/config",
            )
            if isinstance(response, dict):
                # Copy before popping; mutating the response dict can leak side
                # effects to callers/test doubles that keep a reference.
                resp = dict(response.get("sysConf", {}) or {})
                resp.pop("versn", None)
                return resp
            return {}
        except Exception as e:
            raise XSOARAPIError(f"Failed to get available server settings: {to_text(e)}") from e

    def update_server_setting(self, server_setting_data):
        """
        Update Server Setting in XSOAR.

        Args:
            server_setting_data (dict): Data for the new Server Setting

        Returns:
            dict: Information about the updated Server Setting
        """
        try:
            response = self.connection.request(
                method="POST",
                endpoint="/xsoar/system/config",
                data=server_setting_data,
            )
            if isinstance(response, dict):
                resp = dict(response.get("sysConf", {}) or {})
                resp.pop("versn", None)
                return resp
            return {}
        except Exception as e:
            raise XSOARAPIError(f"Failed to update server setting: {to_text(e)}") from e


def ensure_present(module, server_settings_manager):
    """
    Ensure Server Settings are present.

    Args:
        module: AnsibleModule instance
        server_settings_manager: XSOARServerSettingsManager instance

    Returns:
        dict: Result information
    """
    result = {}

    if current_settings := server_settings_manager.get_server_settings():
        fields_to_compare = list(server_settings_manager.server_settings.items())
        if instance_needs_update(current_settings, fields_to_compare):
            merged_settings = server_settings_manager.merge_server_settings(current_settings)
            if module.check_mode:
                result = {
                    "changed": True,
                    "msg": "Server settings would be updated.",
                    "server_settings": merged_settings,
                }
            else:
                update_response = server_settings_manager.update_server_setting(
                    server_settings_manager.prepare_server_settings_data(merged_settings)
                )
                result = {
                    "changed": True,
                    "msg": "Server settings updated successfully.",
                    "server_settings": update_response,
                }
        else:
            result = {
                "changed": False,
                "msg": "Server settings are already up to date.",
                "server_settings": current_settings,
            }
    else:
        if module.check_mode:
            result = {
                "changed": True,
                "msg": "Server settings would be created.",
                "server_settings": server_settings_manager.server_settings,
            }
        else:
            created_server_settings = server_settings_manager.update_server_setting(
                server_settings_manager.prepare_server_settings_data(server_settings_manager.server_settings)
            )
            result = {
                "changed": True,
                "msg": "Server settings created successfully.",
                "server_settings": created_server_settings,
            }

    return result


def ensure_absent(module, server_settings_manager):
    """
    Ensure Server Settings are absent.

    Args:
        module: AnsibleModule instance
        server_settings_manager: XSOARServerSettingsManager instance

    Returns:
        dict: Result information
    """
    result = {}

    if current_settings := server_settings_manager.get_server_settings():
        # Idempotency: only act on keys that are actually present in the
        # current configuration; if none of the requested keys exist, this is
        # a no-op.
        keys_to_delete = [k for k in (server_settings_manager.delete_settings or []) if k in current_settings]
        if not keys_to_delete:
            result = {
                "changed": False,
                "msg": "Server settings are already absent.",
                "server_settings": current_settings,
                "deleted_keys": [],
            }
        elif module.check_mode:
            projected = {k: v for k, v in current_settings.items() if k not in keys_to_delete}
            result = {
                "changed": True,
                "msg": "Server settings would be deleted.",
                "server_settings": projected,
                "deleted_keys": keys_to_delete,
            }
        else:
            for setting in keys_to_delete:
                current_settings.pop(setting, None)
            updated_settings = server_settings_manager.update_server_setting(
                server_settings_manager.prepare_server_settings_data(current_settings)
            )
            result = {
                "changed": True,
                "msg": "Server settings deleted successfully.",
                "server_settings": updated_settings,
                "deleted_keys": keys_to_delete,
            }
    else:
        result = {
            "changed": False,
            "msg": "No server settings available to delete.",
        }

    return result


def gather_server_settings(server_settings_manager):
    """
    Gather Server Settings configuration.

    Args:
        server_settings_manager: XSOARServerSettingsManager instance

    Returns:
        dict: Result configuration
    """
    result = {"changed": False}

    if server_settings := server_settings_manager.get_server_settings():
        result["server_settings"] = server_settings
    else:
        result["msg"] = "No server settings found."

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            delete_settings=dict(type="list", elements="str", required=False),
            server_settings=dict(type="dict", required=False),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[
            ("state", "present", ["server_settings"]),
            ("state", "absent", ["delete_settings"]),
        ],
        supports_check_mode=True,
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create server settings manager
    try:
        connection = get_connection(module)
        server_settings_manager = XSOARServerSettingsManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if server_settings_manager.state == "present":
            result = ensure_present(module, server_settings_manager)
        elif server_settings_manager.state == "absent":
            result = ensure_absent(module, server_settings_manager)
        else:  # gathered
            result = gather_server_settings(server_settings_manager)
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
