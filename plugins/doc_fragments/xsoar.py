#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


class ModuleDocFragment:
    # Shared provider connection options for Cortex XSOAR modules.
    PROVIDER = r"""
options:
  provider:
    description:
      - Connection options for Cortex XSOAR.
      - Provider values override top-level values when both are supplied.
    type: dict
    suboptions:
      server:
        description:
          - Cortex XSOAR base URL.
        type: str
      api_key:
        description:
          - Cortex XSOAR API key.
        type: str
      api_key_id:
        description:
          - API key ID (required with C(api_key)).
        type: str
      security_level:
        description:
          - API security level.
          - Defaults to the top-level C(security_level) value when not set.
        type: str
        choices: [standard, advanced]
      verify_ssl:
        description:
          - Whether to verify TLS certificates.
          - Defaults to the top-level C(verify_ssl) value when not set.
        type: bool
      timeout:
        description:
          - HTTP request timeout in seconds.
          - Defaults to the top-level C(timeout) value when not set.
        type: int
  server:
    description:
      - Cortex XSOAR base URL.
      - Used when C(provider.server) is not set.
    type: str
  api_key:
    description:
      - Cortex XSOAR API key.
      - Used when C(provider.api_key) is not set.
    type: str
  api_key_id:
    description:
      - API key ID (required with C(api_key)).
      - Used when C(provider.api_key_id) is not set.
    type: str
  security_level:
    description:
      - API security level.
      - Used when C(provider.security_level) is not set.
    type: str
    choices: [standard, advanced]
    default: standard
  verify_ssl:
    description:
      - Whether to verify TLS certificates.
      - Used when C(provider.verify_ssl) is not set.
    type: bool
    default: true
  timeout:
    description:
      - HTTP request timeout in seconds.
      - Used when C(provider.timeout) is not set.
    type: int
    default: 30
"""
