#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: pre_process_rule
short_description: Manage XSOAR 8 pre-process rules
description:
    - Create, update, delete, and gather information about pre-process rules in Cortex XSOAR 8.
    - Pre-process rules evaluate incoming events and determine how to handle duplicates
      of existing open incidents.
    - Rules can close, drop, link, or run a script against duplicate events.
    - Uses the XSOAR 8 REST API for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
    - Uses the /xsoar/preprocess/rules and /xsoar/preprocess/rule endpoints.
    - I(script_id) is required when I(action) is C(script).
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    name:
        description:
            - The name of the pre-process rule.
            - Required when state is C(present) or C(absent).
        type: str
    action:
        description:
            - The action to perform when the rule matches an incoming event.
            - Required when state is C(present).
            - C(close) - Close the new incoming event.
            - C(drop) - Drop the incoming event without creating an incident.
            - C(dropAndUpdate) - Drop the event and update the matched existing incident.
            - C(link) - Link the incoming event to the matched existing incident.
            - C(linkAndClose) - Link the event to the matched existing incident and close the new one.
            - C(script) - Run a custom script to handle the event. Requires I(script_id).
        type: str
        choices: ['close', 'drop', 'dropAndUpdate', 'link', 'linkAndClose', 'script']
    enabled:
        description:
            - Whether the pre-process rule is active.
        type: bool
        default: true
    script_id:
        description:
            - The ID of the script to run when I(action) is C(script).
            - Required when I(action) is C(script).
        type: str
    propagation_labels:
        description:
            - Labels used for rule propagation in multi-tenant environments.
        type: list
        default: []
    state:
        description:
            - The desired state of the pre-process rule.
            - C(present) - Create or update the rule.
            - C(absent) - Delete the rule.
            - C(gathered) - Retrieve information about existing rules.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a pre-process rule that drops duplicate events
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Drop Duplicate Phishing Alerts"
    action: "drop"
    enabled: true
    state: present

- name: Create a pre-process rule that links duplicate events
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Link Related Malware Incidents"
    action: "link"
    enabled: true
    state: present

- name: Create a pre-process rule that runs a script
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Custom Dedup Script Rule"
    action: "script"
    script_id: "DedupScript"
    enabled: true
    state: present

- name: Disable a pre-process rule
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Drop Duplicate Phishing Alerts"
    action: "drop"
    enabled: false
    state: present

- name: Gather all pre-process rules
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_rules

- name: Get a specific pre-process rule by name
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Drop Duplicate Phishing Alerts"
    state: gathered
  register: rule_info

- name: Delete a pre-process rule
  cortex.xsoar8.pre_process_rule:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Drop Duplicate Phishing Alerts"
    state: absent
"""

RETURN = """
changed:
    description: Whether the pre-process rule was created, updated, or deleted.
    returned: always
    type: bool
    sample: true
pre_process_rule:
    description: Information about the pre-process rule.
    returned: when state is present, when state is absent and the rule existed,
              or when state is gathered and a matching rule is found by name.
              May be omitted for state is present if the API operation succeeds
              but response payload does not contain a matching object and
              follow-up read does not find the rule.
    type: dict
    contains:
        id:
            description: The unique ID of the pre-process rule.
            type: str
            sample: "12345678-1234-1234-1234-123456789abc"
        name:
            description: The name of the pre-process rule.
            type: str
            sample: "Drop Duplicate Phishing Alerts"
        action:
            description: The action performed on matching events.
            type: str
            sample: "drop"
        enabled:
            description: Whether the rule is active.
            type: bool
            sample: true
        scriptID:
            description: The ID of the script run when action is C(script).
            type: str
            sample: "DedupScript"
        propagationLabels:
            description: Propagation labels for multi-tenant environments.
            type: list
            sample: []
pre_process_rules:
    description: All pre-process rules.
    returned: when state is gathered, no I(name) is specified, and at least one rule exists
    type: list
    elements: dict
    sample: [{"id": "abc123", "name": "Drop Duplicate Phishing Alerts", "action": "drop"}]
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Pre-process rule Drop Duplicate Phishing Alerts created successfully"
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


class XSOARPreProcessRuleManager:
    """
    Manager class for XSOAR Pre-Process Rule operations.
    """

    def __init__(self, connection):
        """
        Initialize the Pre-Process Rule manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module

        self.action = connection.module.params["action"]
        self.enabled = connection.module.params["enabled"]
        self.name = connection.module.params["name"]
        self.propagation_labels = connection.module.params["propagation_labels"]
        self.script_id = connection.module.params["script_id"]
        self.state = connection.module.params["state"]

        self.fields_to_compare = [
            ("action", self.action),
            ("enabled", self.enabled),
            ("propagationLabels", self.propagation_labels),
            ("scriptID", self.script_id),
        ]

    def build_rule_data(self, raw_rule_data=None):
        """
        Create the data payload for creating or updating a Pre-Process Rule.

        Args:
            raw_rule_data (dict, optional): Raw rule data from an existing rule.

        Returns:
            dict: Data payload for Pre-Process Rule operations
        """
        if raw_rule_data:
            raw_rule_data = dict(raw_rule_data)
            raw_rule_data["action"] = self.action
            raw_rule_data["enabled"] = self.enabled
            raw_rule_data["propagationLabels"] = self.propagation_labels or []
            raw_rule_data["scriptID"] = self.script_id
            raw_rule_data["version"] = -1
            return raw_rule_data

        rule_data = {
            "action": self.action,
            "commitMessage": "Preprocess rule edited",
            "enabled": self.enabled,
            "existingEventsFilters": [],
            "id": "",
            "linkTo": "oldest",
            "name": self.name,
            "newEventFilters": [],
            "searchClosed": False,
            "period": {"fromValue": 30, "by": "days"},
            "propagationLabels": self.propagation_labels or [],
            "scriptID": self.script_id,
            "shouldPublish": True,
            "shouldCommit": True,
        }

        return rule_data

    def get_pre_process_rules(self):
        """
        Retrieves Pre-Process Rules.

        Returns:
            list | dict: Pre-Process Rule response from the API.
        """
        try:
            response = self.connection.request("GET", "/xsoar/preprocess/rules")
            return response if isinstance(response, list) else []
        except XSOARAPIError as e:
            raise XSOARAPIError(f"Failed to get available pre-process rules: {to_text(e)}") from e

    def get_pre_process_rule_by_name(self, name):
        """
        Retrieves a Pre-Process Rule by name.

        Args:
            name (str): Name of the Pre-Process Rule to retrieve.

        Returns:
            dict | None: Pre-Process Rule data if found, else None.
        """
        if rules := self.get_pre_process_rules():
            for _rule in rules:
                if _rule.get("name") == name:
                    return _rule
        return None

    def create_pre_process_rule(self, rule_data):
        """
        Creates a new Pre-Process Rule.

        Args:
            rule_data (dict): Data for the new Pre-Process Rule.

        Returns:
            dict: Created Pre-Process Rule response from the API.
        """
        try:
            response = self.connection.request("POST", "/xsoar/preprocess/rule", data=rule_data)
            if isinstance(response, list):
                return next((rule for rule in response if rule.get("name") == self.name), None)
            return None
        except XSOARAPIError as e:
            raise XSOARAPIError(f"Failed to create pre-process rule: {to_text(e)}") from e

    def update_pre_process_rule(self, current_rule_data):
        """
        Updates an existing Pre-Process Rule.

        Args:
            current_rule_data (dict): Current data of the Pre-Process Rule to update.

        Returns:
            dict: Updated Pre-Process Rule response from the API.
        """
        try:
            response = self.connection.request(
                "POST", "/xsoar/preprocess/rule", data=self.build_rule_data(current_rule_data)
            )
            if isinstance(response, list):
                return next((rule for rule in response if rule.get("name") == self.name), None)
            return None
        except XSOARAPIError as e:
            raise XSOARAPIError(f"Failed to update pre-process rule: {to_text(e)}") from e

    def delete_pre_process_rule(self, rule_id):
        """
        Deletes a Pre-Process Rule.

        Args:
            rule_id (str): ID of the Pre-Process Rule to delete.

        Returns:
            dict: Response from the API after deletion.
        """
        try:
            response = self.connection.request("DELETE", f"/xsoar/preprocess/rule/{rule_id}")
            return response
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to delete Pre-Process Rule {rule_id}: {to_text(e)}")


def ensure_present(module, pre_process_rule_manager):
    """
    Ensure Pre-Process Rule is present.

    Args:
        module: AnsibleModule instance
        pre_process_rule_manager: XSOARPreProcessRuleManager instance

    Returns:
        dict: Result information
    """
    result = {}

    # Check if rule exists
    if current_rule := pre_process_rule_manager.get_pre_process_rule_by_name(name=pre_process_rule_manager.name):
        if module.check_mode:
            # Only report what would happen, do not update
            if instance_needs_update(current_rule, pre_process_rule_manager.fields_to_compare):
                result = {
                    "changed": True,
                    "msg": f"Pre-Process Rule {pre_process_rule_manager.name} would be updated",
                    "pre_process_rule": current_rule,
                }
            else:
                result = {
                    "changed": False,
                    "msg": f"Pre-Process Rule {pre_process_rule_manager.name} is already up to date (check mode)",
                    "pre_process_rule": current_rule,
                }
        elif instance_needs_update(current_rule, pre_process_rule_manager.fields_to_compare):
            updated_rule = pre_process_rule_manager.update_pre_process_rule(current_rule_data=current_rule)
            result = {
                "changed": True,
                "msg": f"Pre-Process Rule {pre_process_rule_manager.name} updated successfully",
                "pre_process_rule": updated_rule,
            }
        else:
            # No update needed
            result = {
                "changed": False,
                "msg": f"Pre-Process Rule {pre_process_rule_manager.name} is already up to date",
                "pre_process_rule": current_rule,
            }

    else:
        rule_data = pre_process_rule_manager.build_rule_data()
        # Create new rule
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Pre-Process Rule {pre_process_rule_manager.name} would be created",
                "pre_process_rule": rule_data,
            }
        else:
            created_rule = pre_process_rule_manager.create_pre_process_rule(rule_data)
            result = {
                "changed": True,
                "msg": f"Pre-Process Rule {pre_process_rule_manager.name} created successfully",
                "pre_process_rule": created_rule,
            }

    return result


def ensure_absent(module, pre_process_rule_manager):
    """
    Ensure Pre-Process Rule is absent.

    Args:
        module: AnsibleModule instance
        pre_process_rule_manager: XSOARPreProcessRuleManager instance

    Returns:
        dict: Result information
    """
    result = {}

    if current_rule := pre_process_rule_manager.get_pre_process_rule_by_name(name=pre_process_rule_manager.name):
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Pre-Process Rule: {pre_process_rule_manager.name} would be deleted",
                "pre_process_rule": current_rule,
            }
        else:
            pre_process_rule_manager.delete_pre_process_rule(current_rule["id"])
            result = {
                "changed": True,
                "msg": f"Pre-Process Rule: {pre_process_rule_manager.name} deleted successfully",
                "pre_process_rule": current_rule,
            }
    else:
        result = {"changed": False, "msg": f"Pre-Process Rule: {pre_process_rule_manager.name} does not exist"}

    return result


def gather_pre_process_rules(pre_process_rule_manager):
    """
    Gather Pre-Process Rule information.

    Args:
        pre_process_rule_manager: XSOARPreProcessRuleManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    if pre_process_rule_manager.name:
        if rule := pre_process_rule_manager.get_pre_process_rule_by_name(pre_process_rule_manager.name):
            result["pre_process_rule"] = rule
            result["msg"] = f"Pre-Process Rule '{pre_process_rule_manager.name}' retrieved successfully."
        else:
            result["msg"] = f"Pre-Process Rule '{pre_process_rule_manager.name}' not found."
    else:
        if rules := pre_process_rule_manager.get_pre_process_rules():
            result["pre_process_rules"] = rules
            result["msg"] = f"Retrieved {len(rules)} pre-process rules."
        else:
            result["msg"] = "No pre-process rules found."

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    # TODO: Add support for "Conditions for Incoming incident" field
    argument_spec.update(
        dict(
            action=dict(type="str", choices=["close", "drop", "dropAndUpdate", "link", "linkAndClose", "script"]),
            enabled=dict(type="bool", default=True),
            name=dict(type="str"),
            propagation_labels=dict(type="list", elements="str", default=[]),
            script_id=dict(type="str"),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[
            ("state", "present", ["name", "action"]),
            ("state", "absent", ["name"]),
        ],
        supports_check_mode=True,
    )

    if module.params["state"] == "present" and module.params["action"] == "script" and not module.params["script_id"]:
        module.fail_json(msg="script_id is required when state=present and action=script.")

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create pre-process rule manager
    try:
        connection = get_connection(module)
        pre_process_rule_manager = XSOARPreProcessRuleManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if pre_process_rule_manager.state == "present":
            result = ensure_present(module, pre_process_rule_manager)
        elif pre_process_rule_manager.state == "absent":
            result = ensure_absent(module, pre_process_rule_manager)
        else:  # gathered
            result = gather_pre_process_rules(pre_process_rule_manager)
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
