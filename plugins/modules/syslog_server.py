#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


# TODO: Update when requested features are implemented in the API.

DOCUMENTATION = """
---
module: syslog_server
short_description: Manage XSOAR 8 SaaS syslog server integrations
description:
    - Create, update, delete, and gather information about syslog server integrations in Cortex XSOAR 8 SaaS.
    - Syslog servers receive log data forwarded from XSOAR over TCP, UDP, or TLS.
    - Supports filtering by address, id, name, or status when deleting or gathering servers.
    - Uses the XSOAR 8 SaaS public API C(/public_api/v1/integrations/syslog/) endpoints.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 SaaS instance with appropriate API permissions.
    - C(request_data) is always required and must be non-empty.
    - For C(state=present), C(request_data) must contain the direct fields C(name), C(address), C(port),
      C(protocol), and C(facility). Filters are not supported.
    - For C(state=absent) and C(state=gathered), C(request_data) must contain C(filters). Direct fields
      are not supported. The API requires at least one filter object.
        - The API rejects private (RFC 1918) IP addresses for the C(address) field.
        - C(security_info) is only processed when C(protocol=TLS).
        - For C(protocol=TLS), C(request_data.security_info.ignore_cert_errors) is required.
        - C(certificate_name) and C(certificate_content) are optional for C(protocol=TLS).
        - C(ignore_cert_errors=true) disables certificate validation and is not recommended for production.
        - C(certificate_content) may be sent during create/update to upload certificate material; it is
            treated as sensitive input and excluded from idempotency comparisons.
    - XSOAR allows two syslog servers to share the same name when one was created via the UI and the
      other via the API (they receive different IDs). A name-based C(state=absent) will therefore
      delete ALL servers matching that name.
    - The C(status) filter field accepts the values C(ACTIVE) or C(ERROR) (uppercase).
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    request_data:
        description:
            - Data payload describing the syslog server to manage or filter.
            - For C(state=present), supply direct fields C(name), C(address), C(port), C(protocol), C(facility), and optionally C(syslog_id) or C(security_info).
            - For C(state=absent) and C(state=gathered), supply a C(filters) list.
        type: dict
        required: true
        suboptions:
            name:
                description: Name of the syslog server integration.
                type: str
                required: false
            address:
                description:
                    - IP address or hostname of the syslog destination.
                    - Must be a publicly routable IP address; private RFC 1918 addresses are rejected by the API.
                type: str
                required: false
            port:
                description: Destination port as a numeric string or integer (e.g. "514" or 514).
                type: raw
                required: false
            protocol:
                description: Transport protocol for syslog traffic.
                type: str
                choices: ['TCP', 'UDP', 'TLS']
                required: false
            facility:
                description: Syslog facility code to use when forwarding messages.
                type: str
                choices:
                    - FAC_KERNEL
                    - FAC_USER
                    - FAC_MAIL
                    - FAC_SYSTEM
                    - FAC_SECURITY
                    - FAC_SYSLOG
                    - FAC_PRINTER
                    - FAC_NETWORK
                    - FAC_UUCP
                    - FAC_CLOCK
                    - FAC_AUTH
                    - FAC_FTP
                    - FAC_NTP
                    - FAC_LOG_AUDIT
                    - FAC_LOG_ALERT
                    - FAC_CLOCK2
                    - FAC_LOCAL0
                    - FAC_LOCAL1
                    - FAC_LOCAL2
                    - FAC_LOCAL3
                    - FAC_LOCAL4
                    - FAC_LOCAL5
                    - FAC_LOCAL6
                    - FAC_LOCAL7
                required: false
            syslog_id:
                description:
                    - The unique ID of the syslog server integration.
                    - Optional for C(state=present); if omitted the server is looked up by name.
                type: str
                required: false
            security_info:
                description:
                    - TLS security configuration. Only used when C(protocol=TLS).
                                        - Required when C(protocol=TLS), and must include C(ignore_cert_errors).
                                        - C(certificate_name) and C(certificate_content) are optional.
                type: dict
                required: false
                suboptions:
                    certificate_name:
                        description:
                            - Name of the TLS certificate stored in XSOAR.
                            - Recommended when C(protocol=TLS) so XSOAR can validate the receiver certificate.
                        type: str
                        required: false
                    ignore_cert_errors:
                        description:
                            - Whether to ignore TLS certificate validation errors.
                            - Required when C(protocol=TLS).
                            - Set to C(true) only when certificate validation bypass is explicitly desired.
                        type: bool
                        required: false
                    certificate_content:
                        description:
                            - Raw PEM certificate content.
                            - Only relevant for C(protocol=TLS).
                            - Used only during create/update; excluded from idempotency comparisons.
                        type: str
                        required: false
            filters:
                description:
                    - List of filter objects used for C(state=absent) and C(state=gathered).
                    - Each filter must specify C(field), C(operator), and C(value).
                    - At least one filter is required (the API rejects empty filter lists).
                type: list
                elements: dict
                required: false
                suboptions:
                    field:
                        description: Field to filter on.
                        type: str
                        choices: ['address', 'id', 'name', 'status']
                        required: true
                    operator:
                        description: Filter operator.
                        type: str
                        choices: ['eq']
                        required: true
                    value:
                        description:
                            - Value to match against.
                            - When C(field=status) the accepted values are C(ACTIVE) or C(ERROR) (uppercase).
                        type: raw
                        required: true
    state:
        description:
            - The desired state of the syslog server integration.
            - C(present) - Create or update the syslog server.
            - C(absent) - Delete syslog servers matching the supplied filters.
            - C(gathered) - Retrieve syslog servers matching the supplied filters.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a UDP syslog server
  cortex.xsoar8.syslog_server:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      name: "prod_syslog"
      address: "203.0.113.10"
      port: "514"
      protocol: "UDP"
      facility: "FAC_LOCAL0"
    state: present
  register: syslog_result

- name: Create a TLS syslog server with certificate
  cortex.xsoar8.syslog_server:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      name: "secure_syslog"
      address: "203.0.113.20"
      port: "6514"
      protocol: "TLS"
      facility: "FAC_LOCAL1"
      security_info:
        certificate_name: "syslog-tls-cert"
        ignore_cert_errors: false
    state: present

- name: Gather syslog servers by name
  cortex.xsoar8.syslog_server:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: name
          operator: eq
          value: "prod_syslog"
    state: gathered
  register: syslog_info

- name: Gather syslog servers by status (ACTIVE or ERROR)
  cortex.xsoar8.syslog_server:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: status
          operator: eq
          value: "ERROR"
    state: gathered
  register: failing_syslogs

- name: Delete a syslog server by name
  cortex.xsoar8.syslog_server:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    request_data:
      filters:
        - field: name
          operator: eq
          value: "prod_syslog"
    state: absent
"""

RETURN = """
changed:
    description: Whether the syslog server integration was changed.
    returned: always
    type: bool
    sample: true
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Syslog server prod_syslog created"
syslog_server:
    description: Information about the syslog server integration.
    returned: when state is C(present)
    type: dict
    contains:
        syslog_id:
            description: The unique ID of the syslog server integration.
            type: str
            sample: "abc123-def4-5678-ghij-klmnopqrstuv"
        name:
            description: Name of the syslog server integration.
            type: str
            sample: "prod_syslog"
        address:
            description: IP address or hostname of the syslog destination.
            type: str
            sample: "203.0.113.10"
        port:
            description: Destination port as a string.
            type: str
            sample: "514"
        protocol:
            description: Transport protocol.
            type: str
            sample: "UDP"
        facility:
            description: Syslog facility code.
            type: str
            sample: "FAC_LOCAL0"
        status:
            description: Current connection status reported by XSOAR. One of C(ACTIVE) or C(ERROR).
            type: str
            sample: "ACTIVE"
        server_error:
            description: Error message if the server is in an error state, otherwise null.
            type: str
            sample: null
        security_info:
            description: TLS security configuration. Present only when the server uses TLS.
            type: dict
            contains:
                certificate_name:
                    description: Name of the TLS certificate.
                    type: str
                    sample: "syslog-tls-cert"
                ignore_cert_errors:
                    description: Whether TLS certificate validation errors are ignored.
                    type: bool
                    sample: false
syslog_servers:
    description: List of syslog server integrations matching the supplied filters.
    returned: when state is C(gathered)
    type: list
    elements: dict
    sample:
        - syslog_id: "abc123-def4-5678-ghij-klmnopqrstuv"
          name: "prod_syslog"
          address: "203.0.113.10"
          port: "514"
          protocol: "UDP"
          facility: "FAC_LOCAL0"
          status: "ACTIVE"
          server_error: null
"""

import copy
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


class XSOARSyslogServerManager:
    """
    Manager class for XSOAR Syslog Server operations.
    """

    DIRECT_FIELDS = ["address", "facility", "name", "port", "protocol", "security_info", "syslog_id"]
    FILTER_FIELDS = ["address", "id", "name", "status"]
    ALLOWED_OPERATORS = ["eq"]
    PROTOCOLS = ["TCP", "UDP", "TLS"]
    FACILITIES = [
        "FAC_KERNEL",
        "FAC_USER",
        "FAC_MAIL",
        "FAC_SYSTEM",
        "FAC_SECURITY",
        "FAC_SYSLOG",
        "FAC_PRINTER",
        "FAC_NETWORK",
        "FAC_UUCP",
        "FAC_CLOCK",
        "FAC_AUTH",
        "FAC_FTP",
        "FAC_NTP",
        "FAC_LOG_AUDIT",
        "FAC_LOG_ALERT",
        "FAC_CLOCK2",
        "FAC_LOCAL0",
        "FAC_LOCAL1",
        "FAC_LOCAL2",
        "FAC_LOCAL3",
        "FAC_LOCAL4",
        "FAC_LOCAL5",
        "FAC_LOCAL6",
        "FAC_LOCAL7",
    ]

    def __init__(self, connection):
        self.connection = connection
        self.module = connection.module
        self.request_data = connection.module.params["request_data"] or {}
        self.state = connection.module.params["state"]
        if self.request_data:
            self.validate_request_data()

    @staticmethod
    def normalize_server(server):
        """Normalize API response fields into module-facing shape."""
        if not server:
            return {}

        normalized_server = {
            "syslog_id": server.get("SYSLOG_INTEGRATION_ID"),
            "name": server.get("SYSLOG_INTEGRATION_NAME"),
            "address": server.get("SYSLOG_INTEGRATION_ADDRESS"),
            "port": str(server.get("SYSLOG_INTEGRATION_PORT")),
            "protocol": server.get("SYSLOG_INTEGRATION_PROTOCOL"),
            "facility": server.get("FACILITY"),
            "status": server.get("SYSLOG_INTEGRATION_STATUS"),
            "server_error": server.get("SYSLOG_INTEGRATION_ERROR"),
        }

        security_info = {}
        if (certificate_name := server.get("SYSLOG_INTEGRATION_CERTIFICATE_NAME")) not in (None, {}, ""):
            security_info["certificate_name"] = certificate_name
        if (ignore_cert_errors := server.get("SYSLOG_INTEGRATION_IGNORE_CERTIFICATE_ERROR")) not in (None, {}, ""):
            security_info["ignore_cert_errors"] = ignore_cert_errors
        if security_info:
            normalized_server["security_info"] = security_info

        return normalized_server

    def _redacted_payload(self, payload):
        """Return a deep copy of payload with security_info.certificate_content redacted."""
        try:
            redacted = copy.deepcopy(payload)
        except Exception:
            return payload
        request_data = redacted.get("request_data") if isinstance(redacted, dict) else None
        if isinstance(request_data, dict):
            security_info = request_data.get("security_info")
            if isinstance(security_info, dict) and security_info.get("certificate_content") is not None:
                security_info["certificate_content"] = "***REDACTED***"
        return redacted

    def get_fields_to_compare(self):
        """Build normalized comparison fields for idempotency checks."""
        desired_data = self.prepared_request_data["request_data"]
        fields_to_compare = [
            ("name", desired_data.get("name")),
            ("address", desired_data.get("address")),
            ("port", desired_data.get("port")),
            ("protocol", desired_data.get("protocol")),
            ("facility", desired_data.get("facility")),
        ]

        if desired_data.get("protocol") == "TLS":
            security_info = dict(desired_data.get("security_info", {}))
            security_info.pop("certificate_content", None)
            fields_to_compare.append(("security_info", security_info))

        return fields_to_compare

    def validate_request_data(self):
        """Validate request_data shape and prepare reusable request payload."""
        has_filters = self.request_data.get("filters") is not None
        has_direct_fields = any(self.request_data.get(key) is not None for key in self.DIRECT_FIELDS)

        if has_filters and has_direct_fields:
            self.module.fail_json(
                msg=(
                    "request_data must contain either 'filters' or direct keys "
                    "(address, facility, name, port, protocol, security_info, syslog_id), not both"
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

            if field not in self.FILTER_FIELDS:
                self.module.fail_json(
                    msg=f"Invalid filters[{index}].field '{field}'. Supported values: {', '.join(self.FILTER_FIELDS)}.",
                )
            if operator not in self.ALLOWED_OPERATORS:
                self.module.fail_json(
                    msg=(
                        f"Invalid filters[{index}].operator '{operator}'. "
                        f"Supported values: {', '.join(self.ALLOWED_OPERATORS)}.",
                    )
                )
            if value is None:
                self.module.fail_json(msg=f"Invalid filters[{index}].value. A value is required.")

            # The XSOAR API only accepts ACTIVE/ERROR for the status field;
            # reject other values here so the caller gets a clear error.
            if field == "status" and value not in {"ACTIVE", "ERROR"}:
                self.module.fail_json(
                    msg=(
                        f"Invalid filters[{index}].value '{value}' for field 'status'. "
                        "Supported values: ACTIVE, ERROR."
                    )
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

        allowed_keys = set(self.DIRECT_FIELDS)
        unknown_keys = [
            key for key in self.request_data if key not in allowed_keys and self.request_data.get(key) is not None
        ]
        if unknown_keys:
            self.module.fail_json(msg=f"Unsupported request_data field(s): {', '.join(sorted(unknown_keys))}.")

        required_fields = ["name", "port", "protocol", "address", "facility"]
        missing_fields = [field for field in required_fields if self.request_data.get(field) is None]
        if missing_fields:
            self.module.fail_json(
                msg=(
                    "state=present requires request_data fields: "
                    f"{', '.join(required_fields)}. Missing: {', '.join(missing_fields)}."
                )
            )

        if (address := self.request_data.get("address")) is not None:
            if not isinstance(address, str) or not address.strip():
                self.module.fail_json(msg="Invalid request_data.address. Expected non-empty string.")
            normalized_data["address"] = address

        if (facility := self.request_data.get("facility")) is not None:
            if not isinstance(facility, str):
                self.module.fail_json(msg="Invalid request_data.facility. Expected string.")
            if facility not in self.FACILITIES:
                self.module.fail_json(
                    msg=f"Invalid request_data.facility. Supported values: {', '.join(self.FACILITIES)}.",
                )
            normalized_data["facility"] = facility

        if (name := self.request_data.get("name")) is not None:
            if not isinstance(name, str) or not name.strip():
                self.module.fail_json(msg="Invalid request_data.name. Expected non-empty string.")
            normalized_data["name"] = name

        if (port := self.request_data.get("port")) is not None:
            if isinstance(port, bool):
                self.module.fail_json(msg="Invalid request_data.port. Expected numeric string or integer.")
            if isinstance(port, int):
                port_value = port
            elif isinstance(port, str) and port.isdigit():
                port_value = int(port)
            else:
                self.module.fail_json(msg="Invalid request_data.port. Expected numeric string or integer.")
            if not 1 <= port_value <= 65535:
                self.module.fail_json(msg="Invalid request_data.port. Expected value in range 1-65535.")
            normalized_data["port"] = str(port_value)

        if (protocol := self.request_data.get("protocol")) is not None:
            if not isinstance(protocol, str):
                self.module.fail_json(msg="Invalid request_data.protocol. Expected string.")
            if protocol not in self.PROTOCOLS:
                self.module.fail_json(
                    msg=f"Invalid request_data.protocol. Supported values: {', '.join(self.PROTOCOLS)}.",
                )
            normalized_data["protocol"] = protocol

        if (syslog_id := self.request_data.get("syslog_id")) is not None:
            if not isinstance(syslog_id, str):
                self.module.fail_json(msg="Invalid request_data.syslog_id. Expected string.")
            normalized_data["syslog_id"] = syslog_id

        if protocol == "TLS":
            if (security_info := self.request_data.get("security_info")) is None:
                self.module.fail_json(
                    msg=(
                        "state=present with request_data.protocol=TLS requires request_data.security_info "
                        "including request_data.security_info.ignore_cert_errors."
                    )
                )

            if not isinstance(security_info, dict):
                self.module.fail_json(msg="Invalid request_data.security_info. Expected dictionary.")

            allowed_security_keys = {"certificate_name", "ignore_cert_errors", "certificate_content"}
            unknown_security_keys = [
                key for key in security_info if key not in allowed_security_keys and security_info.get(key) is not None
            ]
            if unknown_security_keys:
                self.module.fail_json(
                    msg=(
                        "Unsupported request_data.security_info field(s): "
                        f"{', '.join(sorted(unknown_security_keys))}."
                    ),
                )

            if (ignore_cert_errors := security_info.get("ignore_cert_errors")) is None:
                self.module.fail_json(
                    msg=("request_data.security_info.ignore_cert_errors is required when " "request_data.protocol=TLS.")
                )

            normalized_security_info = {}

            if (certificate_name := security_info.get("certificate_name")) is not None:
                if not isinstance(certificate_name, str):
                    self.module.fail_json(msg="Invalid request_data.security_info.certificate_name. Expected string.")
                normalized_security_info["certificate_name"] = certificate_name

            if not isinstance(ignore_cert_errors, bool):
                self.module.fail_json(msg="Invalid request_data.security_info.ignore_cert_errors. Expected boolean.")
            normalized_security_info["ignore_cert_errors"] = ignore_cert_errors

            if (certificate_content := security_info.get("certificate_content")) is not None:
                if not isinstance(certificate_content, str):
                    self.module.fail_json(
                        msg="Invalid request_data.security_info.certificate_content. Expected string."
                    )
                normalized_security_info["certificate_content"] = certificate_content

            normalized_data["security_info"] = normalized_security_info

        if not normalized_data:
            self.module.fail_json(
                msg=(
                    "request_data must include either 'filters' or at least one direct key "
                    "(syslog_id, name, address, port, protocol, facility, security_info)."
                )
            )

        return normalized_data

    def get_syslog_servers(self, data=None):
        """
        Get syslog server objects.

        Returns:
            list: List of syslog server objects
        """
        # TODO: Add support for fetching all servers without filters (currently requires at least one filter).
        data = data if data is not None else self.prepared_request_data
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/integrations/syslog/get",
                data=data,
            )
            if isinstance(response, dict):
                return response.get("objects", [])
            return []
        except XSOARAPIError as e:
            self.module.fail_json(
                msg=(
                    f"Failed to retrieve syslog servers from /public_api/v1/integrations/syslog/get"
                    f" with payload {self._redacted_payload(data)}: {to_text(e)}"
                )
            )

    def get_syslog_server_by_name(self, name):
        """
        Get syslog server by name.

        Returns:
            list: List of syslog server objects
        """
        data = {"request_data": {"filters": [{"field": "name", "operator": "eq", "value": name}]}}
        return self.get_syslog_servers(data=data)

    def get_syslog_server_by_id(self, syslog_id):
        """
        Get syslog server by id.

        Returns:
            list: List of syslog server objects
        """
        data = {"request_data": {"filters": [{"field": "id", "operator": "eq", "value": syslog_id}]}}
        return self.get_syslog_servers(data=data)

    def create_syslog_server(self):
        """
        Create a new syslog server.

        Returns:
            dict: Created syslog server response
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/integrations/syslog/create",
                data=self.prepared_request_data,
            )
            if isinstance(response, dict):
                return response
            return {}
        except XSOARAPIError as e:
            self.module.fail_json(
                msg=(
                    f"Failed to create syslog server via /public_api/v1/integrations/syslog/create "
                    f"with payload {self._redacted_payload(self.prepared_request_data)}: {to_text(e)}"
                )
            )

    def update_syslog_server(self, current_server):
        """
        Update a syslog server.

        Returns:
            bool: Whether the update was successful
        """
        current_id = current_server.get("SYSLOG_INTEGRATION_ID")
        if current_id is None:
            self.module.fail_json(msg="Cannot update syslog server because SYSLOG_INTEGRATION_ID is missing.")

        request_data = dict(self.prepared_request_data["request_data"])
        request_data["syslog_id"] = str(current_id)

        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/integrations/syslog/update",
                data={"request_data": request_data},
            )
            if isinstance(response, dict):
                return bool(response.get("reply"))
            return False
        except XSOARAPIError as e:
            self.module.fail_json(
                msg=(
                    f"Failed to update syslog server via /public_api/v1/integrations/syslog/update "
                    f"with payload {self._redacted_payload({'request_data': request_data})}: {to_text(e)}"
                )
            )

    def delete_syslog_servers(self):
        """
        Delete syslog servers.

        Returns:
            dict: API response or empty dict for simple OK responses
        """
        try:
            response = self.connection.request(
                "POST",
                "/public_api/v1/integrations/syslog/delete",
                data=self.prepared_request_data,
            )
            if isinstance(response, dict):
                return response
            return {}
        except XSOARAPIError as e:
            self.module.fail_json(
                msg=(
                    f"Failed to delete syslog server(s) via /public_api/v1/integrations/syslog/delete "
                    f"with payload {self._redacted_payload(self.prepared_request_data)}: {to_text(e)}"
                )
            )


def ensure_present(module, syslog_server_manager):
    """
    Ensure syslog server is present.

    Args:
        module: AnsibleModule instance
        syslog_server_manager: XSOARSyslogServerManager instance

    Returns:
        dict: Result information
    """
    result = {}
    requested = syslog_server_manager.prepared_request_data.get("request_data", {})
    requested_name = requested.get("name")
    requested_id = requested.get("syslog_id")

    # Prefer syslog_id when supplied so callers can disambiguate duplicate names
    # that XSOAR allows when a server is created via both UI and API.
    if requested_id:
        matching_servers = syslog_server_manager.get_syslog_server_by_id(requested_id)
    else:
        matching_servers = syslog_server_manager.get_syslog_server_by_name(requested_name)
        if len(matching_servers) > 1:
            module.fail_json(
                msg=(
                    f"Multiple syslog servers found with name '{requested_name}'. "
                    "Supply request_data.syslog_id to target a specific server."
                )
            )
    current_server = matching_servers[0] if matching_servers else None

    if not current_server:
        if module.check_mode:
            result = {
                "changed": True,
                "msg": "Syslog server would be created",
                "syslog_server": syslog_server_manager.prepared_request_data,
            }
        else:
            syslog_server = syslog_server_manager.create_syslog_server()
            result = {
                "changed": True,
                "msg": f'Syslog server {syslog_server.get("name")} created',
                "syslog_server": syslog_server_manager.normalize_server(syslog_server),
            }
        return result

    normalized_current = syslog_server_manager.normalize_server(current_server)
    needs_update = instance_needs_update(normalized_current, syslog_server_manager.get_fields_to_compare())

    if module.check_mode:
        result = {
            "changed": needs_update,
            "msg": (
                "Syslog server would be updated (check mode)"
                if needs_update
                else "Syslog server is already up to date (check mode)"
            ),
            "syslog_server": normalized_current,
        }
    elif needs_update:
        syslog_server_manager.update_syslog_server(current_server)
        updated_servers = syslog_server_manager.get_syslog_server_by_name(requested_name)
        updated_server = updated_servers[0] if updated_servers else None
        result = {
            "changed": True,
            "msg": f"Syslog server {requested_name} updated",
            "syslog_server": (
                syslog_server_manager.normalize_server(updated_server) if updated_server else normalized_current
            ),
        }
    else:
        result = {
            "changed": False,
            "msg": "Syslog server is already up to date",
            "syslog_server": normalized_current,
        }

    return result


def ensure_absent(module, syslog_server_manager):
    """
    Ensure syslog server is absent.

    Args:
        module: AnsibleModule instance
        syslog_server_manager: XSOARSyslogServerManager instance

    Returns:
        dict: Result information
    """
    names = [
        f.get("value") for f in syslog_server_manager.request_data.get("filters", []) if f.get("field") == "name"
    ] or []
    target_name = names[0] if names else syslog_server_manager.request_data.get("name")

    if module.check_mode:
        matching_servers = syslog_server_manager.get_syslog_servers()
        result = {
            "changed": bool(matching_servers),
            "msg": (
                f"Syslog server(s) matching '{target_name}' would be deleted"
                if matching_servers
                else f"Syslog server(s) matching '{target_name}' do not exist"
            ),
        }
    else:
        matching_servers = syslog_server_manager.get_syslog_servers()
        if matching_servers:
            syslog_server_manager.delete_syslog_servers()
        result = {
            "changed": bool(matching_servers),
            "msg": (
                f"{len(matching_servers)} syslog server(s) matching '{target_name}' deleted"
                if matching_servers
                else f"Syslog server(s) matching '{target_name}' do not exist"
            ),
        }

    return result


def gather_syslog_servers(syslog_server_manager):
    """
    Gather syslog server information.

    Args:
        syslog_server_manager: XSOARSyslogServerManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    if syslog_servers := syslog_server_manager.get_syslog_servers():
        result["syslog_servers"] = [syslog_server_manager.normalize_server(server) for server in syslog_servers]
        result["msg"] = f"Retrieved {len(syslog_servers)} syslog servers."
    else:
        result["msg"] = "No syslog servers found."

    return result


def main():
    """Main function."""
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
                            field=dict(type="str", choices=["address", "id", "name", "status"], required=True),
                            operator=dict(type="str", choices=["eq"], required=True),
                            value=dict(type="raw", required=True),
                        ),
                    ),
                    syslog_id=dict(type="str", required=False),
                    name=dict(type="str", required=False),
                    address=dict(type="str", required=False),
                    port=dict(type="raw", required=False),
                    protocol=dict(type="str", choices=["TCP", "UDP", "TLS"], required=False),
                    facility=dict(type="str", choices=XSOARSyslogServerManager.FACILITIES, required=False),
                    security_info=dict(
                        type="dict",
                        required=False,
                        options=dict(
                            certificate_name=dict(type="str", required=False),
                            ignore_cert_errors=dict(type="bool", required=False),
                            certificate_content=dict(type="str", required=False, no_log=True),
                        ),
                    ),
                ),
            ),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not module.params.get("request_data"):
        module.fail_json(msg="request_data is required and must be populated.")

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    try:
        connection = get_connection(module)
        syslog_server_manager = XSOARSyslogServerManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    try:
        if syslog_server_manager.state == "present":
            result = ensure_present(module, syslog_server_manager)
        elif syslog_server_manager.state == "absent":
            result = ensure_absent(module, syslog_server_manager)
        else:
            result = gather_syslog_servers(syslog_server_manager)
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

    module.exit_json(**result)


if __name__ == "__main__":
    main()
