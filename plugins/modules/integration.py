#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: integration
short_description: Manage XSOAR 8 SaaS integration instances
description:
    - Create, update, delete, and gather information about integration instances in Cortex XSOAR 8 SaaS.
    - Integration instances are configured instances of integrations (brands) that provide specific functionality.
    - Supports managing integration configuration, enabling/disabling instances, and credential assignment.
    - Uses the XSOAR 8 SaaS REST API endpoints for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 SaaS instance with appropriate API permissions.
    - Uses the /xsoar/public/v1/settings/integration, /xsoar/public/v1/settings/integration/search,
      and /xsoar/public/v1/settings/integration-commands endpoints.
    - Integration instances require a valid integration brand to be available in the system.
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    name:
        description:
            - The name of the integration instance.
            - Must be unique within the XSOAR instance.
            - At least one of I(name) or I(instance_id) is required when state is C(present) or C(absent).
        type: str
        required: false
    instance_id:
        description:
            - The unique ID of the integration instance.
            - Can be used instead of I(name) to identify an existing instance.
            - At least one of I(name) or I(instance_id) is required when state is C(present) or C(absent).
        type: str
        required: false
    brand:
        description:
            - The brand/type of the integration (e.g., 'VirusTotal', 'Splunk', 'Active Directory Query v2').
            - Required when creating a new integration instance.
            - Must match an available integration brand in the system.
            - Ignored when updating an existing instance; the brand is preserved from the existing instance.
        type: str
        required: false
    enabled:
        description:
            - Whether the integration instance should be enabled.
            - Enabled instances can execute commands and fetch data.
        type: bool
        default: true
    configuration:
        description:
            - Configuration parameters for the integration instance.
            - These are integration-specific settings like API keys, server URLs, credentials, etc.
            - The required parameters depend on the specific integration brand.
            - Plain values are passed as-is (strings, numbers, booleans).
            - To reference a named credential stored in XSOAR, use a dict with a C(credential) key,
                            e.g. C({credential:my_credential_name}).
            - To supply an inline password credential, use a dict with a C(password) key and an
                            optional C(identifier) key, e.g. C({password:secret,identifier:username}).
        type: dict
        default: {}
    engine:
        description:
            - The engine to run this integration instance on.
            - If not specified, uses the default engine assignment.
        type: str
        default: ""
    engine_group:
        description:
            - The engine group to run this integration instance on.
            - Used for load balancing across multiple engines.
        type: str
        default: ""
    default_ignore:
        description:
            - If true, the integration instance is ignored by default and must be explicitly referenced in tasks.
        type: bool
        default: false
    incoming_mapper_id:
        description:
            - The ID of the incoming mapper to use for this integration instance.
            - Maps incoming data to the XSOAR incident schema.
        type: str
        default: ""
    propagation_labels:
        description:
            - Labels used for instance propagation in multi-tenant environments.
        type: list
        elements: str
        default: ["all"]
    get_available:
        description:
            - When true and state is 'gathered', returns all available integration brands.
            - Useful for discovering what integration types are available for configuration.
        type: bool
        default: false
    state:
        description:
            - The desired state of the integration instance.
            - C(present) - Create or update the integration instance.
            - C(absent) - Delete the integration instance.
            - C(gathered) - Retrieve information about existing integration instances.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Get all available integration types
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    get_available: true
    state: gathered
  register: available_integrations

- name: Create a VirusTotal integration instance
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "VirusTotal_Production"
    brand: "VirusTotal"
    enabled: true
    configuration:
      apikey: "your-virustotal-api-key"
      reliability: "B - Usually reliable"
      threshold: 10
      longRunning: false
      integrationReliability: "B - Usually reliable"
    state: present
  register: vt_integration

- name: Gather all integration instances
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_integrations

- name: Get specific integration instance by name
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "VirusTotal_Production"
    state: gathered
  register: vt_integration_info

- name: Update integration configuration
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "VirusTotal_Production"
    configuration:
      apikey: "updated-virustotal-api-key"
      reliability: "A - Completely reliable"
      threshold: 5
    state: present

- name: Disable an integration instance
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "VirusTotal_Production"
    enabled: false
    state: present

- name: Create integration with a stored credential reference
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Splunk_Main"
    brand: "SplunkPy"
    enabled: true
    configuration:
      host: "splunk.company.com"
      port: 8089
      authentication:
        credential: "splunk_creds"
    state: present

- name: Delete integration instance
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "VirusTotal_Production"
    state: absent

- name: Delete integration by instance ID
  cortex.xsoar8.integration:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    instance_id: "12345678-1234-1234-1234-123456789abc"
    state: absent
"""

RETURN = """
changed:
    description: Whether the integration instance was changed.
    returned: always
    type: bool
    sample: true
integration:
    description: Information about the integration instance.
    returned: when state is present or gathered (single instance)
    type: dict
    contains:
        id:
            description: The unique ID of the integration instance
            type: str
            sample: "12345678-1234-1234-1234-123456789abc"
        name:
            description: The name of the integration instance
            type: str
            sample: "VirusTotal_Production"
        brand:
            description: The brand/type of the integration
            type: str
            sample: "VirusTotal"
        enabled:
            description: Whether the integration instance is enabled
            type: str
            sample: "true"
        category:
            description: The category of the integration
            type: str
            sample: "Data Enrichment & Threat Intelligence"
        engine:
            description: The engine assignment
            type: str
            sample: "default"
        version:
            description: The version of the integration instance
            type: int
            sample: 42
        modified:
            description: Last modification timestamp
            type: str
            sample: "2024-11-17T10:30:00.000Z"
integrations:
    description: List of integration instances.
    returned: when state is gathered (multiple instances)
    type: list
    elements: dict
    sample: [
        {
            "id": "12345678-1234-1234-1234-123456789abc",
            "name": "VirusTotal_Production",
            "brand": "VirusTotal",
            "enabled": "true",
            "category": "Data Enrichment & Threat Intelligence"
        }
    ]
available_integrations:
    description: List of available integration brands that can be configured.
    returned: when state is gathered and get_available is true
    type: list
    elements: dict
    contains:
        id:
            description: Integration brand identifier
            type: str
            sample: "VirusTotal"
        name:
            description: Integration brand name
            type: str
            sample: "VirusTotal"
        display:
            description: Display name of the integration
            type: str
            sample: "VirusTotal"
        category:
            description: Category of the integration
            type: str
            sample: "Data Enrichment & Threat Intelligence"
        description:
            description: Description of the integration
            type: str
            sample: "Analyze suspicious files and URLs..."
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Integration instance created successfully"
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


class XSOARIntegrationManager:
    """
    Manager class for XSOAR integration instance operations.
    """

    def __init__(self, connection):
        """
        Initialize the integration manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.brand = connection.module.params["brand"]
        self.configuration = self._build_configuration_data(connection.module.params["configuration"])
        self.default_ignore = connection.module.params["default_ignore"]
        self.enabled = connection.module.params["enabled"]
        self.engine = connection.module.params["engine"]
        self.engine_group = connection.module.params["engine_group"]
        self.get_available = connection.module.params["get_available"]
        self.incoming_mapper_id = connection.module.params["incoming_mapper_id"]
        self.instance_id = connection.module.params["instance_id"]
        self.name = connection.module.params["name"]
        self.propagation_labels = connection.module.params["propagation_labels"]
        self.state = connection.module.params["state"]

        self.fields_to_compare = [
            ("data", self.configuration),
            ("defaultIgnore", self.default_ignore),
            ("enabled", str(self.enabled).lower()),
            ("propagationLabels", self.propagation_labels),
        ]
        # Only compare optional identifiers / engine bindings when the user actually
        # supplied them. Comparing module defaults (empty string / None) against
        # API responses that omit the field caused a perpetual changed=True loop.
        if self.name:
            self.fields_to_compare.append(("name", self.name))
        if self.brand:
            self.fields_to_compare.append(("brand", self.brand))
        if self.engine:
            self.fields_to_compare.append(("engine", self.engine))
        if self.engine_group:
            self.fields_to_compare.append(("engineGroup", self.engine_group))
        if self.incoming_mapper_id:
            self.fields_to_compare.append(("incomingMapperId", self.incoming_mapper_id))

    def _build_configuration_data(self, configuration):
        """
        Build configuration data structure for API requests.

        Formats configuration items, with special handling for password/credential fields.
        Password fields are marked with 'type': 9 and restructured as credential objects.

        Args:
            configuration (dict): Configuration dictionary

        Returns:
            list: List of configuration items in the format [{'name': k, 'value': v, 'type': t}, ...]
        """
        config_data = []

        for name, raw_value in configuration.items():
            item = {"name": name, "value": raw_value}

            if isinstance(raw_value, dict):
                password = raw_value.get("password")
                credential = raw_value.get("credential")

                if password:
                    item["value"] = {"password": password}
                    identifier = raw_value.get("identifier")
                    if identifier:
                        item["value"]["identifier"] = identifier
                    item["type"] = 9
                elif credential:
                    item["value"] = {"credential": credential}
                    item["type"] = 9

            config_data.append(item)

        return config_data

    def get_available_integrations(self):
        """
        Get all available integration brands.

        Returns:
            list: List of available integration brands
        """
        try:
            response = self.connection.request("GET", "/settings/integration-commands")
            return response if isinstance(response, list) else []
        except Exception as e:
            raise XSOARAPIError(f"Failed to get available integrations: {to_text(e)}") from e

    def get_all_instances(self):
        """
        Get all integration instances.

        Returns:
            list: List of integration instances
        """
        try:
            response = self.connection.request("POST", "/settings/integration/search", data={})

            # Extract instances from configurations
            if isinstance(response, dict):
                return response.get("instances", [])
            return []
        except Exception as e:
            raise XSOARAPIError(f"Failed to get integration instances: {to_text(e)}") from e

    def get_instance_by_name(self, name):
        """
        Get integration instance by name.

        Args:
            name (str): Instance name

        Returns:
            dict: Integration instance data or None if not found
        """
        instances = self.get_all_instances()

        for instance in instances:
            if instance.get("name") == name:
                return instance

        return None

    def get_instance_by_id(self, instance_id):
        """
        Get integration instance by ID.

        Args:
            instance_id (str): Instance ID

        Returns:
            dict: Integration instance data or None if not found
        """
        try:
            response = self.connection.request(
                "POST", "/settings/integration/search", data={}, params={"id": instance_id}
            )

            if isinstance(response, dict) and "instances" in response:
                instances = response["instances"]
                if instances:
                    return instances[0]
            return None
        except Exception as e:
            raise XSOARAPIError(f"Failed to get integration instance by ID: {to_text(e)}") from e

    def instance_exists(self, name=None, instance_id=None):
        """
        Check if an integration instance exists.

        Args:
            name (str): Instance name
            instance_id (str): Instance ID

        Returns:
            tuple: (exists, instance_data)
        """
        instance = None
        if name:
            instance = self.get_instance_by_name(name)
        elif instance_id:
            instance = self.get_instance_by_id(instance_id)
        if instance:
            return True, instance
        return False, None

    def create_instance(self):
        """
        Create a new integration instance.

        Returns:
            dict: Created instance information
        """
        # Build the instance data
        instance_data = {
            "brand": self.brand,
            "data": self.configuration,
            "defaultIgnore": self.default_ignore,
            "enabled": str(self.enabled).lower(),
            "isIntegrationScript": True,
            "name": self.name,
            "propagationLabels": self.propagation_labels,
            "version": 0,
        }

        instance_data.update(
            {
                k: v
                for k, v in {
                    "engine": self.engine,
                    "engineGroup": self.engine_group,
                    "incomingMapperId": self.incoming_mapper_id,
                }.items()
                if v
            }
        )

        try:
            return self.connection.request("PUT", "/settings/integration", data=instance_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to create integration instance: {to_text(e)}") from e

    def update_instance(self, current_instance):
        """
        Update an existing integration instance.

        Args:
            current_instance (dict): Current instance data to use as a base for updates

        Returns:
            dict: Updated instance information
        """
        # Merge desired values into the current schema items to preserve type
        # metadata. The XSOAR API uses the 'type' field to interpret values
        # correctly (e.g. type 8 for booleans). Omitting it causes the API to
        # silently ignore the submitted value and keep the existing one.
        current_schema = {item["name"]: item for item in current_instance.get("data", [])}
        data_payload = [
            {**current_schema[item["name"]], "value": item["value"]} if item["name"] in current_schema else item
            for item in self.configuration
        ]

        instance_data = {
            "brand": current_instance.get("brand"),
            "data": data_payload,
            "defaultIgnore": self.default_ignore,
            "enabled": str(self.enabled).lower(),
            "id": self.instance_id or current_instance.get("id"),
            "isIntegrationScript": True,
            "name": self.name or current_instance.get("name"),
            "propagationLabels": self.propagation_labels,
            "version": -1,
        }

        instance_data.update(
            {
                k: v
                for k, v in {
                    "engine": self.engine or current_instance.get("engine"),
                    "engineGroup": self.engine_group or current_instance.get("engineGroup"),
                    "incomingMapperId": self.incoming_mapper_id or current_instance.get("incomingMapperId"),
                }.items()
                if v
            }
        )

        try:
            return self.connection.request("PUT", "/settings/integration", data=instance_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to update integration instance: {to_text(e)}") from e

    def delete_instance(self, instance_id):
        """
        Delete an integration instance.

        Args:
            instance_id (str): Instance ID to delete

        Returns:
            bool: True if successful
        """
        try:
            self.connection.request("DELETE", f"/settings/integration/{instance_id}")
            return True
        except Exception as e:
            raise XSOARAPIError(f"Failed to delete integration instance: {to_text(e)}") from e


def ensure_present(module, integration_manager):
    """
    Ensure integration instance is present.

    Args:
        module: AnsibleModule instance
        integration_manager: XSOARIntegrationManager instance

    Returns:
        dict: Result information
    """
    if not integration_manager.name and not integration_manager.instance_id:
        module.fail_json(msg="Either 'name' or 'instance_id' is required when state is present")

    result = {}

    # Check if instance exists
    if integration_manager.instance_id:
        exists, current_instance = integration_manager.instance_exists(instance_id=integration_manager.instance_id)
        identifier = integration_manager.instance_id
    else:
        exists, current_instance = integration_manager.instance_exists(name=integration_manager.name)
        identifier = integration_manager.name

    if exists:
        if module.check_mode:
            # Only report what would happen, do not update
            if instance_needs_update(current_instance, integration_manager.fields_to_compare):
                result = {
                    "changed": True,
                    "msg": f"Integration instance {identifier} would be updated",
                    "integration": current_instance,
                }
            else:
                result = {
                    "changed": False,
                    "msg": f"Integration instance {identifier} is already up to date (check mode)",
                    "integration": current_instance,
                }
        elif instance_needs_update(current_instance, integration_manager.fields_to_compare):
            updated_instance = integration_manager.update_instance(current_instance)
            result = {
                "changed": True,
                "msg": f"Integration instance {identifier} updated successfully",
                "integration": updated_instance,
            }
        else:
            # No update needed
            result = {
                "changed": False,
                "msg": f"Integration instance {identifier} is already up to date",
                "integration": current_instance,
            }
    else:
        # Create new instance
        if not integration_manager.brand:
            module.fail_json(msg="'brand' is required when creating a new integration instance")
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Integration instance {integration_manager.name} would be created",
                "integration": {
                    "name": integration_manager.name,
                    "brand": integration_manager.brand,
                    "enabled": str(integration_manager.enabled).lower(),
                },
            }
        else:
            created_instance = integration_manager.create_instance()
            result = {
                "changed": True,
                "msg": f"Integration instance {integration_manager.name} created successfully",
                "integration": created_instance,
            }

    return result


def ensure_absent(module, integration_manager):
    """
    Ensure integration instance is absent.

    Args:
        module: AnsibleModule instance
        integration_manager: XSOARIntegrationManager instance

    Returns:
        dict: Result information
    """
    if not integration_manager.name and not integration_manager.instance_id:
        module.fail_json(msg="Either 'name' or 'instance_id' is required when state is absent")

    result = {}

    # Check if instance exists
    if integration_manager.instance_id:
        exists, current_instance = integration_manager.instance_exists(instance_id=integration_manager.instance_id)
        identifier = integration_manager.instance_id
    else:
        exists, current_instance = integration_manager.instance_exists(name=integration_manager.name)
        identifier = integration_manager.name

    if exists:
        if module.check_mode:
            result = {"changed": True, "msg": f"Integration instance {identifier} would be deleted"}
        else:
            integration_manager.delete_instance(current_instance["id"])
            result = {"changed": True, "msg": f"Integration instance {identifier} deleted successfully"}
    else:
        result = {"changed": False, "msg": f"Integration instance {identifier} does not exist"}

    return result


def gather_instances(integration_manager):
    """
    Gather integration instance information.

    Args:
        integration_manager: XSOARIntegrationManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    # Get available integrations if requested
    if integration_manager.get_available:
        available = integration_manager.get_available_integrations()
        result["available_integrations"] = available
        result["msg"] = f"Retrieved {len(available)} available integration types"
        return result

    # Get specific instance by ID or name
    if integration_manager.instance_id:
        instance = integration_manager.get_instance_by_id(integration_manager.instance_id)
        if instance:
            result["integration"] = instance
            result["msg"] = f"Integration instance {integration_manager.instance_id} found"
        else:
            result["msg"] = f"Integration instance {integration_manager.instance_id} not found"
    elif integration_manager.name:
        instance = integration_manager.get_instance_by_name(integration_manager.name)
        if instance:
            result["integration"] = instance
            result["msg"] = f"Integration instance {integration_manager.name} found"
        else:
            result["msg"] = f"Integration instance {integration_manager.name} not found"
    else:
        # Get all instances
        instances = integration_manager.get_all_instances()
        result["integrations"] = instances
        result["msg"] = f"Retrieved {len(instances)} integration instances"

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            brand=dict(type="str", required=False),
            configuration=dict(type="dict", required=False, default={}, no_log=True),
            default_ignore=dict(type="bool", default=False),
            enabled=dict(type="bool", default=True),
            engine=dict(type="str", required=False, default=""),
            engine_group=dict(type="str", required=False, default=""),
            get_available=dict(type="bool", default=False),
            incoming_mapper_id=dict(type="str", required=False, default=""),
            instance_id=dict(type="str", required=False),
            name=dict(type="str", required=False),
            propagation_labels=dict(type="list", elements="str", default=["all"]),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ("state", "present", ["name", "instance_id"], True),
            ("state", "absent", ["name", "instance_id"], True),
        ],
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create integration manager
    try:
        connection = get_connection(module)
        integration_manager = XSOARIntegrationManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if integration_manager.state == "present":
            result = ensure_present(module, integration_manager)
        elif integration_manager.state == "absent":
            result = ensure_absent(module, integration_manager)
        else:  # gathered
            result = gather_instances(integration_manager)
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
