#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: multi_tenant
short_description: Manage XSOAR 8 SaaS multi-tenant child tenants
description:
    - Create, delete, and gather information about child tenants in a Cortex XSOAR 8 SaaS multi-tenant deployment.
    - Uses the XSOAR MSSP public API C(/public_api/v1/mssp/) endpoints.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 SaaS multi-tenant (MSSP) instance with appropriate API permissions.
    - For C(state=absent), you may supply any one of C(cortex_id), C(tenant_name), or C(tenant_id). If only one
      identifier is provided the module will attempt to resolve the remaining ones via an API lookup so that the
      delete payload is complete. If the tenant cannot be found during that lookup, the module returns
      C(changed=False) rather than failing.
    - For C(state=absent), you may alternatively supply all three identifiers directly and skip the API lookup.
    - C(state=present) does not perform an update; if a tenant with the given C(tenant_name) already exists the
      module returns C(changed=False).
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    cortex_id:
        description:
            - The Cortex platform ID of the tenant.
            - Used as an identifier for C(state=absent) and C(state=gathered).
        type: str
        required: false
    tenant_id:
        description:
            - The internal XSOAR tenant ID.
            - Used as an identifier for C(state=absent) and C(state=gathered).
        type: str
        required: false
    tenant_name:
        description:
            - The display name of the tenant.
            - Required for C(state=present).
            - Used as an identifier for C(state=absent) and C(state=gathered).
        type: str
        required: false
    tenant_subdomain:
        description:
            - The subdomain to assign to the new tenant.
            - Required for C(state=present).
        type: str
        required: false
    initial_user:
        description:
            - The email address of the initial administrator user for the new tenant.
            - Required for C(state=present).
        type: str
        required: false
    data_retention:
        description:
            - Data retention period in days for the new tenant.
            - Must be a positive integer.
            - Required for C(state=present).
        type: int
        required: false
    state:
        description:
            - The desired state for the tenant.
            - C(present) - Create the tenant if it does not already exist.
            - C(absent) - Delete the tenant if it exists. Requires at least one of C(cortex_id),
              C(tenant_name), or C(tenant_id).
            - C(gathered) - Retrieve tenant information. Optionally filter by C(cortex_id),
              C(tenant_name), or C(tenant_id). If no identifier is provided, all tenants are returned.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a new child tenant
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    tenant_name: "acme-corp"
    tenant_subdomain: "acme"
    initial_user: "admin@acme.com"
    data_retention: 365
    state: present
  register: tenant_result

- name: Gather all tenants
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_tenants

- name: Gather a specific tenant by name
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    tenant_name: "acme-corp"
    state: gathered
  register: tenant_info

- name: Gather a specific tenant by Cortex ID
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    cortex_id: "cortex-abc123"
    state: gathered
  register: tenant_by_cortex_id

- name: Delete a tenant by name (module resolves remaining identifiers via API lookup)
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    tenant_name: "acme-corp"
    state: absent

- name: Delete a tenant by providing all three identifiers (skips API lookup)
  cortex.xsoar8.multi_tenant:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    cortex_id: "cortex-abc123"
    tenant_id: "tenant-abc123"
    tenant_name: "acme-corp"
    state: absent
"""

RETURN = """
changed:
    description: Whether a change was made to the tenant.
    returned: always
    type: bool
    sample: true
msg:
    description: A message describing the outcome.
    returned: always
    type: str
    sample: "Tenant created successfully."
tenant:
    description: Information about the tenant that was created, found, or deleted.
    returned: when state is C(present) or C(absent)
    type: dict
    contains:
        cortex_id:
            description: The Cortex platform ID of the tenant.
            type: str
            sample: "cortex-abc123"
        tenant_id:
            description: The internal XSOAR tenant ID.
            type: str
            sample: "tenant-abc123"
        tenant_name:
            description: Display name of the tenant.
            type: str
            sample: "acme-corp"
        tenant_subdomain:
            description: Subdomain assigned to the tenant.
            type: str
            sample: "acme"
        data_retention:
            description: Data retention period in days.
            type: int
            sample: 365
        initial_user:
            description: Email address of the initial administrator.
            type: str
            sample: "admin@acme.com"
        status:
            description: Current status of the tenant.
            type: str
            sample: "active"
deleted:
    description: Raw API response from the delete operation.
    returned: when state is C(absent) and the tenant was deleted
    type: raw
    sample: true
tenant:
    description: Tenant information matching the supplied identifier filter.
    returned: when state is C(gathered) and a filter identifier was provided
    type: dict
    sample:
        cortex_id: "cortex-abc123"
        tenant_id: "tenant-abc123"
        tenant_name: "acme-corp"
        tenant_subdomain: "acme"
        data_retention: 365
        status: "active"
tenants:
    description: List of all tenants. Returned when C(state=gathered) and no identifier filter is provided.
    returned: when state is C(gathered) and no filter is provided
    type: list
    elements: dict
    sample:
        - cortex_id: "cortex-abc123"
          tenant_id: "tenant-abc123"
          tenant_name: "acme-corp"
          tenant_subdomain: "acme"
          data_retention: 365
          status: "active"
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


class XSOARTenantManager:
    """
    Manager class for XSOAR Tenant operations.
    """

    def __init__(self, connection):
        """
        Initialize the Tenant manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module

        self.cortex_id = connection.module.params["cortex_id"]
        self.data_retention = connection.module.params["data_retention"]
        self.initial_user = connection.module.params["initial_user"]
        self.tenant_id = connection.module.params["tenant_id"]
        self.tenant_name = connection.module.params["tenant_name"]
        self.tenant_subdomain = connection.module.params["tenant_subdomain"]
        self.state = connection.module.params["state"]

        self.validate_request_data()

    def validate_request_data(self):
        """Validate request_data shape and prepare reusable request payload."""
        if self.state == "present":
            validated = self._validate_present_fields()
        elif self.state == "absent":
            validated = self._validate_absent_fields()
        else:  # gathered
            validated = self._validate_gathered_fields()
        self.prepared_request_data = {"request_data": validated}

    def _validate_present_fields(self):
        """Validate fields required for state=present."""
        normalized_data = {}

        for field in ["tenant_name", "tenant_subdomain", "initial_user"]:
            if (value := getattr(self, field)) is not None:
                if not value.strip():
                    self.module.fail_json(msg=f"Invalid {field}. Expected non-empty string.")
                normalized_data[field] = value

        if self.data_retention is not None:
            if self.data_retention <= 0:
                self.module.fail_json(msg="Invalid data_retention. Expected positive integer.")
            normalized_data["data_retention"] = self.data_retention

        required_fields = ["tenant_name", "tenant_subdomain", "initial_user", "data_retention"]
        if still_missing := [f for f in required_fields if f not in normalized_data]:
            self.module.fail_json(
                msg=(f"state=present is missing required fields after validation: " f"{', '.join(still_missing)}.")
            )

        return normalized_data

    def _validate_absent_fields(self):
        """Validate fields required for state=absent."""
        identifier_fields = ["cortex_id", "tenant_name", "tenant_id"]
        if not [f for f in identifier_fields if getattr(self, f)]:
            self.module.fail_json(msg=("state=absent requires at least one of: " f"{', '.join(identifier_fields)}."))

        # All identifier fields share identical validation logic — handle in one loop.
        normalized_data = {}
        for field in identifier_fields:
            if (value := getattr(self, field)) is not None:
                if not value.strip():
                    self.module.fail_json(msg=f"Invalid {field}. Expected non-empty string.")
                normalized_data[field] = value

        # If fewer than all identifiers were supplied, resolve the missing ones via the
        # dedicated lookup helpers. Priority: cortex_id > tenant_name > tenant_id.
        if missing_identifiers := [f for f in identifier_fields if f not in normalized_data]:
            if "cortex_id" in normalized_data:
                tenant = self.get_tenant_by_cortex_id(normalized_data["cortex_id"])
            elif "tenant_name" in normalized_data:
                tenant = self.get_tenant_by_name(normalized_data["tenant_name"])
            else:
                tenant = self.get_tenant_by_tenant_id(normalized_data["tenant_id"])

            if not tenant:
                # Tenant not found — return partial data and let ensure_absent
                # handle the "not found" case with changed=False instead of failing.
                return normalized_data

            for field in missing_identifiers:
                if value := tenant.get(field):
                    normalized_data[field] = str(value)

        if still_missing := [f for f in identifier_fields if f not in normalized_data]:
            self.module.fail_json(
                msg=(
                    f"Could not resolve all required identifiers for deletion. "
                    f"Missing after lookup: {', '.join(still_missing)}. "
                    f"Resolved so far: {normalized_data}."
                )
            )

        return normalized_data

    def _validate_gathered_fields(self):
        """Validate format of any provided identifier fields for state=gathered."""
        normalized_data = {}
        for field in ["cortex_id", "tenant_name", "tenant_id"]:
            if (value := getattr(self, field)) is not None:
                if not value.strip():
                    self.module.fail_json(msg=f"Invalid {field}. Expected non-empty string.")
                normalized_data[field] = value
        return normalized_data

    def get_tenants(self, data=None):
        """
        Retrieves Tenants.

        Args:
            data (dict, optional): Full request payload. Defaults to
                {"request_data": {}} which fetches all tenants.

        Returns:
            list[dict]: Tenant response from the API.
        """
        data = data if data is not None else {"request_data": {}}

        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/mssp/get_tenants",
                data=data,
            )
            if isinstance(response, dict):
                return response.get("reply")
            return response
        except Exception as e:
            raise XSOARAPIError(f"Failed to retrieve tenants: {to_text(e)}") from e

    def get_tenant_by_cortex_id(self, cortex_id):
        """
        Retrieve a Tenant by Cortex ID.

        Args:
            cortex_id (str): The Cortex ID of the Tenant to retrieve.

        Returns:
            dict: Tenant information if found, else None
        """
        if tenants := self.get_tenants():
            for tenant in tenants:
                if tenant.get("cortex_id") == cortex_id:
                    return tenant
        return None

    def get_tenant_by_tenant_id(self, tenant_id):
        """
        Retrieve a Tenant by ID.

        Args:
            tenant_id (str): The ID of the Tenant to retrieve.

        Returns:
            dict: Tenant information if found, else None
        """
        if tenants := self.get_tenants():
            for tenant in tenants:
                if tenant.get("tenant_id") == tenant_id:
                    return tenant
        return None

    def get_tenant_by_name(self, tenant_name):
        """
        Retrieve a Tenant by name.

        Args:
            tenant_name (str): The name of the Tenant to retrieve.

        Returns:
            dict: Tenant information if found, else None
        """
        if tenants := self.get_tenants():
            for tenant in tenants:
                if tenant.get("tenant_name") == tenant_name:
                    return tenant
        return None

    def create_tenant(self):
        """
        Create a new Tenant.

        Returns:
            dict: Created Tenant information
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/mssp/create_child",
                data=self.prepared_request_data,
            )
            if isinstance(response, dict):
                return response.get("reply")
            return response
        except Exception as e:
            raise XSOARAPIError(f"Failed to create Tenant: {to_text(e)}") from e

    def delete_tenant(self):
        """
        Delete an existing Tenant.

        Returns:
            bool: Whether the deletion was successful
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/mssp/delete_child",
                data=self.prepared_request_data,
            )
            if isinstance(response, dict):
                return response.get("reply")
            return response
        except Exception as e:
            raise XSOARAPIError(f"Failed to delete Tenant: {to_text(e)}") from e


def ensure_present(module, tenant_manager):
    """
    Ensure Tenant is present.

    Args:
        module: AnsibleModule instance
        tenant_manager: XSOARTenantManager instance

    Returns:
        dict: Result information
    """
    result = {}

    if tenant_exists := tenant_manager.get_tenant_by_name(tenant_manager.tenant_name):
        result = {
            "changed": False,
            "tenant": tenant_exists,
            "msg": "Tenant already exists with the provided name.",
        }
    else:
        if module.check_mode:
            result = {
                "changed": True,
                "tenant": tenant_manager.prepared_request_data["request_data"],
                "msg": "Tenant would be created with the provided information.",
            }
        else:
            created_tenant = tenant_manager.create_tenant()
            result = {"changed": True, "tenant": created_tenant, "msg": "Tenant created successfully."}

    return result


def ensure_absent(module, tenant_manager):
    """
    Ensure Tenant is absent.

    Args:
        module: AnsibleModule instance
        tenant_manager: XSOARTenantManager instance

    Returns:
        dict: Result information
    """
    resolved = tenant_manager.prepared_request_data["request_data"]

    # Check existence using the highest-priority resolved identifier.
    # Priority mirrors _validate_absent_fields: cortex_id > tenant_name > tenant_id.
    if "cortex_id" in resolved:
        existing_tenant = tenant_manager.get_tenant_by_cortex_id(resolved["cortex_id"])
    elif "tenant_name" in resolved:
        existing_tenant = tenant_manager.get_tenant_by_name(resolved["tenant_name"])
    else:
        existing_tenant = tenant_manager.get_tenant_by_tenant_id(resolved["tenant_id"])

    if not existing_tenant:
        return {
            "changed": False,
            "msg": f"Tenant matching {resolved} does not exist.",
        }

    if module.check_mode:
        return {
            "changed": True,
            "tenant": existing_tenant,
            "msg": "Tenant would be deleted.",
        }

    deleted = tenant_manager.delete_tenant()
    return {
        "changed": True,
        "deleted": deleted,
        "tenant": existing_tenant,
        "msg": "Tenant deleted successfully.",
    }


def gather_tenants(tenant_manager):
    """
    Gather Tenant information.

    Args:
        tenant_manager: XSOARTenantManager instance

    Returns:
        dict: Result information
    """
    if not (filter_data := tenant_manager.prepared_request_data["request_data"]):
        result = {
            "changed": False,
            "tenants": tenant_manager.get_tenants(),
            "msg": "No filter provided, returning all tenants.",
        }
        return result

    # Try each provided identifier in priority order; return on first match.
    lookups = [
        ("cortex_id", tenant_manager.get_tenant_by_cortex_id),
        ("tenant_name", tenant_manager.get_tenant_by_name),
        ("tenant_id", tenant_manager.get_tenant_by_tenant_id),
    ]
    for field, lookup_fn in lookups:
        if value := filter_data.get(field):
            if tenant := lookup_fn(value):
                result = {"changed": False, "tenant": tenant, "msg": f"Retrieved tenant by {field} filter."}
                return result

    result = {
        "changed": False,
        "tenant": None,
        "msg": f"No tenant found matching the provided identifier(s): {filter_data}.",
    }
    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            cortex_id=dict(type="str"),
            data_retention=dict(type="int"),
            initial_user=dict(type="str"),
            tenant_id=dict(type="str"),
            tenant_name=dict(type="str"),
            tenant_subdomain=dict(type="str"),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ("state", "present", ["tenant_name", "tenant_subdomain", "initial_user", "data_retention"]),
        ],
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create tenant manager
    try:
        connection = get_connection(module)
        tenant_manager = XSOARTenantManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if tenant_manager.state == "present":
            result = ensure_present(module, tenant_manager)
        elif tenant_manager.state == "absent":
            result = ensure_absent(module, tenant_manager)
        else:  # gathered
            result = gather_tenants(tenant_manager)
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
