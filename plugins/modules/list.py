#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: list
short_description: Manage XSOAR 8 list objects
description:
    - Create, update, delete, and gather information about list objects in Cortex XSOAR 8.
    - Lists store reusable data such as IP addresses, domains, or structured JSON that can
      be referenced in playbooks and rules.
    - Supports multiple content types including Text, HTML, Markdown, CSS, and JSON.
    - Uses the XSOAR 8 REST API for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
    - Uses the /xsoar/public/v1/lists, /xsoar/public/v1/lists/save, and
      /xsoar/public/v1/lists/delete endpoints.
    - I(content) and I(json_content) are mutually exclusive.
    - When I(content_type) is C(JSON), both I(json_content) and I(name) are required, and I(content) must not be set.
    - I(json_content) accepts either a JSON object or a JSON array.
    - Setting I(read_roles) restricts read access to the specified roles and sets C(allRead) to C(false).
    - Setting I(edit_roles) restricts write access to the specified roles and sets C(allReadWrite) to C(false).
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    name:
        description:
            - The name of the list object.
            - Must be unique within the XSOAR instance.
            - Required when state is C(present) or C(absent).
        type: str
    content:
        description:
            - The text content of the list.
            - Mutually exclusive with I(json_content).
            - Use for I(content_type) values C(Text), C(HTML), C(Markdown), and C(CSS).
        type: str
        default: ""
    content_type:
        description:
            - The content type of the list.
            - When set to C(JSON), I(json_content) must be provided instead of I(content).
        type: str
        choices: ['JSON', 'HTML', 'Text', 'Markdown', 'CSS']
        default: "Text"
    description:
        description:
            - A human-readable description of the list.
        type: str
        default: ""
    json_content:
        description:
            - The structured JSON content of the list.
            - Can be either a JSON object or a JSON array.
            - Mutually exclusive with I(content).
            - Required when I(content_type) is C(JSON).
        type: raw
        default: null
    propagation_labels:
        description:
            - Labels used for list propagation in multi-tenant environments.
        type: list
        elements: str
        default: ["all"]
    read_roles:
        description:
            - Roles that have read-only access to the list.
            - When set, restricts read access to the specified roles only.
            - Stored in the API as C(xsoarReadOnlyRoles) with C(allRead) set to C(false).
        type: list
        elements: str
    edit_roles:
        description:
            - Roles that have read-write access to the list.
            - When set, restricts write access to the specified roles only.
            - Stored in the API as C(roles) with C(allReadWrite) set to C(false).
        type: list
        elements: str
    state:
        description:
            - The desired state of the list object.
            - C(present) - Create or update the list.
            - C(absent) - Delete the list.
            - C(gathered) - Retrieve information about existing lists.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a plain text list
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "blocked_ips"
    content: |
      192.168.1.100
      10.0.0.50
      172.16.0.1
    content_type: "Text"
    description: "List of blocked IP addresses"
    state: present

- name: Create a JSON list
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "threat_actors"
    content_type: "JSON"
    json_content:
      actors:
        - name: "Actor1"
          ttps: ["phishing", "malware"]
        - name: "Actor2"
          ttps: ["ransomware"]
    description: "Known threat actor information"
    state: present

- name: Create a list with role-based access restrictions
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "sensitive_domains"
    content: "internal.company.com"
    description: "Internal sensitive domains"
    read_roles:
      - "analyst"
      - "admin"
    edit_roles:
      - "admin"
    state: present

- name: Gather all lists
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_lists

- name: Get a specific list by name
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "blocked_ips"
    state: gathered
  register: blocked_ips_list

- name: Delete a list
  cortex.xsoar8.list:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "blocked_ips"
    state: absent
"""

RETURN = """
changed:
    description: Whether the list was created, updated, or deleted.
    returned: always
    type: bool
    sample: true
list:
    description: Information about the list object.
    returned: when state is present, when state is absent and the list existed,
              or when state is gathered and a matching list is found by name
    type: dict
    contains:
        id:
            description: The unique ID of the list.
            type: str
            sample: "12345678-1234-1234-1234-123456789abc"
        name:
            description: The name of the list.
            type: str
            sample: "blocked_ips"
        data:
            description: The content of the list as stored in the API.
            type: str
            sample: "192.168.1.100\n10.0.0.50"
        type:
            description: The content type of the list.
            type: str
            sample: "Text"
        description:
            description: The description of the list.
            type: str
            sample: "List of blocked IP addresses"
        propagationLabels:
            description: Propagation labels for multi-tenant environments.
            type: list
            sample: ["all"]
        roles:
            description: Roles with read-write access (maps to I(edit_roles)).
            type: list
            sample: ["admin"]
        xsoarReadOnlyRoles:
            description: Roles with read-only access (maps to I(read_roles)).
            type: list
            sample: ["analyst"]
lists:
    description: All list objects.
    returned: when state is gathered and no I(name) is specified
    type: list
    elements: dict
    sample: [{"id": "abc123", "name": "blocked_ips", "type": "Text"}]
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "List blocked_ips created successfully"
"""

import json
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


class XSOARListManager:
    """
    Manager class for XSOAR list object operations.
    """

    def __init__(self, connection):
        """
        Initialize the list manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.content = connection.module.params["content"]
        self.content_type = connection.module.params["content_type"]
        self.description = connection.module.params["description"]
        self.json_content = connection.module.params["json_content"]
        self.name = connection.module.params["name"]
        self.propagation_labels = connection.module.params["propagation_labels"]
        self.state = connection.module.params["state"]

        self.edit_roles = connection.module.params["edit_roles"]
        self.read_roles = connection.module.params["read_roles"]

        self.fields_to_compare = [
            ("name", self.name),
            ("description", self.description),
            ("propagationLabels", self.propagation_labels),
            ("type", self.content_type),
            ("roles", self.edit_roles),
            ("xsoarReadOnlyRoles", self.read_roles),
        ]

    def data_differs(self, current_list):
        """
        Return True when the desired list content differs from the API value.

        For C(JSON) lists the comparison parses the current ``data`` string and
        compares the deserialised structure to ``json_content``, so whitespace
        and key-ordering differences introduced by the server do not trigger
        spurious updates. For text-based content types a plain string compare
        is performed against ``content`` (with ``None`` normalised to ``""``).

        Args:
            current_list (dict): List object returned by the API.

        Returns:
            bool: True when the desired content differs from the current value.
        """
        current_data = current_list.get("data")
        if self.content_type == "JSON":
            try:
                if isinstance(current_data, (dict | list)):
                    current_parsed = current_data
                elif current_data:
                    current_parsed = json.loads(current_data)
                else:
                    current_parsed = None
            except (TypeError, ValueError):
                return True
            return current_parsed != self.json_content
        return (current_data or "") != (self.content or "")

    def get_all_lists(self):
        """
        Retrieve all lists from XSOAR.

        Returns:
            list: A list of all lists in XSOAR.
        """
        try:
            response = self.connection.request("GET", "/lists")
            return response if isinstance(response, list) else []
        except Exception as e:
            raise XSOARAPIError(f"Failed to get available lists: {to_text(e)}") from e

    def get_list_by_name(self, list_name):
        """
        Retrieve a list by its name.

        Args:
            list_name (str): The name of the list to retrieve.

        Returns:
            dict: The list object if found, else None.
        """
        lists = self.get_all_lists()
        for _list in lists:
            if _list.get("name") == list_name:
                return _list
        return None

    def create_list(self):
        """
        Create a new list in XSOAR.

        Returns:
            dict: The created list object.
        """
        if self.content_type == "JSON":
            content = json.dumps(self.json_content, indent=2)
        else:
            content = self.content or ""

        list_data = {
            "allRead": True,
            "allReadWrite": True,
            "data": content,
            "description": self.description,
            "name": self.name,
            "propagationLabels": self.propagation_labels,
            "type": self.content_type,
            "version": -1,
        }

        if self.read_roles:
            list_data.update({"xsoarReadOnlyRoles": self.read_roles, "allRead": False})

        if self.edit_roles:
            list_data.update({"roles": self.edit_roles, "allReadWrite": False})

        try:
            return self.connection.request("POST", "/lists/save", data=list_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to create list: {to_text(e)}") from e

    def update_list(self, current_list):
        """
        Update an existing list in XSOAR.

        Args:
            current_list (dict): Current list object, mainly to retrieve the list ID.

        Returns:
            dict: The updated list object.
        """
        if self.content_type == "JSON":
            content = json.dumps(self.json_content, indent=2)
        else:
            content = self.content or ""

        list_data = {
            "allRead": True,
            "allReadWrite": True,
            "data": content,
            "description": self.description,
            "id": current_list.get("id"),
            "name": self.name,
            "propagationLabels": self.propagation_labels,
            "type": self.content_type,
            "version": -1,
        }

        if self.read_roles:
            list_data.update({"xsoarReadOnlyRoles": self.read_roles, "allRead": False})

        if self.edit_roles:
            list_data.update({"roles": self.edit_roles, "allReadWrite": False})

        try:
            return self.connection.request("POST", "/lists/save", data=list_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to update list: {to_text(e)}") from e

    def delete_list(self, list_id):
        """
        Delete a list from XSOAR.

        Args:
            list_id (str): The ID of the list to delete.

        Returns:
            bool: True if successful.
        """
        try:
            self.connection.request("POST", "/lists/delete", {"id": list_id})
            return True
        except Exception as e:
            raise XSOARAPIError(f"Failed to delete list: {to_text(e)}") from e


def ensure_present(module, list_manager):
    """
    Ensure list object is present.

    Args:
        module: AnsibleModule instance
        list_manager: XSOARListManager instance

    Returns:
        dict: Result information
    """
    # Check if list exists
    if current_list := list_manager.get_list_by_name(list_name=list_manager.name):
        needs_update = instance_needs_update(current_list, list_manager.fields_to_compare) or list_manager.data_differs(
            current_list
        )
        if module.check_mode:
            # Only report what would happen, do not update
            if needs_update:
                result = {
                    "changed": True,
                    "msg": f"List {list_manager.name} would be updated",
                    "list": current_list,
                }
            else:
                result = {
                    "changed": False,
                    "msg": f"List {list_manager.name} is already up to date (check mode)",
                    "list": current_list,
                }
        elif needs_update:
            updated_list = list_manager.update_list(current_list)
            result = {
                "changed": True,
                "msg": f"List {list_manager.name} updated successfully",
                "list": updated_list,
            }
        else:
            result = {"changed": False, "msg": f"List {list_manager.name} is already up to date", "list": current_list}
    else:
        if module.check_mode:
            # Project an API-shaped object so downstream playbooks get the same
            # keys in check mode as they do for a real create.
            projected = {
                "name": list_manager.name,
                "description": list_manager.description,
                "type": list_manager.content_type,
                "propagationLabels": list_manager.propagation_labels,
                "roles": list_manager.edit_roles,
                "xsoarReadOnlyRoles": list_manager.read_roles,
                "data": (
                    json.dumps(list_manager.json_content, indent=2)
                    if list_manager.content_type == "JSON"
                    else (list_manager.content or "")
                ),
            }
            result = {
                "changed": True,
                "msg": f"List {list_manager.name} would be created",
                "list": projected,
            }
        else:
            created_list = list_manager.create_list()
            result = {
                "changed": True,
                "msg": f"List {list_manager.name} created successfully",
                "list": created_list,
            }

    return result


def ensure_absent(module, list_manager):
    """
    Ensure list object is absent.

    Args:
        module: AnsibleModule instance
        list_manager: XSOARListManager instance

    Returns:
        dict: Result information
    """
    # Check if list exists
    if current_list := list_manager.get_list_by_name(list_manager.name):
        if module.check_mode:
            result = {"changed": True, "msg": f"List {list_manager.name} would be deleted", "list": current_list}
        else:
            list_manager.delete_list(current_list["id"])
            result = {
                "changed": True,
                "msg": f"List {list_manager.name} deleted successfully",
                "list": current_list,
            }
    else:
        result = {"changed": False, "msg": f"List {list_manager.name} does not exist"}

    return result


def gather_lists(list_manager):
    """
    Gather list object information.

    Args:
        list_manager: XSOARListManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    # Get specific list name
    if list_manager.name:
        if _list := list_manager.get_list_by_name(list_manager.name):
            result["list"] = _list
            result["msg"] = f"List {list_manager.name} found"
        else:
            result["msg"] = f"List {list_manager.name} not found"
    else:
        # Get all lists
        lists = list_manager.get_all_lists()
        result["lists"] = lists
        result["msg"] = f"Retrieved {len(lists)} lists"

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            content=dict(type="str", default=None),
            content_type=dict(type="str", choices=["JSON", "HTML", "Text", "Markdown", "CSS"], default="Text"),
            description=dict(type="str", default=""),
            edit_roles=dict(type="list", elements="str"),
            json_content=dict(type="raw", default=None),
            name=dict(type="str"),
            propagation_labels=dict(type="list", elements="str", default=["all"]),
            read_roles=dict(type="list", elements="str"),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[("content", "json_content")],
        required_if=[
            ("state", "present", ["name"]),
            ("state", "absent", ["name"]),
            ("content_type", "JSON", ("json_content", "name")),
        ],
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create list manager
    try:
        connection = get_connection(module)
        list_manager = XSOARListManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if list_manager.state == "present":
            result = ensure_present(module, list_manager)
        elif list_manager.state == "absent":
            result = ensure_absent(module, list_manager)
        else:  # gathered
            result = gather_lists(list_manager)
    except Exception as e:
        module.fail_json(msg=f"Module execution failed: {to_text(e)}", exception=traceback.format_exc())
    finally:
        try:
            connection.close()
        except Exception:
            pass

    # Return result
    module.exit_json(**result)


if __name__ == "__main__":
    main()
