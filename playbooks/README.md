# Cortex XSOAR 8 Playbook Examples

This directory contains example playbooks for managing Cortex XSOAR 8 resources using the `cortex.xsoar8` Ansible collection.

## Overview

Each playbook covers the full lifecycle of one resource type (create/update, gather, delete) and uses tag-based execution so individual operations can be run independently. All playbooks load provider credentials from `vars/xsoar.yml` and support `--check` mode.

## Provider Configuration

All playbooks load connection details from `../vars/xsoar.yml`. Create this file before running any playbook:

```yaml
# vars/xsoar.yml
server: "https://api-<tenant>.xdr.paloaltonetworks.com"
api_key: "your-api-key"
api_key_id: "your-api-key-id"
```

## Playbooks

### `api_keys_management.yml`

Manage XSOAR 8 API keys (`cortex.xsoar8.api_key`).

| Tag | Operation |
|-----|-----------|
| `create` | Create a basic API key |
| `create_advanced` | Create a key with comment, roles, and expiration |
| `gather` | Gather all keys (default expiration filter applied) |
| `gather_filtered` | Gather keys using custom filters (roles, expiration) |
| `delete` | Delete a key by ID filter |

```bash
ansible-playbook playbooks/api_keys_management.yml --tags create
ansible-playbook playbooks/api_keys_management.yml --tags gather_filtered
ansible-playbook playbooks/api_keys_management.yml --tags delete
```

---

### `credentials_management.yml`

Manage XSOAR 8 credential objects (`cortex.xsoar8.credential`).

Supported credential types demonstrated: username/password (Azure, AD workgroup) and SSH key.

| Tag | Operation |
|-----|-----------|
| `create_az` | Create an Azure Sentinel credential (username + password) |
| `create_wc` | Create a workgroup credential (AD service account) |
| `create_ssh` | Create an SSH key credential |
| `gather_all` | Gather all credentials |
| `gather` | Gather a specific credential by name |
| `delete` | Delete a credential by name |

```bash
ansible-playbook playbooks/credentials_management.yml --tags create_az \
  -e "azure_client_id=<id>" -e "azure_client_secret=<secret>"
ansible-playbook playbooks/credentials_management.yml --tags gather_all
ansible-playbook playbooks/credentials_management.yml --tags delete
```

> **Note**: `password` and `certificate` are write-only. Only `username` and `workgroup` are compared for idempotency checks.

---

### `integration_management.yml`

Manage XSOAR 8 integration instances (`cortex.xsoar8.integration`).
Demonstrates a VirusTotal integration with an inline API key.

| Tag | Operation |
|-----|-----------|
| `create` | Create or update a VirusTotal integration instance |
| `gather` | Gather all instances and a specific instance by name |
| `delete` | Delete an integration instance by name |

```bash
ansible-playbook playbooks/integration_management.yml --tags create \
  -e "vt_api_key=<key>"
ansible-playbook playbooks/integration_management.yml --tags gather
ansible-playbook playbooks/integration_management.yml --tags delete
```

For integrations that reference a XSOAR credential object, use `integration_with_credentials.yml`.

---

### `integration_with_credentials.yml`

Create an integration instance by referencing an existing XSOAR credential object (`cortex.xsoar8.integration` + `cortex.xsoar8.credential`).

Demonstrates the Azure Sentinel integration flow.

> **Important**: The credential-related key under `configuration` is integration-specific. This playbook uses `configuration.credentials` for Azure Sentinel, while other integrations can use a different key (for example `creds_apikey`). Verify the exact key in the integration settings before running the playbook.

| Tag | Operation |
|-----|-----------|
| `create_azure` | Fetch credential by name and create the Azure Sentinel integration |
| `gather_azure` | Gather the Azure Sentinel integration by name |
| `delete_azure` | Delete the Azure Sentinel integration by name |

```bash
# Step 1 — create credential (if not already present)
ansible-playbook playbooks/credentials_management.yml --tags create_az \
  -e "azure_client_id=<id>" -e "azure_client_secret=<secret>"

# Step 2 — create integration using the credential
ansible-playbook playbooks/integration_with_credentials.yml --tags create_azure \
  -e "azure_tenant_id=<tid>" -e "azure_subscription_id=<sid>" \
  -e "azure_resource_group=<rg>" -e "azure_workspace=<ws>"
```

Optional overrides: `-e "azure_credential_name=..."`, `-e "azure_integration_name=..."`.

---

### `job_management.yml`

Manage XSOAR 8 scheduled jobs (`cortex.xsoar8.job`).

| Tag | Operation |
|-----|-----------|
| `create` | Create a daily job with severity, owner, and tags |
| `create_advanced` | Create a weekly job with end date and a job with custom fields/type |
| `gather` | Gather all jobs and a specific job by name |
| `gather_filtered` | Gather jobs matching a free-text query |
| `delete` | Delete a job by name |

```bash
ansible-playbook playbooks/job_management.yml --tags create \
  -e "threat_intel_playbook_id=<uuid>"
ansible-playbook playbooks/job_management.yml --tags gather
ansible-playbook playbooks/job_management.yml --tags delete
```

> **Note**: `playbook_id` must be a valid playbook ID (UUID or name) from your XSOAR instance.

---

### `list_management.yml`

Manage XSOAR 8 list objects (`cortex.xsoar8.list`).

| Tag | Operation |
|-----|-----------|
| `create_text` | Create a plain text list; also demonstrates role-based access restrictions |
| `create_json` | Create a JSON-typed list using `json_content` (object or array) |
| `gather` | Gather all lists and a specific list by name |
| `delete` | Delete a list by name |

```bash
ansible-playbook playbooks/list_management.yml --tags create_text
ansible-playbook playbooks/list_management.yml --tags create_json
ansible-playbook playbooks/list_management.yml --tags gather
ansible-playbook playbooks/list_management.yml --tags delete
```

> **Note**: `content` and `json_content` are mutually exclusive. Use `json_content` when `content_type` is `JSON`; it can be either a JSON object or a JSON array.

---

### `pre_process_rule_management.yml`

Manage XSOAR 8 pre-process rules (`cortex.xsoar8.pre_process_rule`).

| Tag | Operation |
|-----|-----------|
| `create_drop` | Create a rule that drops duplicate events |
| `create_link` | Create a rule that links duplicate events to an existing incident |
| `create_drop_update` | Create a rule that drops and updates the matched incident |
| `create_script` | Create a rule that runs a custom deduplication script |
| `disable` | Disable a rule by updating it with `enabled: false` |
| `gather` | Gather all rules and a specific rule by name |
| `delete` | Delete a rule by name |

```bash
ansible-playbook playbooks/pre_process_rule_management.yml --tags create_drop
ansible-playbook playbooks/pre_process_rule_management.yml --tags create_script \
  -e "dedup_script_id=<script-id>"
ansible-playbook playbooks/pre_process_rule_management.yml --tags gather
ansible-playbook playbooks/pre_process_rule_management.yml --tags delete
```

> **Note**: `script_id` is required when `action` is `script`.

---

### `server_settings_management.yml`

Manage XSOAR 8 server configuration settings (`cortex.xsoar8.server_settings`).

| Tag | Operation |
|-----|-----------|
| `gather` | Retrieve all current server settings |
| `update` | Merge audit and condition settings into the configuration |
| `update_email` | Merge e-mail notification settings into the configuration |
| `delete` | Remove specific setting keys from the configuration |

```bash
ansible-playbook playbooks/server_settings_management.yml --tags gather
ansible-playbook playbooks/server_settings_management.yml --tags update
ansible-playbook playbooks/server_settings_management.yml --tags delete
```

> **Note**: `present` merges — unlisted keys are left unchanged. `absent` removes only the listed keys. Setting keys use XSOAR dot-notation (e.g. `audit.log.playground.user.commands`).

---

### `syslog_server_management.yml`

Manage XSOAR 8 syslog server integrations (`cortex.xsoar8.syslog_server`).

| Tag | Operation |
|-----|-----------|
| `create` | Create or update a UDP syslog server |
| `create_tls` | Create or update a TLS syslog server with a named certificate |
| `gather` | Gather a specific syslog server by name |
| `gather_filtered` | Gather syslog servers in error state |
| `delete` | Delete a syslog server by name filter |

```bash
ansible-playbook playbooks/syslog_server_management.yml --tags create \
  -e "syslog_dest_ip=203.0.113.10"
ansible-playbook playbooks/syslog_server_management.yml --tags create_tls \
  -e "syslog_tls_address=203.0.113.20" -e "tls_cert_name=syslog-tls-cert"
ansible-playbook playbooks/syslog_server_management.yml --tags gather
ansible-playbook playbooks/syslog_server_management.yml --tags gather_filtered
ansible-playbook playbooks/syslog_server_management.yml --tags delete
```

> **Note**: The XSOAR API rejects private (RFC 1918) IP addresses for `address`. Use a publicly routable IP. At least one filter object is required for `absent` and `gathered` states. The `status` filter field accepts `ACTIVE` or `ERROR` (uppercase). XSOAR can hold two servers with the same name (one UI-created, one API-created); a name-based `absent` will delete both.

---

### `multi_tenant_management.yml`

Manage XSOAR 8 MSSP child tenants (`cortex.xsoar8.multi_tenant`).

| Tag | Operation |
|-----|-----------|
| `create` | Create a new child tenant |
| `gather_all` | Gather all tenants (no filter) |
| `gather` | Gather a specific tenant by name |
| `delete_by_name` | Delete a tenant by name; module resolves remaining identifiers via API lookup |
| `delete_by_all_ids` | Delete a tenant by supplying all three identifiers; skips the API lookup |

```bash
ansible-playbook playbooks/multi_tenant_management.yml --tags create \
  -e "tenant_name=acme-corp" -e "tenant_subdomain=acme" \
  -e "tenant_initial_user=admin@acme.com" -e "tenant_data_retention=365"
ansible-playbook playbooks/multi_tenant_management.yml --tags gather_all
ansible-playbook playbooks/multi_tenant_management.yml --tags gather -e "tenant_name=acme-corp"
ansible-playbook playbooks/multi_tenant_management.yml --tags delete_by_name -e "tenant_name=acme-corp"
ansible-playbook playbooks/multi_tenant_management.yml --tags delete_by_all_ids \
  -e "tenant_cortex_id=cortex-abc123" -e "tenant_id=tenant-abc123" -e "tenant_name=acme-corp"
```

> **Note**: All MSSP endpoints require a **Global Management API key**. A standard tenant-scoped key will be rejected with a 403 error — ensure the credentials in `vars/xsoar.yml` belong to a Global Management key created at the MSSP management level. For `absent`, you may supply only one identifier (`cortex_id`, `tenant_name`, or `tenant_id`) and the module will resolve the rest automatically via an API lookup. If the tenant is not found, the module returns `changed=False` (idempotent). Supplying all three identifiers skips the lookup entirely. `state=present` is not idempotent with respect to updates — if a tenant with the given name already exists, no update is performed and `changed=False` is returned.

---

### `multi_tenant_sync_account_management.yml`

Manage sync candidates and content synchronization for XSOAR 8 MSSP child tenants (`cortex.xsoar8.multi_tenant_sync_account`).

| Tag | Operation |
|-----|-----------|
| `sync_selected` | Sync selected item names for selected accounts |
| `sync_all` | Sync all pending items for all running accounts |
| `gather_selected` | Gather sync candidates for selected accounts/items |
| `gather_all` | Gather sync candidates for all running accounts |

```bash
ansible-playbook playbooks/multi_tenant_sync_account_management.yml --tags sync_selected
ansible-playbook playbooks/multi_tenant_sync_account_management.yml --tags sync_all
ansible-playbook playbooks/multi_tenant_sync_account_management.yml --tags gather_selected
ansible-playbook playbooks/multi_tenant_sync_account_management.yml --tags gather_all
```

> **Note**: `all_accounts` and `accounts` are mutually exclusive. `all_items` and `items` are mutually exclusive.

> **Global Management Key compatibility**: Some multi-tenant sync endpoints may be incompatible with, or may not work when using, Global Management Key authentication depending on backend/tenant configuration. If you encounter authorization or endpoint errors, verify key scope/permissions and retry with a standard API key that has MSSP and content sync permissions.

---

## Check Mode

All playbooks support `--check` to preview changes without applying them:

```bash
ansible-playbook playbooks/<playbook>.yml --tags <tag> --check
```

## Troubleshooting

**Authentication errors** — verify `server`, `api_key`, and `api_key_id` in `vars/xsoar.yml`.

**SSL errors** — uncomment `verify_ssl: true` (or set to `false` for self-signed certs) in the `xsoar_provider` var block.

**Verbose output** — add `-vvv` for full API request/response details.

## License

Apache License 2.0 — see the LICENSE file for details.