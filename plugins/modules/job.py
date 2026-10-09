#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


DOCUMENTATION = """
---
module: job
short_description: Manage XSOAR 8 scheduled jobs
description:
    - Create, update, delete, and gather information about scheduled jobs in Cortex XSOAR 8.
    - Jobs run playbooks on a recurring schedule defined by a cron expression.
    - Uses the XSOAR 8 REST API for all operations.
version_added: "1.0.0"
author:
    - Palo Alto Networks (@PaloAltoNetworks)
requirements:
    - requests
    - python-dateutil
notes:
    - Check mode is supported.
    - This module requires access to a Cortex XSOAR 8 instance with appropriate API permissions.
    - Uses the /xsoar/public/v1/jobs and /xsoar/public/v1/jobs/search endpoints.
    - Jobs are identified by I(name); only one job per name is expected.
    - Idempotency is based on I(cron), I(custom_fields), I(notify_owner), I(owner), I(playbook_id), I(severity), I(should_trigger_new), I(tags), and I(type).
    - Changes to I(start_date), I(end_date), I(ending_type), and I(close_previous_run) are not detected for idempotency, but are applied when any other tracked field triggers an update.
    - All dates are normalized to UTC ISO 8601 format before being sent to the API.
extends_documentation_fragment:
    - cortex.xsoar8.xsoar.PROVIDER
options:
    name:
        description:
            - The name of the job.
            - Required when state is C(present) or C(absent).
        type: str
    playbook_id:
        description:
            - The ID of the playbook to run.
            - Required when state is C(present).
        type: str
    cron:
        description:
            - The cron expression defining the job schedule.
            - Standard 5-field cron format (e.g., C(0 6 * * 1) for every Monday at 06:00).
            - Required when state is C(present).
        type: str
    active:
        description:
            - Whether the job is active and will run on schedule.
            - Maps to the C(isactive) field in the job's C(CustomFields).
        type: bool
        default: true
    close_previous_run:
        description:
            - Whether to close the incident from the previous job run before starting a new one.
        type: bool
        default: true
    custom_fields:
        description:
            - Additional custom fields to set on the job's incident.
            - Merged with fields managed by other parameters such as I(active).
        type: dict
        default: {}
    end_date:
        description:
            - The date and time at which the job stops running.
            - Accepts any date format supported by python-dateutil (e.g., C(2026-12-31T23:59:59Z)).
            - Only relevant when I(ending_type) is not C(never).
        type: str
    ending_type:
        description:
            - Determines when the job stops recurring.
            - C(never) - the job runs indefinitely.
            - Other values such as C(date) stop the job at I(end_date).
        type: str
        default: "never"
    notify_owner:
        description:
            - Whether to notify the job owner when the job runs.
        type: bool
        default: false
    owner:
        description:
            - The XSOAR username to assign as the job owner.
        type: str
        default: ""
    query:
        description:
            - A free-text search query for filtering jobs when state is C(gathered).
            - Follows the XSOAR query syntax.
            - Only used when state is C(gathered).
        type: str
    severity:
        description:
            - The severity level for the job's incident.
            - C(0) - Unknown.
            - C(0.5) - Informational.
            - C(1) - Low.
            - C(2) - Medium.
            - C(3) - High.
            - C(4) - Critical.
        type: float
        choices: [0, 0.5, 1, 2, 3, 4]
        default: 0
    should_trigger_new:
        description:
            - Whether to trigger a new job run even if a previous run is still active.
        type: bool
        default: true
    start_date:
        description:
            - The date and time at which the job starts.
            - Accepts any date format supported by python-dateutil, or the special value C(now).
            - Defaults to the current UTC time when set to C(now).
        type: str
        default: "now"
    tags:
        description:
            - Tags to apply to the job.
        type: list
        elements: str
        default: []
    type:
        description:
            - The incident type for the job.
            - Accepts any valid XSOAR incident type name.
        type: str
        default: "Unclassified"
    state:
        description:
            - The desired state of the job.
            - C(present) - Create or update the job.
            - C(absent) - Delete the job.
            - C(gathered) - Retrieve information about existing jobs.
        type: str
        choices: ['present', 'absent', 'gathered']
        default: 'present'
"""

EXAMPLES = """
- name: Create a daily scheduled job
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Daily Threat Intel Update"
    playbook_id: "ThreatIntelUpdate"
    cron: "0 6 * * *"
    active: true
    severity: 1
    owner: "admin"
    tags:
      - "threat-intel"
      - "automation"
    state: present

- name: Create a weekly job with an end date
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Weekly Compliance Scan"
    playbook_id: "ComplianceScan"
    cron: "0 8 * * 1"
    ending_type: "date"
    end_date: "2026-12-31T23:59:59Z"
    severity: 2
    state: present

- name: Create a job with a custom incident type and fields
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Phishing Report Job"
    playbook_id: "PhishingInvestigation"
    cron: "0 */4 * * *"
    type: "Phishing"
    severity: 2
    custom_fields:
      sourceip: "10.0.0.0/8"
    state: present

- name: Gather all jobs
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    state: gathered
  register: all_jobs

- name: Get a specific job by name
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Daily Threat Intel Update"
    state: gathered
  register: job_info

- name: Gather jobs matching a query
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    query: "tags:threat-intel"
    state: gathered
  register: matching_jobs

- name: Delete a job
  cortex.xsoar8.job:
    provider:
      server: "https://api-company.crtx.de.paloaltonetworks.com"
      api_key: "your-api-key"
      api_key_id: "your-api-key-id"
    name: "Daily Threat Intel Update"
    state: absent
"""

RETURN = """
changed:
    description: Whether the job was created, updated, or deleted.
    returned: always
    type: bool
    sample: true
job:
    description: Information about the job.
    returned: when state is present, when state is absent and the job existed,
              or when state is gathered and a matching job is found by name
    type: dict
    contains:
        id:
            description: The unique ID of the job.
            type: str
            sample: "12345678-1234-1234-1234-123456789abc"
        name:
            description: The name of the job.
            type: str
            sample: "Daily Threat Intel Update"
        playbookId:
            description: The ID of the playbook the job runs.
            type: str
            sample: "ThreatIntelUpdate"
        cron:
            description: The cron schedule expression.
            type: str
            sample: "0 6 * * *"
        startDate:
            description: The job start date in ISO 8601 format.
            type: str
            sample: "2026-01-01T06:00:00.000000Z"
        endingDate:
            description: The job end date in ISO 8601 format.
            type: str
            sample: "2026-12-31T23:59:59.000000Z"
        endingType:
            description: How the job ends (e.g., C(never) or C(date)).
            type: str
            sample: "never"
        severity:
            description: The incident severity level.
            type: float
            sample: 1
        owner:
            description: The job owner username.
            type: str
            sample: "admin"
        tags:
            description: Tags applied to the job.
            type: list
            sample: ["threat-intel", "automation"]
        type:
            description: The incident type.
            type: str
            sample: "Unclassified"
        CustomFields:
            description: Custom fields set on the job's incident, including C(isactive).
            type: dict
            sample: {"isactive": "true"}
jobs:
    description: List of jobs.
    returned: when state is gathered and the lookup returns multiple jobs
            (via a C(query) match or when neither C(name) nor C(query) is supplied)
    type: list
    elements: dict
    sample: [{"id": "abc123", "name": "Daily Threat Intel Update", "cron": "0 6 * * *"}]
msg:
    description: A message describing the result.
    returned: always
    type: str
    sample: "Job Daily Threat Intel Update created successfully"
"""

import copy
import traceback
from datetime import UTC, datetime

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_text

try:
    from dateutil.parser import parse

    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

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


class XSOARJobManager:
    """
    Manager class for XSOAR Job operations.
    """

    def __init__(self, connection):
        """
        Initialize the Job manager.

        Args:
            connection: XSOARConnection instance
        """
        self.connection = connection
        self.module = connection.module

        self.active = connection.module.params["active"]
        self.close_previous_run = connection.module.params["close_previous_run"]
        self.cron = connection.module.params["cron"]
        self.custom_fields = connection.module.params["custom_fields"]
        self.end_date = connection.module.params["end_date"]
        self.ending_type = connection.module.params["ending_type"]
        self.name = connection.module.params["name"]
        self.notify_owner = connection.module.params["notify_owner"]
        self.owner = connection.module.params["owner"]
        self.playbook_id = connection.module.params["playbook_id"]
        self.query = connection.module.params["query"]
        self.severity = connection.module.params["severity"]
        self.should_trigger_new = connection.module.params["should_trigger_new"]
        self.start_date = connection.module.params["start_date"]
        self.state = connection.module.params["state"]
        self.tags = connection.module.params["tags"]
        self.type = connection.module.params["type"]

        self.fields_to_compare = []

    def validate_and_normalize(self):
        """Normalize date inputs and build the idempotency compare list.

        Kept separate from __init__ so callers can distinguish parameter
        validation errors from connection-setup errors.
        """
        if self.state != "present":
            return

        if self.start_date == "now":
            self.start_date = datetime.now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            self.start_date = parse(self.start_date).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if self.ending_type == "never":
            self.end_date = self.start_date
        elif self.end_date:
            self.end_date = parse(self.end_date).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        expected_custom_fields = dict(self.custom_fields or {})

        if self.active is not None:
            expected_custom_fields["isactive"] = str(self.active).lower()

        self.fields_to_compare = [
            ("cron", self.cron),
            ("CustomFields", expected_custom_fields),
            ("notifyOwner", self.notify_owner),
            ("playbookId", self.playbook_id),
            ("severity", self.severity),
            ("shouldTriggerNew", self.should_trigger_new),
            ("tags", self.tags),
            ("type", self.type),
        ]
        # owner defaults to "" which is never sent to the API on update (the
        # build_job_data fallback preserves the existing value); comparing
        # "" against a non-empty current owner caused a perpetual changed=True.
        if self.owner:
            self.fields_to_compare.append(("owner", self.owner))

    def build_job_data(self, raw_job_data=None):
        """
        Build the data payload for creating or updating a Job.

        Args:
            raw_job_data (dict, optional): Raw job data from an existing job.

        Returns:
            dict: Data payload for Job operations
        """
        if raw_job_data:
            raw_job_data = copy.deepcopy(raw_job_data)
            raw_job_data["version"] = -1
            custom_fields = raw_job_data.get("CustomFields")
            if not isinstance(custom_fields, dict):
                custom_fields = {}
            if self.custom_fields:
                custom_fields.update(self.custom_fields)
            if self.active is not None:
                custom_fields["isactive"] = str(self.active).lower()
            if custom_fields:
                raw_job_data["CustomFields"] = custom_fields
            raw_job_data["cron"] = self.cron or raw_job_data.get("cron")
            raw_job_data["closePrevRun"] = (
                self.close_previous_run if self.close_previous_run is not None else raw_job_data.get("closePrevRun")
            )
            raw_job_data["endingDate"] = self.end_date or raw_job_data.get("endingDate")
            raw_job_data["endingType"] = self.ending_type or raw_job_data.get("endingType")
            raw_job_data["name"] = self.name or raw_job_data.get("name")
            raw_job_data["notifyOwner"] = (
                self.notify_owner if self.notify_owner is not None else raw_job_data.get("notifyOwner")
            )
            raw_job_data["owner"] = self.owner or raw_job_data.get("owner")
            raw_job_data["playbookId"] = self.playbook_id or raw_job_data.get("playbookId")
            raw_job_data["rawName"] = self.name or raw_job_data.get("rawName") or raw_job_data.get("name")
            raw_job_data["rawType"] = self.type or raw_job_data.get("rawType") or raw_job_data.get("type")
            raw_job_data["severity"] = self.severity if self.severity is not None else raw_job_data.get("severity")
            raw_job_data["shouldTriggerNew"] = (
                self.should_trigger_new if self.should_trigger_new is not None else raw_job_data.get("shouldTriggerNew")
            )
            raw_job_data["startDate"] = self.start_date or raw_job_data.get("startDate")
            raw_job_data["type"] = self.type or raw_job_data.get("type")
            return raw_job_data

        custom_fields = self.custom_fields if isinstance(self.custom_fields, dict) else {}
        if self.active is not None:
            custom_fields = dict(custom_fields)
            custom_fields["isactive"] = str(self.active).lower()

        job_data = {
            "atTimeHour": "",
            "atTimeMinute": "",
            "closePrevRun": self.close_previous_run,
            "cron": self.cron,
            "cronView": True,
            "CustomFields": custom_fields,
            "endingDate": self.end_date,
            "endingMomentOb": self.end_date,
            "endingType": self.ending_type,
            "humanCron": {},
            "isAllFeeds": False,
            "isDateSelectionOpen": False,
            "isFeed": False,
            "isStartDateSelectionOpen": False,
            "name": self.name,
            "notifyOwner": self.notify_owner,
            "owner": self.owner,
            "playbookId": self.playbook_id,
            "recurrent": True,
            "runOnce": False,
            "severity": self.severity,
            "scheduled": True,
            "schedulerEmpty": False,
            "selectedFeeds": [],
            "shouldTriggerNew": self.should_trigger_new,
            "startDate": self.start_date,
            "startMomentOb": self.start_date,
            "tags": self.tags or [],
            "times": 0,
            "timezone": "Europe/Brussels",
            "timezoneOffset": -60,
            "type": self.type,
            "valid": True,
        }

        return job_data

    def get_jobs(self, query=None):
        """
        Retrieve all Jobs.

        Returns:
            list: List of Jobs
        """
        data = {}
        if query:
            data["query"] = query
        try:
            response = self.connection.request(
                "POST",
                "/xsoar/public/v1/jobs/search",
                data=data,
            )
            # Extract Jobs from response and return
            if isinstance(response, dict):
                return response.get("data", [])
            return []
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to retrieve Jobs: {to_text(e)}")

    def get_job_by_name(self, name):
        """
        Retrieve a Job by name.

        Returns:
            dict or None: Job data if found, else None
        """
        if job := self.get_jobs(query=f'name:"{name}"'):
            return job[0]
        return None

    def create_job(self, job_data):
        """
        Create a new Job with the specified data.

        Returns:
            dict: Result of the create operation
        """
        try:
            response = self.connection.request(
                "POST",
                "/xsoar/public/v1/jobs",
                data=job_data,
            )
            return response
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to create Job: {to_text(e)}")

    def update_job(self, current_job):
        """
        Update an existing Job with the specified data.

        Args:
            current_job (dict): Current job data

        Returns:
            dict: Result of the update operation
        """
        try:
            response = self.connection.request(
                "POST",
                "/xsoar/public/v1/jobs",
                data=self.build_job_data(raw_job_data=current_job),
            )
            return response
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to update Job: {to_text(e)}")

    def delete_job(self, job_id):
        """
        Deletes the specified Job.

        Returns:
            dict: Result of the delete operation
        """
        try:
            response = self.connection.request("DELETE", f"/xsoar/public/v1/jobs/{job_id}")
            return response
        except XSOARAPIError as e:
            self.module.fail_json(msg=f"Failed to delete Job {job_id}: {to_text(e)}")


def ensure_present(module, job_manager):
    """
    Ensure Job is present.

    Args:
        module: AnsibleModule instance
        job_manager: XSOARJobManager instance

    Returns:
        dict: Result information
    """
    result = {}

    # Check if job exists
    if current_job := job_manager.get_job_by_name(job_manager.name):
        if module.check_mode:
            # Only report what would happen, do not update
            if instance_needs_update(current_job, job_manager.fields_to_compare):
                result = {
                    "changed": True,
                    "msg": f"Job {job_manager.name} would be updated",
                    "job": current_job,
                }
            else:
                result = {
                    "changed": False,
                    "msg": f"Job {job_manager.name} is already up to date (check mode)",
                    "job": current_job,
                }
        elif instance_needs_update(current_job, job_manager.fields_to_compare):
            updated_job = job_manager.update_job(current_job=current_job)
            result = {
                "changed": True,
                "msg": f"Job {job_manager.name} updated successfully",
                "job": updated_job,
            }
        else:
            # No update needed
            result = {
                "changed": False,
                "msg": f"Job {job_manager.name} is already up to date",
                "job": current_job,
            }
    else:
        job_data = job_manager.build_job_data()
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Job {job_manager.name} would be created",
                "job": job_data,
            }
        else:
            created_job = job_manager.create_job(job_data)
            result = {
                "changed": True,
                "msg": f"Job {job_manager.name} created successfully",
                "job": created_job,
            }

    return result


def ensure_absent(module, job_manager):
    """
    Ensure Job is absent.

    Args:
        module: AnsibleModule instance
        job_manager: XSOARJobManager instance

    Returns:
        dict: Result information
    """
    result = {}

    # Check if job exists
    if current_job := job_manager.get_job_by_name(job_manager.name):
        if module.check_mode:
            result = {
                "changed": True,
                "msg": f"Job {job_manager.name} would be deleted",
                "job": current_job,
            }
        else:
            job_manager.delete_job(current_job["id"])
            result = {
                "changed": True,
                "msg": f'Job {job_manager.name} with ID {current_job["id"]} deleted successfully',
                "job": current_job,
            }
    else:
        result = {
            "changed": False,
            "msg": f"Job {job_manager.name} does not exist",
        }

    return result


def gather_jobs(job_manager):
    """
    Gather Job information.

    Args:
        job_manager: XSOARJobManager instance

    Returns:
        dict: Result information
    """
    result = {"changed": False}

    # Get specific job name
    if job_manager.name:
        if job := job_manager.get_job_by_name(job_manager.name):
            result["job"] = job
            result["msg"] = f"Job {job_manager.name} found"
        else:
            result["msg"] = f"Job {job_manager.name} not found"
    elif job_manager.query:
        if jobs := job_manager.get_jobs(query=job_manager.query):
            result["jobs"] = jobs
            result["msg"] = f"Retrieved {len(jobs)} jobs matching query"
        else:
            result["msg"] = "No jobs found matching query"
    else:
        # Get all jobs
        if jobs := job_manager.get_jobs():
            result["jobs"] = jobs
            result["msg"] = f"Retrieved {len(jobs)} jobs"
        else:
            result["msg"] = "No jobs found"

    return result


def main():
    """Main function."""
    # Define module arguments
    argument_spec = xsoar_argument_spec()
    argument_spec.update(
        dict(
            active=dict(type="bool", default=True),
            close_previous_run=dict(type="bool", default=True),
            cron=dict(type="str"),
            custom_fields=dict(type="dict", default={}),
            end_date=dict(type="str"),
            ending_type=dict(type="str", default="never"),
            name=dict(type="str"),
            notify_owner=dict(type="bool", default=False),
            owner=dict(type="str", default=""),
            playbook_id=dict(type="str"),
            query=dict(type="str"),
            severity=dict(type="float", choices=[0, 0.5, 1, 2, 3, 4], default=0),
            should_trigger_new=dict(type="bool", default=True),
            start_date=dict(type="str", default="now"),
            state=dict(type="str", choices=["present", "absent", "gathered"], default="present"),
            tags=dict(type="list", elements="str", default=[]),
            type=dict(type="str", default="Unclassified"),
        )
    )

    # Create module
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[
            ["state", "present", ["name", "playbook_id", "cron"]],
            ["state", "absent", ["name"]],
        ],
        supports_check_mode=True,
    )

    if not HAS_LIB:
        module.fail_json(msg="Missing required library")

    if not HAS_DATEUTIL:
        module.fail_json(msg="The 'python-dateutil' library is required for this module")

    # Get connection and create job manager
    try:
        connection = get_connection(module)
        job_manager = XSOARJobManager(connection)
    except Exception as e:
        module.fail_json(msg=f"Failed to establish connection: {to_text(e)}")

    try:
        job_manager.validate_and_normalize()
    except Exception as e:
        module.fail_json(msg=f"Invalid job parameters: {to_text(e)}")

    # Execute based on state
    try:
        if job_manager.state == "present":
            result = ensure_present(module, job_manager)
        elif job_manager.state == "absent":
            result = ensure_absent(module, job_manager)
        else:  # gathered
            result = gather_jobs(job_manager)
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
