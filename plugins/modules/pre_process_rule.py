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
    - Rules can close, drop, update, link, or run a script against duplicate events.
    - Uses the XSOAR 8 REST API for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
    - Uses the /xsoar/preprocess/rules, /xsoar/preprocess/rule, and /xsoar/preprocess/filters endpoints.
    - Nonempty filters for C(state=present) require operator metadata from the API, including in check mode.
    - Filters are validated before payload conversion; invalid conditions fail the task.
    - The API is expected to supply a Boolean C(isSingleValue) flag for each operator.
    - Supplied filters are compared against both incoming-event filter fields; a difference in either field triggers an update that synchronizes both.
    - Clearing incoming-event filters can broaden matches for an enabled rule.
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
    filters:
        description:
            - Filters for incoming events, sent as C(newEventFilters) and C(readyNewEventFilters).
            - Used only when I(state) is C(present); it does not affect C(absent) or C(gathered) operations.
            - All groups under C(and) must match; at least one condition under each C(or) must match.
            - A single group can contain one condition or multiple OR-connected conditions.
            - The C(and) and C(or) keys are converted to nested lists and are not sent as payload keys.
            - 'Omit to preserve existing filters on update. Use C({and: []}) to clear them.'
            - When supplied on update, both incoming-event filter fields must match or the rule is updated to synchronize them.
            - New rules without this option are created with empty incoming-event filters.
            - Existing-event filters are preserved on update and cannot be configured with this option.
        type: dict
        suboptions:
            and:
                description:
                    - Groups joined by logical AND.
                type: list
                elements: dict
                required: true
                suboptions:
                    or:
                        description:
                            - Conditions joined by logical OR. Each group must contain at least one condition.
                        type: list
                        elements: dict
                        required: true
                        suboptions:
                            operator:
                                description:
                                    - XSOAR comparison operator, such as C(isEqualString) or C(isNotEqualString).
                                    - Must match a key in the operator metadata returned by the API.
                                type: str
                                required: true
                            left:
                                description:
                                    - Left operand.
                                type: dict
                                required: true
                                suboptions:
                                    value:
                                        description:
                                            - Event field name, wrapped as C(value.simple) with C(isContext=true) in the API payload.
                                        type: str
                                        required: true
                            right:
                                description:
                                    - Right operand, required when the operator API metadata has C(isSingleValue=false).
                                    - Operand requirements depend on C(isSingleValue), not the operator data type.
                                    - Omit or use an empty dict for unary operators with C(isSingleValue=true); nonempty values are rejected.
                                    - Unary operators, including C(isTrue), C(isFalse), C(isEmpty), and C(isNotEmpty), are sent with an empty C(right) object.
                                type: dict
                                suboptions:
                                    value:
                                        description:
                                            - Literal comparison value, wrapped as C(value.simple) with C(isContext=false) in the API payload.
                                            - Required and must not be empty for operators with C(isSingleValue=false).
                                        type: str
                            type:
                                description:
                                    - XSOAR filter type, such as C(sourceBrand).
                                type: str
                                required: true
    script_id:
        description:
            - The ID of the script to run when I(action) is C(script).
            - Required when I(action) is C(script).
        type: str
    propagation_labels:
        description:
            - Labels used for rule propagation in multi-tenant environments.
        type: list
        elements: str
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
- name: Create or reconcile a pre-process rule that drops duplicate events
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Duplicate Phishing Alerts
    action: drop
    enabled: true
    filters:
      and:
      - or:
        - operator: isEqualString
          left:
            value: sourceBrand
          right:
            value: Azure Sentinel
          type: sourceBrand
        - operator: isEqualString
          left:
            value: sourceBrand
          right:
            value: Microsoft Graph
          type: sourceBrand
      - or:
        - operator: isEqualString
          left:
            value: name
          right:
            value: Suspicious login
          type: name
    state: present
- name: Create a rule for an incoming Boolean field
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Testing Events
    action: drop
    filters:
      and:
      - or:
        - operator: isTrue
          left:
            value: testing
          type: testing
    state: present
- name: Remove all incoming-event filters from an existing rule
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Testing Events
    action: drop
    enabled: false
    filters:
      and: []
    state: present
- name: Create a pre-process rule that links duplicate events
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Link Related Malware Incidents
    action: link
    enabled: true
    state: present
- name: Create a pre-process rule that runs a script
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Custom Dedup Script Rule
    action: script
    script_id: DedupScript
    enabled: true
    state: present
- name: Disable a pre-process rule
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Duplicate Phishing Alerts
    action: drop
    enabled: false
    state: present
- name: Gather all pre-process rules
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    state: gathered
  register: all_rules
- name: Get a specific pre-process rule by name
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Duplicate Phishing Alerts
    state: gathered
  register: rule_info
- name: Delete a pre-process rule
  cortex.xsoar8.pre_process_rule:
    provider:
      server: https://api-company.crtx.de.paloaltonetworks.com
      api_key: your-api-key
      api_key_id: your-api-key-id
    name: Drop Duplicate Phishing Alerts
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
              May be null after creation or update if the API response does not
              contain a list with a matching rule.
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
            elements: str
            sample: []
        newEventFilters:
            description: Incoming-event conditions as lists of OR-connected conditions joined by AND.
            type: list
            elements: list
            sample: []
        readyNewEventFilters:
            description: Prepared incoming-event filters sent with the same content as C(newEventFilters).
            type: list
            elements: list
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
        self.filters = connection.module.params.get("filters")
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
        self.rule_filters = []
        if self.state == "present" and self.filters is not None:
            self.validate_filters()
            self.rule_filters = self.build_filters()
            self.fields_to_compare.extend((
                 ("newEventFilters", self.rule_filters),
                 ("readyNewEventFilters", self.rule_filters),
             ))

    def validate_filters(self):
        """Validate supplied filters against API metadata, failing on invalid conditions."""
        if not self.filters["and"]:
            return
        operator_definitions = self.get_rule_filters()
        if not isinstance(operator_definitions, dict) or not operator_definitions:
            self.module.fail_json(msg="Cannot validate filters: operator metadata is unavailable.")
        for group_index, filter_group in enumerate(self.filters["and"]):
            if not filter_group["or"]:
                self.module.fail_json(msg="Each filters.and group must contain at least one condition in or.")
            for condition_index, condition in enumerate(filter_group["or"]):
                condition_path = f"filters.and[{group_index}].or[{condition_index}]"
                operator_name = condition["operator"]
                if operator_name not in operator_definitions:
                    self.module.fail_json(msg=f"{condition_path}.operator: unknown operator '{operator_name}'.")
                operator_metadata = operator_definitions[operator_name]
                # Metadata must be a dict with a Boolean isSingleValue flag, otherwise the unary/binary check below is unreliable.
                if not isinstance(operator_metadata, dict) or not isinstance(operator_metadata.get("isSingleValue"), bool):
                    self.module.fail_json(msg=f"{condition_path}.operator: invalid metadata for '{operator_name}'.")
                right_value = (condition.get("right") or {}).get("value")
                if operator_metadata["isSingleValue"]:
                    if right_value is not None:
                        self.module.fail_json(msg=f"{condition_path}.right: Unary operator '{operator_name}' requires an empty operand.")
                elif right_value in (None, ""):
                    self.module.fail_json(msg=f"{condition_path}.right.value is required for operator '{operator_name}'.")

    def build_filters(self):
        """Convert validated filters to the API payload without fetching metadata."""
        groups = []
        for group in self.filters["and"]:
            conditions = []
            for condition in group["or"]:
                right = condition.get("right")
                right_payload = {}
                if right and right.get("value") is not None:
                    right_payload = {"value": {"simple": right["value"]}, "isContext": False}
                conditions.append({
                    "operator": condition["operator"],
                    "left": {"value": {"simple": condition["left"]["value"]}, "isContext": True},
                    "right": right_payload,
                    "type": condition["type"],
                })
            groups.append(conditions)
        return groups

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
            if self.filters is not None:
                raw_rule_data["newEventFilters"] = self.rule_filters
                raw_rule_data["readyNewEventFilters"] = self.rule_filters
            return raw_rule_data

        rule_data = {
            "action": self.action,
            "commitMessage": "Preprocess rule edited",
            "enabled": self.enabled,
            "existingEventsFilters": [],
            "id": "",
            "linkTo": "oldest",
            "name": self.name,
            "newEventFilters": self.rule_filters,
            "readyNewEventFilters": self.rule_filters,
            "searchClosed": False,
            "period": {"fromValue": 30, "by": "days"},
            "propagationLabels": self.propagation_labels or [],
            "scriptID": self.script_id,
            "shouldPublish": True,
            "shouldCommit": True,
        }

        return rule_data

    def get_rule_filters(self):
        """
        Returns the allowed filters to be used in Pre-Process Rules.

        Returns:
            dict: Allowed filters for Pre-Process Rules, or an empty dict on API failure.
        """
        try:
            return self.connection.request("GET", "/xsoar/preprocess/filters")
        except XSOARAPIError as e:
            self.module.log(msg=f"Failed to get pre-process rule filters: {to_text(e)}")
            return {}

    def get_pre_process_rules(self):
        """
        Retrieves Pre-Process Rules.

        Returns:
            list: Pre-Process Rule response from the API, or an empty list for non-list responses.
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
        for rule in self.get_pre_process_rules():
            if rule.get("name") == name:
                return rule
        return None

    def create_pre_process_rule(self, rule_data):
        """
        Creates a new Pre-Process Rule.

        Args:
            rule_data (dict): Data for the new Pre-Process Rule.

        Returns:
            dict | None: Matching created rule from the API response, or None if not found.
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
            dict | None: Matching updated rule from the API response, or None if not found.
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
            return self.connection.request("DELETE", f"/xsoar/preprocess/rule/{rule_id}")
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
    argument_spec.update(
        dict(
            action=dict(type="str", choices=["close", "drop", "dropAndUpdate", "link", "linkAndClose", "script"]),
            enabled=dict(type="bool", default=True),
            filters=dict(
                type="dict",
                options={
                    "and": dict(
                        type="list",
                        elements="dict",
                        required=True,
                        options={
                            "or": dict(
                                type="list",
                                elements="dict",
                                required=True,
                                options=dict(
                                    operator=dict(type="str", required=True),
                                    left=dict(
                                        type="dict",
                                        required=True,
                                        options=dict(
                                            value=dict(type="str", required=True),
                                        ),
                                    ),
                                    right=dict(
                                        type="dict",
                                        options=dict(
                                            value=dict(type="str"),
                                        ),
                                    ),
                                    type=dict(type="str", required=True),
                                ),
                            ),
                        },
                    ),
                },
            ),
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
