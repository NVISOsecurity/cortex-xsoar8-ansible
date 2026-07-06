#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: api_key
short_description: Manage XSOAR 8 API keys
description:
    - Create, delete, and gather information about API keys in Cortex XSOAR 8.
    - When state is C(present) and a I(comment) is provided, the module checks whether an API key
      with that comment already exists and skips creation if it does.
    - Uses the Cortex XSOAR public API endpoints for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
    - Uses the /public_api/v1/api_keys/get_api_keys, /public_api/v1/api_keys/generate,
      and /public_api/v1/api_keys/delete endpoints.
    - State C(present) creates a new API key unless a key with the same I(comment) already exists.
    - I(request_data) is required when state is C(present) or C(absent).
    - I(request_data.filters) is only valid with state C(absent) and C(gathered).
    - Direct I(request_data) fields (I(roles), I(security_level), I(expiration), I(set_max_expiration),
      I(comment)) are only valid with state C(present).
    - When state is C(gathered) and I(request_data) is omitted, returns all non-expired API keys.
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    request_data:
        description:
            - Request payload controlling API key creation, deletion, or filtering.
            - Required when state is C(present) or C(absent); optional for C(gathered).
            - Use direct sub-keys (I(roles), I(security_level), I(expiration), I(set_max_expiration),
              I(comment)) when state is C(present).
            - Use I(filters) when state is C(absent) or C(gathered).
        type: dict
        required: false
        suboptions:
            filters:
                description:
                    - List of filter objects used to query or delete API keys.
                    - Only valid when state is C(absent) or C(gathered).
                type: list
                elements: dict
                required: false
                suboptions:
                    field:
                        description: The API key attribute to filter on.
                        type: str
                        choices: ['expiration', 'roles', 'id']
                        required: true
                    operator:
                        description:
                            - The comparison operator for the filter.
                            - Use C(gte) or C(lte) with I(expiration).
                            - Use C(contains) with I(roles).
                            - Use C(in) with I(id).
                        type: str
                        choices: ['gte', 'lte', 'contains', 'in']
                        required: true
                    value:
                        description:
                            - The filter value.
                            - Integer epoch milliseconds for I(expiration).
                            - List of role name strings for I(roles).
                            - List of integer API key IDs for I(id).
                        type: raw
                        required: true
            roles:
                description:
                    - Roles to assign to the new API key.
                    - Only valid when state is C(present).
                type: list
                elements: str
                required: false
            security_level:
                description:
                    - Security level for the new API key.
                    - Only valid when state is C(present).
                type: str
                choices: ['standard', 'advanced']
                required: false
            expiration:
                description:
                    - Expiration timestamp for the new API key as epoch milliseconds.
                    - Overridden by I(set_max_expiration) if both are provided.
                    - If neither I(expiration) nor I(set_max_expiration) is set, the API default applies.
                    - Only valid when state is C(present).
                type: int
                required: false
            set_max_expiration:
                description:
                    - If C(true), sets the expiration to the maximum allowed value (6 months from now).
                    - Overrides any value in I(expiration).
                    - Only valid when state is C(present).
                type: bool
                required: false
            comment:
                description:
                    - A comment or label to attach to the API key.
                    - Only valid when state is C(present).
                type: str
                required: false
    state:
        description:
            - The desired state.
            - C(present) - Create a new API key.
            - C(absent) - Delete API key(s) matching the provided I(filters).
            - C(gathered) - Retrieve information about existing API keys.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create an API key with standard security level
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      roles:
        - "analyst"
        - "admin"
      security_level: "standard"
      comment: "Automation key for CI/CD pipeline"
    state: present
  register: new_key

- name: Create an API key with maximum expiration (6 months)
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      roles:
        - "analyst"
      security_level: "advanced"
      set_max_expiration: true
      comment: "Long-lived automation key"
    state: present
  register: new_key

- name: Delete API keys by ID
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: "id"
          operator: "in"
          value: [1001, 1002]
    state: absent

- name: Gather all non-expired API keys
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_keys

- name: Gather API keys assigned to a specific role
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: "roles"
          operator: "contains"
          value: ["analyst"]
    state: gathered
  register: analyst_keys

- name: Gather API keys expiring before a specific timestamp
  cortex.xsoar8.api_key:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: "expiration"
          operator: "lte"
          value: 1767225600000
    state: gathered
  register: expiring_keys
"""

RETURN = """
changed:
    description: Whether an API key was created or deleted.
    returned: always
    type: bool
    sample: true
api_key:
    description: >
        Information about the created API key.
        The C(key) field contains the plaintext API key value and is only available at
        creation time — it cannot be retrieved later. Store it securely immediately.
    returned: when state is C(present) and C(changed) is True
    type: dict
    contains:
        id:
            description: The numeric ID of the created API key.
            type: int
            sample: 1001
        key:
            description: The plaintext API key value. Only available at creation time.
            type: str
            sample: "xsoar-api-key-abc123..."
api_keys:
    description: List of API key objects matching the query.
    returned: when state is gathered and API keys are found
    type: list
    elements: dict
    contains:
        id:
            description: The numeric ID of the API key.
            type: int
            sample: 1001
        roles:
            description: Roles assigned to the API key.
            type: list
            sample: ["analyst"]
        security_level:
            description: Security level of the API key.
            type: str
            sample: "standard"
        expiration:
            description: Expiration timestamp in epoch milliseconds.
            type: int
            sample: 1767225600000
        comment:
            description: Comment attached to the API key.
            type: str
            sample: "Automation key for CI/CD pipeline"
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Api key with ID 1001 created"
"""

import traceback
from calendar import monthrange
from datetime import UTC, datetime, timedelta

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


class XSOARApiKeyManager:
    """
    Manager class for XSOAR API key operations.
    """

    def __init__(self, connection):
        """
        Initialize the API key manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module
        self.request_data = connection.module.params["request_data"] or {}
        self.state = connection.module.params["state"]
        if self.request_data:
            self.validate_request_data()

    def validate_request_data(self):
        """Validate request_data shape and prepare reusable request payload."""
        # Ansible normalizes all declared options keys to None when not provided,
        # so check value is not None rather than key presence
        has_filters = self.request_data.get("filters") is not None
        has_direct_fields = any(
            self.request_data.get(key) is not None
            for key in [
                "roles",
                "security_level",
                "expiration",
                "set_max_expiration",
                "comment",
            ]
        )

        if has_filters and has_direct_fields:
            self.module.fail_json(
                msg=(
                    "request_data must contain either 'filters' or direct keys "
                    "(roles, security_level, expiration, set_max_expiration, comment), not both"
                )
            )

        if self.state == "present":
            if has_filters:
                self.module.fail_json(msg="state=present does not support request_data.filters.")
            validated_request_data = self.validate_direct_fields()
        else:
            if has_direct_fields:
                self.module.fail_json(msg="state=absent or state=gathered do not support direct request_data fields.")
            validated_request_data = self.validate_request_filters()

        self.prepared_request_data = {"request_data": validated_request_data}
        return

    @staticmethod
    def get_max_expiration_epoch_ms():
        """Return a backend-safe max expiration epoch ms for 6 months semantics."""
        now = datetime.now(UTC)
        month_index = now.month - 1 + 6
        target_year = now.year + (month_index // 12)
        target_month = (month_index % 12) + 1
        target_day = min(now.day, monthrange(target_year, target_month)[1])
        calendar_six_months = now.replace(year=target_year, month=target_month, day=target_day)

        day_based_six_months = now + timedelta(days=180)
        max_expiration = min(calendar_six_months, day_based_six_months) - timedelta(minutes=5)

        return int(max_expiration.timestamp() * 1000)

    @staticmethod
    def get_today_epoch_ms():
        """Return today's date at 00:00:00 UTC as epoch milliseconds."""
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(today.timestamp() * 1000)

    def validate_request_filters(self):
        """Validate request_data.filters and return normalized request_data payload."""
        if not (filters := self.request_data.get("filters")) or not isinstance(filters, list):
            self.module.fail_json(msg="Invalid request_data.filters. Expected a non-empty array of filter objects.")

        normalized_filters = []

        for index, filter_item in enumerate(filters):
            if not isinstance(filter_item, dict):
                self.module.fail_json(msg=f"Invalid filters[{index}]. Expected object with field/operator/value.")

            field = filter_item.get("field")
            operator = filter_item.get("operator")
            value = filter_item.get("value")

            if field == "expiration":
                if operator not in ("gte", "lte"):
                    self.module.fail_json(
                        msg=f"Invalid operator '{operator}' for filters[{index}].expiration. Use 'gte' or 'lte'."
                    )
                if not isinstance(value, int):
                    self.module.fail_json(
                        msg=f"Invalid value type for filters[{index}].expiration. Expected integer epoch milliseconds."
                    )

            elif field == "roles":
                if operator != "contains":
                    self.module.fail_json(
                        msg=f"Invalid operator '{operator}' for filters[{index}].roles. Use 'contains'."
                    )
                if not isinstance(value, list) or not all(isinstance(role, str) for role in value):
                    self.module.fail_json(
                        msg=f"Invalid value type for filters[{index}].roles. Expected array of role strings."
                    )

            elif field == "id":
                if operator != "in":
                    self.module.fail_json(msg=f"Invalid operator '{operator}' for filters[{index}].id. Use 'in'.")
                if not isinstance(value, list) or not all(isinstance(api_key_id, int) for api_key_id in value):
                    self.module.fail_json(
                        msg=f"Invalid value type for filters[{index}].id. Expected array of API key IDs (integers)."
                    )

            normalized_filters.append(
                {
                    "field": field,
                    "operator": operator,
                    "value": value,
                }
            )

        return {"filters": normalized_filters}

    def validate_direct_fields(self):
        """Validate direct request_data fields and return normalized request_data payload."""
        normalized_data = {}

        if (expiration := self.request_data.get("expiration")) is not None:
            if not isinstance(expiration, int):
                self.module.fail_json(msg="Invalid request_data.expiration. Expected integer epoch milliseconds.")
            normalized_data["expiration"] = expiration

        # if set_max_expiration is true, it overrides any provided expiration value
        # with the maximum allowed expiration (6 months from now)
        # if both fields are missing a default expiration of 1 week is applied by the API
        if (set_max_expiration := self.request_data.get("set_max_expiration")) is not None and not isinstance(
            set_max_expiration, bool
        ):
            self.module.fail_json(msg="Invalid request_data.set_max_expiration. Expected boolean.")
        if set_max_expiration:
            normalized_data["expiration"] = self.get_max_expiration_epoch_ms()

        if (roles := self.request_data.get("roles")) is not None:
            if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
                self.module.fail_json(msg="Invalid request_data.roles. Expected array of role strings.")
            normalized_data["roles"] = roles

        if (level := self.request_data.get("security_level")) is not None:
            if level not in ("standard", "advanced"):
                self.module.fail_json(msg="Invalid request_data.security_level. Use 'standard' or 'advanced'.")
            normalized_data["security_level"] = level

        if (comment := self.request_data.get("comment")) is not None:
            if not isinstance(comment, str):
                self.module.fail_json(msg="Invalid request_data.comment. Expected string.")
            normalized_data["comment"] = comment

        if not normalized_data:
            self.module.fail_json(
                msg=(
                    "request_data must include either 'filters' or at least one direct key "
                    "(roles, security_level, expiration, set_max_expiration, comment)."
                )
            )

        return normalized_data

    def get_api_keys(self, request_data=None):
        """
        Get all API key objects.

        Args:
            request_data (dict): Optional request data containing filters.

        Returns:
            list: List of API key objects
        """
        if request_data is not None:
            data = request_data
        else:
            data = {
                "request_data": {
                    "filters": [
                        {
                            "field": "expiration",
                            "operator": "gte",
                            "value": self.get_today_epoch_ms(),
                        }
                    ]
                }
            }
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/api_keys/get_api_keys",
                data=data,
            )
            # Extract API keys from response and return
            if isinstance(response, dict):
                return response.get("reply", {}).get("DATA", [])
            return []
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to retrieve API keys: {to_text(e)}")

    def create_api_key(self):
        """
        Create a new API key with provided request_data.

        Returns:
            dict: Created API key object
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/api_keys/generate",
                data=self.prepared_request_data,
            )
            # Extract created API key from response and return
            if isinstance(response, dict):
                return response.get("reply", {})  # Contains id and key value
            return {}
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to create API key: {to_text(e)}")

    def delete_api_key(self):
        """
        Delete an API key by ID.

        Returns:
            int: Number of deleted API keys
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/api_keys/delete",
                data=self.prepared_request_data,
            )
            # The API does not always populate update_count; coerce to int so callers
            # can safely compare against thresholds without a TypeError.
            if isinstance(response, dict):
                return int(response.get("reply", {}).get("update_count") or 0)
            return 0
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to delete API key(s): {to_text(e)}")

    def key_exists(self, api_keys, api_key_comment):
        """
        Check if an API key with the given comment exists.

        Args:
            api_keys (list): List of API key objects
            api_key_comment (str): The comment of the API key to check.

        Returns:
            bool: True if the API key exists, False otherwise.
        """
        return any(api_key.get("comment") == api_key_comment for api_key in api_keys)


def ensure_present(module, api_key_manager):
    """
    Ensure API key is present.

    Args:
        module: AnsibleModule instance
        api_key_manager: XSOARApiKeyManager instance

    Returns:
        dict: Result information
    """
    if (comment := api_key_manager.request_data.get("comment")) and api_key_manager.key_exists(
        api_key_manager.get_api_keys(),
        comment,
    ):
        result = {
            "changed": False,
            "msg": f'Api key with comment "{comment}" already exists',
        }
    else:
        if module.check_mode:
            # Project the same shape as the real-mode result: a flat dict with
            # id/key (unknown in check mode) merged with the requested fields,
            # rather than the wrapped {"request_data": {...}} payload.
            result = {
                "changed": True,
                "msg": "Api key would be created",
                "api_key": {
                    "id": None,
                    "key": None,
                    **api_key_manager.prepared_request_data["request_data"],
                },
            }
        else:
            api_key = api_key_manager.create_api_key()
            result = {
                "changed": True,
                "msg": f'Api key with ID {api_key.get("id")} created',
                "api_key": api_key,  # Contains created API key info including plaintext key value
            }

    return result


def ensure_absent(module, api_key_manager):
    """
    Ensure API key is absent.

    Args:
        module: AnsibleModule instance
        api_key_manager: XSOARApiKeyManager instance

    Returns:
        dict: Result information
    """
    ids = (
        [f.get("value", []) for f in api_key_manager.request_data.get("filters", []) if f.get("field") == "id"] or [[]]
    )[0]
    if module.check_mode:
        matching_keys = api_key_manager.get_api_keys(api_key_manager.prepared_request_data)
        result = {
            "changed": bool(matching_keys),
            "msg": (
                f"Api key(s) with ID(s) {ids} would be deleted"
                if matching_keys
                else f"Api key(s) with ID(s) {ids} do not exist"
            ),
        }
    else:
        matching_keys = api_key_manager.get_api_keys(api_key_manager.prepared_request_data)
        if not matching_keys:
            result = {
                "changed": False,
                "msg": f"Api key(s) with ID(s) {ids} do not exist",
            }
        else:
            keys_deleted = api_key_manager.delete_api_key()
            result = {
                "changed": keys_deleted > 0,
                "msg": f"{keys_deleted} Api key(s) with ID(s) {ids} deleted",
            }

    return result


def gather_api_keys(api_key_manager):
    """
    Gather API key information.

    Args:
        api_key_manager: XSOARApiKeyManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    if api_key_manager.request_data.get("filters"):
        api_keys = api_key_manager.get_api_keys(api_key_manager.prepared_request_data)
    else:
        api_keys = api_key_manager.get_api_keys()

    if api_keys:
        result["api_keys"] = api_keys
        result["msg"] = f"Retrieved {len(api_keys)} API keys."
    else:
        result["msg"] = "No API keys found."

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            request_data=dict(
                type="dict",
                required=False,
                default=None,
                options=dict(
                    filters=dict(
                        type="list",
                        elements="dict",
                        required=False,
                        options=dict(
                            field=dict(
                                type="str",
                                choices=["expiration", "roles", "id"],
                                required=True,
                            ),
                            operator=dict(
                                type="str",
                                choices=["gte", "lte", "contains", "in"],
                                required=True,
                            ),
                            value=dict(type="raw", required=True),
                        ),
                    ),
                    roles=dict(type="list", elements="str", required=False),
                    security_level=dict(type="str", choices=["standard", "advanced"], required=False),
                    expiration=dict(type="int", required=False),
                    set_max_expiration=dict(type="bool", required=False),
                    comment=dict(type="str", required=False),
                ),
            ),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not module.params.get("request_data") and module.params.get("state") != "gathered":
        module.fail_json(msg="request_data is required and must be populated.")

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create api key manager
    try:
        connection = get_connection(module)
        api_key_manager = XSOARApiKeyManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if api_key_manager.state == "present":
            result = ensure_present(module, api_key_manager)
        elif api_key_manager.state == "absent":
            result = ensure_absent(module, api_key_manager)
        else:  # gathered
            result = gather_api_keys(api_key_manager)
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
