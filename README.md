# Cortex XSOAR 8 SaaS Ansible Collection

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)

The **Palo Alto Networks Cortex XSOAR 8 SaaS Ansible Collection** provides modules and plugins to automate configuration and operational tasks on the Cortex XSOAR 8 SaaS platform using the REST API.

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
  - [From GitHub](#from-github)
  - [Using requirements.yml](#using-requirementsyml)
- [Authentication](#authentication)
- [Quick Start](#quick-start)
- [Available Modules](#available-modules)
- [Examples](#examples)
- [Testing](#testing)
- [License](#license)
- [Changelog](#changelog)

## Overview

This collection enables Infrastructure as Code (IaC) for Cortex XSOAR 8 SaaS deployments, allowing you to:

- 🔑 **Manage API keys** — create, rotate, filter, and delete XSOAR 8 API keys
- 🔐 **Manage credentials** — create and maintain username/password, SSH, and workgroup credential objects
- 🔌 **Manage integrations** — configure and lifecycle-manage integration instances and their settings
- 📋 **Manage jobs** — create and update scheduled automation jobs
- 📝 **Manage indicator lists** — maintain allow/block lists and other XSOAR indicator list types
- 🏢 **Manage tenants** — provision and deprovision XSOAR 8 MSSP tenants
- 🔄 **Sync tenant content** — push content updates across MSSP tenants
- 🛡️ **Manage pre-process rules** — configure incident ingestion pre-process rules
- ⚙️ **Manage server settings** — read and write XSOAR 8 server configuration keys
- 📡 **Manage syslog servers** — configure SaaS syslog forwarding integrations

## Requirements

### System Requirements

- **Ansible**: ansible-core >=2.16
- **Python**: >=3.12
- **Operating System**: Linux, macOS, or Windows with WSL
- **Network Access**: HTTPS connectivity to your Cortex XSOAR 8 SaaS instance

### Python Dependencies

```txt
requests>=2.25.1
python-dateutil>=2.8.2
```

These dependencies are listed in [requirements.txt](requirements.txt). When installing the collection via `ansible-galaxy collection install`, install the Python dependencies separately (e.g. `pip install -r requirements.txt`).

## Installation

### From GitHub

Install directly from the GitHub repository:

```bash
# Install from main branch
ansible-galaxy collection install git+git@github.com:NVISOsecurity/cortex-xsoar8-ansible.git

# Install from specific branch or tag
ansible-galaxy collection install git+git@github.com:NVISOsecurity/cortex-xsoar8-ansible.git,v1.0.0
```

### Using requirements.yml

Create a `requirements.yml` file for reproducible installations:

```yaml
# requirements.yml
---
collections:
  # From GitHub
  - name: git@github.com:NVISOsecurity/cortex-xsoar8-ansible.git
    type: git
    version: main

  # From local path (development)
  - name: /path/to/cortex-xsoar8-ansible
    type: file
```

Install using requirements file:

```bash
ansible-galaxy collection install -r requirements.yml --force
```

### Verification

Verify the installation:

```bash
# List installed collections
ansible-galaxy collection list

# Verify specific collection
ansible-galaxy collection list cortex.xsoar8

# Check collection path
ansible-config dump | grep COLLECTIONS_PATHS

# Test collection import
ansible-doc cortex.xsoar8.integration
```

## Authentication

The collection authenticates against the Cortex XSOAR 8 REST API using an API key plus key ID, with a configurable security level (C(standard) or C(advanced)). Credentials can be supplied via  `provider` dict, top-level parameters, environment variables, or Ansible Vault.

### API Key Authentication (Recommended)

```yaml
# In your playbook
vars:
  xsoar_provider:
    server: "https://api-{{ company_name }}.crtx.de.paloaltonetworks.com"
    api_key: "{{ xsoar_api_key }}"
    api_key_id: "{{ xsoar_api_key_id }}"
    verify_ssl: true  # Optional, defaults to true
```

### Authentication Compatibility Notes

- Some Cortex XSOAR endpoints can behave differently with Global Management Key authentication.
- In particular, multi-tenant synchronization APIs used by `cortex.xsoar8.multi_tenant_sync_account`
  may fail or be restricted when called with a Global Management Key, depending on tenant/backend behavior.
- If you encounter authorization or endpoint errors, retry with a standard API key that has the required
  MSSP and content synchronization permissions.


## Quick Start

### 1. Basic Integration Configuration

Create your first playbook to configure a VirusTotal integration:

```yaml
# basic_setup.yml
---
- name: Configure XSOAR Integration
  hosts: localhost
  gather_facts: no
  vars:
    xsoar_provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "{{ xsoar_api_key }}"
      api_key_id: "{{ xsoar_api_key_id }}"

  tasks:
    - name: Create VirusTotal integration
      cortex.xsoar8.integration:
        provider: "{{ xsoar_provider }}"
        name: "VirusTotal_Production"
        brand: "VirusTotal"
        enabled: true
        configuration:
          apikey: "{{ virustotal_api_key }}"
          reliability: "B - Usually reliable"
          threshold: 10
        state: present
      register: result

    - name: Display result
      debug:
        var: result
```

### 2. Run the Playbook

```bash
# Create variables file
cat > vars.yml << EOF
xsoar_api_key: "your-xsoar-api-key"
xsoar_api_key_id: "your-xsoar-api-key-id"
virustotal_api_key: "your-virustotal-api-key"
EOF

# Run playbook
ansible-playbook basic_setup.yml --extra-vars @vars.yml
```

## Available Modules

| Module | Description | Status |
|--------|-------------|--------|
| `api_key` | Manage XSOAR 8 API keys | ✅ Stable |
| `credential` | Manage XSOAR 8 credential objects | ✅ Stable |
| `integration` | Manage XSOAR 8 integration instances | ✅ Stable |
| `job` | Manage XSOAR 8 scheduled jobs | ✅ Stable |
| `list` | Manage XSOAR 8 indicator lists | ✅ Stable |
| `multi_tenant` | Manage XSOAR 8 MSSP tenant provisioning | ✅ Stable |
| `multi_tenant_sync_account` | Sync content across MSSP tenants | ✅ Stable |
| `pre_process_rule` | Manage XSOAR 8 pre-process rules | ✅ Stable |
| `server_settings` | Manage XSOAR 8 server configuration settings | ✅ Stable |
| `syslog_server` | Manage XSOAR 8 SaaS syslog server integrations | ✅ Stable |

### Module Documentation

Access detailed module documentation:

```bash
# List all modules in collection
ansible-doc -l cortex.xsoar8

# View specific module documentation
ansible-doc cortex.xsoar8.integration
ansible-doc cortex.xsoar8.credential

# View module examples
ansible-doc cortex.xsoar8.integration -s
ansible-doc cortex.xsoar8.credential -s
```

## Examples

### Credential Management Examples

```yaml
# Create a username/password credential
- name: Create Splunk service account credential
  cortex.xsoar8.credential:
    provider: "{{ xsoar_provider }}"
    name: "splunk_production_creds"
    username: "xsoar_service"
    password: "{{ splunk_password }}"
    state: present

# List all credentials
- name: Get all credentials
  cortex.xsoar8.credential:
    provider: "{{ xsoar_provider }}"
    state: gathered
```

### Integration Management Examples

```yaml
# Get all available integration brands
- name: Discover available integration brands
  cortex.xsoar8.integration:
    provider: "{{ xsoar_provider }}"
    get_available: true
    state: gathered

# Delete an integration
- name: Remove integration
  cortex.xsoar8.integration:
    provider: "{{ xsoar_provider }}"
    name: "Old_Integration"
    state: absent
```

### Advanced Configuration Examples

For comprehensive examples, see the [playbooks directory](./playbooks/):

- `api_keys_management.yml` — API key lifecycle management
- `credentials_management.yml` — Credential creation and rotation patterns
- `integration_management.yml` — Integration configuration with inline API keys
- `integration_with_credentials.yml` — Integration configuration using stored credential objects
- `job_management.yml` — Scheduled job creation and management
- `list_management.yml` — Indicator list management
- `multi_tenant_management.yml` — MSSP tenant provisioning
- `multi_tenant_sync_account_management.yml` — Cross-tenant content sync
- `pre_process_rule_management.yml` — Pre-process rule lifecycle
- `server_settings_management.yml` — Server configuration management
- `syslog_server_management.yml` — Syslog server configuration

## Testing

```bash
# 1. Install Python dependencies
pip install -r requirements.txt -r requirements-tests.txt

# 2. Install the collection locally (required for test imports)
ansible-galaxy collection install . --force

# 3. Run all unit tests
PYTHONPATH=.:~/.ansible/collections python -m pytest tests/units/ -v

# Run a single module's tests
PYTHONPATH=.:~/.ansible/collections python -m pytest tests/units/modules/list/test_list.py -v

# Run all unit tests with no pycache files created
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:~/.ansible/collections python -m pytest tests/units/ -v -p no:cacheprovider
```

Step 2 is required because the tests import from `ansible_collections.cortex.xsoar8.*`. Re-run it whenever you make changes to `plugins/` that you want reflected in the tests.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.rst](CHANGELOG.rst) for version history and release notes.
