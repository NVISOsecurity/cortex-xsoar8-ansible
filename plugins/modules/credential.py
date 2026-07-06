#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: credential
short_description: Manage XSOAR 8 SaaS credential objects
description:
    - Create, update, delete, and gather information about credential objects in Cortex XSOAR 8 SaaS.
    - Credential objects store authentication information securely for use by integrations.
    - Supports username/password, SSH certificate, and workgroup credential types.
    - Uses the XSOAR 8 SaaS REST API endpoints for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 SaaS instance with appropriate API permissions.
    - Uses the /xsoar/public/v1/settings/credentials and /xsoar/public/v1/settings/credentials/delete endpoints.
    - Credential passwords and certificates are write-only and cannot be retrieved after creation.
    - Only I(username) and I(workgroup) are used for idempotency detection; I(password) and I(certificate)
      changes alone will not report a change.
    - Parameters cannot be set to an empty string; omit optional parameters instead.
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    name:
        description:
            - The name/identifier of the credential object.
            - Must be unique within the XSOAR instance.
            - Required when state is C(present) or C(absent).
        type: str
        required: false
    username:
        description:
            - The username for the credential.
        type: str
        required: false
    password:
        description:
            - The password or secret value for the credential.
            - This value is write-only and cannot be retrieved after creation.
            - Changes to password alone do not trigger idempotency detection.
        type: str
        required: false
        no_log: true
    certificate:
        description:
            - An SSH key or certificate value for the credential.
            - This value is write-only and cannot be retrieved after creation.
            - Changes to certificate alone do not trigger idempotency detection.
        type: str
        required: false
        no_log: true
    workgroup:
        description:
            - The workgroup to associate with the credential.
        type: str
        required: false
    state:
        description:
            - The desired state of the credential object.
            - C(present) - Create or update the credential.
            - C(absent) - Delete the credential.
            - C(gathered) - Retrieve information about existing credentials.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a username/password credential
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "splunk_prod"
    username: "xsoar_service"
    password: "{{ splunk_password }}"
    state: present
  register: splunk_creds

- name: Create a certificate (SSH key) credential
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "ssh_key_creds"
    username: "deploy_user"
    certificate: "{{ lookup('file', '~/.ssh/id_rsa') }}"
    state: present

- name: Create a workgroup credential
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "domain_creds"
    username: "svc_xsoar"
    password: "{{ domain_password }}"
    workgroup: "CORP"
    state: present

- name: Gather all credentials
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_credentials

- name: Get a specific credential by name
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "splunk_prod"
    state: gathered
  register: splunk_credential_info

- name: Update credential username
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "splunk_prod"
    username: "xsoar_service_v2"
    state: present

- name: Delete a credential
  cortex.xsoar8.credential:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "old_credential"
    state: absent
"""

RETURN = """
changed:
    description: Whether the credential object was changed.
    returned: always
    type: bool
    sample: true
credential:
    description: Information about the credential object.
    returned: when state is present, when state is absent and the credential existed, or when state is gathered (single credential)
    type: dict
    contains:
        id:
            description: The unique ID of the credential object
            type: str
            sample: "12345678-1234-1234-1234-123456789abc"
        name:
            description: The name of the credential object
            type: str
            sample: "splunk_prod"
        user:
            description: The username associated with the credential
            type: str
            sample: "xsoar_service"
        workgroup:
            description: The workgroup associated with the credential
            type: str
            sample: "CORP"
        hasPassword:
            description: Whether the credential has a password set
            type: bool
            sample: true
        hasCertificate:
            description: Whether the credential has a certificate set
            type: bool
            sample: false
        version:
            description: The version of the credential object
            type: int
            sample: 1
credentials:
    description: List of credential objects.
    returned: when state is gathered and no name is specified
    type: list
    elements: dict
    sample: [
        {
            "id": "12345678-1234-1234-1234-123456789abc",
            "name": "splunk_prod",
            "user": "xsoar_service"
        }
    ]
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Credential splunk_prod created successfully"
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


class XSOARCredentialManager:
    """
    Manager class for XSOAR credential object operations.
    """

    def __init__(self, connection):
        """
        Initialize the credential manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module
        self.certificate = connection.module.params["certificate"]
        self.name = connection.module.params["name"]
        self.password = connection.module.params["password"]
        self.username = connection.module.params["username"]
        self.workgroup = connection.module.params["workgroup"]
        self.state = connection.module.params["state"]

        for field_name, value in {
            "certificate": self.certificate,
            "name": self.name,
            "password": self.password,
            "username": self.username,
            "workgroup": self.workgroup,
        }.items():
            if value == "":
                self.module.fail_json(msg=f"'{field_name}' cannot be an empty string")

        self.fields_to_compare = [
            ("user", self.username),
            ("workgroup", self.workgroup),
        ]

    def get_all_credentials(self):
        """
        Get all credential objects.

        Returns:
            list: List of credential objects
        """
        try:
            response = self.connection.request("POST", "/settings/credentials")

            # Extract credentials from response
            if isinstance(response, dict):
                return response.get("credentials", [])
            return []
        except Exception as e:
            raise XSOARAPIError(f"Failed to get credentials: {to_text(e)}") from e

    def get_credential_by_name(self, name):
        """
        Get credential object by name.

        Args:
            name (str): Credential name

        Returns:
            dict: Credential object data or None if not found
        """
        credentials = self.get_all_credentials()

        for credential in credentials:
            if credential.get("name") == name:
                return credential
        return None

    def create_credential(self):
        """
        Create a new credential object.

        Returns:
            dict: Created credential information
        """
        # Build the credential data
        credential_data = {
            "name": self.name,
        }

        credential_data.update(
            {
                k: v
                for k, v in {
                    "sshkey": self.certificate,
                    "password": self.password,
                    "user": self.username,
                    "workgroup": self.workgroup,
                }.items()
                if v is not None
            }
        )

        try:
            return self.connection.request("PUT", "/settings/credentials", data=credential_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to create credential: {to_text(e)}") from e

    def update_credential(self, current_credential):
        """
        Update an existing credential object.

        Args:
            current_credential (dict): Current credential object

        Returns:
            dict: Updated credential information
        """
        # XSOAR returns credentials with password/sshkey masked. Send the secret
        # only when the caller actually supplied a new value; otherwise omit it
        # so the API preserves the existing secret instead of clearing it.
        # The hasPassword / hasCertificate flags are taken from the current
        # credential so the server keeps tracking the existing secret state.
        credential_data = {
            "hasPassword": bool(current_credential.get("hasPassword")),
            "hasCertificate": bool(current_credential.get("hasCertificate")),
            "id": current_credential.get("id"),
            "name": self.name if self.name is not None else current_credential.get("name"),
            "user": self.username if self.username is not None else current_credential.get("user"),
            "workgroup": self.workgroup if self.workgroup is not None else current_credential.get("workgroup"),
            "version": -1,
        }

        if self.password is not None:
            credential_data["password"] = self.password
            credential_data["hasPassword"] = True

        if self.certificate is not None:
            credential_data["sshkey"] = self.certificate
            credential_data["hasCertificate"] = True

        try:
            return self.connection.request("PUT", "/settings/credentials", data=credential_data)
        except Exception as e:
            raise XSOARAPIError(f"Failed to update credential: {to_text(e)}") from e

    def delete_credential(self, credential_id):
        """
        Delete a credential object.

        Args:
            credential_id (str): Credential ID to delete

        Returns:
            bool: True if successful
        """
        try:
            self.connection.request("POST", "/settings/credentials/delete", {"id": credential_id})
            return True
        except Exception as e:
            raise XSOARAPIError(f"Failed to delete credential: {to_text(e)}") from e


def ensure_present(module, credential_manager):
    """
    Ensure credential object is present.
    Args:
        module: AnsibleModule instance
        credential_manager: XSOARCredentialManager instance

    Returns:
        dict: Result information
    """
    result = {}

    # Check if credential exists
    if current_credential := credential_manager.get_credential_by_name(credential_manager.name):
        if module.check_mode:
            # Only report what would happen, do not update
            if instance_needs_update(current_credential, credential_manager.fields_to_compare):
                result = {
                    "changed": True,
                    "msg": f"Credential {credential_manager.name} would be updated",
                    "credential": current_credential,
                }
            else:
                result = {
                    "changed": False,
                    "msg": f"Credential {credential_manager.name} is already up to date (check mode)",
                    "credential": current_credential,
                }
        elif instance_needs_update(current_credential, credential_manager.fields_to_compare):
            updated_credential = credential_manager.update_credential(current_credential=current_credential)
            result = {
                "changed": True,
                "msg": f"Credential {credential_manager.name} updated successfully",
                "credential": updated_credential,
            }
        else:
            # No update needed
            result = {
                "changed": False,
                "msg": f"Credential {credential_manager.name} is already up to date",
                "credential": current_credential,
            }
    else:
        # Create new credential
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Credential {credential_manager.name} would be created",
                "credential": {
                    "certificate": credential_manager.certificate,
                    "name": credential_manager.name,
                    "password": credential_manager.password,
                    "user": credential_manager.username,
                    "workgroup": credential_manager.workgroup,
                },
            }
        else:
            created_credential = credential_manager.create_credential()
            changed = True
            result = {
                "changed": changed,
                "msg": f"Credential {credential_manager.name} created successfully",
                "credential": created_credential,
            }

    return result


def ensure_absent(module, credential_manager):
    """
    Ensure credential object is absent.

    Args:
        module: AnsibleModule instance
        credential_manager: XSOARCredentialManager instance

    Returns:
        dict: Result information
    """
    result = {}

    # Check if credential exists
    if current_credential := credential_manager.get_credential_by_name(credential_manager.name):
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Credential {credential_manager.name} would be deleted",
                "credential": current_credential,
            }
        else:
            credential_manager.delete_credential(current_credential["id"])
            result = {
                "changed": True,
                "msg": f'Credential {credential_manager.name} with ID {current_credential["id"]} deleted successfully',
                "credential": current_credential,
            }
    else:
        result = {
            "changed": False,
            "msg": f"Credential {credential_manager.name} does not exist",
        }

    return result


def gather_credentials(credential_manager):
    """
    Gather credential object information.

    Args:
        credential_manager: XSOARCredentialManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    # Get specific credential name
    if credential_manager.name:
        if credential := credential_manager.get_credential_by_name(credential_manager.name):
            result["credential"] = credential
            result["msg"] = f"Credential {credential_manager.name} found"
        else:
            result["msg"] = f"Credential {credential_manager.name} not found"
    else:
        # Get all credentials
        credentials = credential_manager.get_all_credentials()
        result["credentials"] = credentials
        result["msg"] = f"Retrieved {len(credentials)} credentials"

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            certificate=dict(type="str", required=False, no_log=True),
            name=dict(type="str", required=False),
            password=dict(type="str", required=False, no_log=True),
            username=dict(type="str", required=False),
            workgroup=dict(type="str", required=False),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[("state", "present", ["name"]), ("state", "absent", ["name"])],
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    # Get connection and create credential manager
    try:
        connection = get_connection(module)
        credential_manager = XSOARCredentialManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    # Execute based on state
    try:
        if credential_manager.state == "present":
            result = ensure_present(module, credential_manager)
        elif credential_manager.state == "absent":
            result = ensure_absent(module, credential_manager)
        else:  # gathered
            result = gather_credentials(credential_manager)
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
