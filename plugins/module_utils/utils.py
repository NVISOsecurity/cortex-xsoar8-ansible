#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


def instance_needs_update(current_instance, desired_params, module=None):
    """
    Check if an instance update is needed.

    Args:
        current_instance (dict): Current instance data
        desired_params (list): List of tuples (field, new_value)
        module (AnsibleModule, optional): Ansible module instance for debug warnings

    Returns:
        bool: True if update is needed, False otherwise
    """

    def normalize(val):
        """
        Normalize values for consistent comparison.
        """
        if val is None:
            return None
        if isinstance(val, bool):
            return str(val).lower()
        if isinstance(val, list):
            normalized_items = [normalize(v) for v in val]
            # Lists can contain dict/list items (for example integration
            # configuration payloads). Python cannot compare dicts directly
            # while sorting, so use a deterministic textual key.
            return sorted(normalized_items, key=lambda item: repr(item))
        if isinstance(val, dict):
            return {k: normalize(v) for k, v in sorted(val.items())}
        return val

    def is_name_value_list(lst):
        """Check if list contains dicts with 'name' and 'value' keys."""
        return lst and isinstance(lst[0], dict) and "name" in lst[0] and "value" in lst[0]

    def list_to_dict(lst):
        """Convert list of dicts to name:value dict.

        Tightly coupled to the integration module's configuration shape:
        type 4 (encrypted) and type 9 (credential/password) items are skipped
        because their API-returned values are masked and would always look
        different from the user-supplied plaintext.
        """
        return {item.get("name"): item.get("value") for item in lst if item.get("type") not in (4, 9)}

    def values_differ(new_val, current_val):
        """
        Check if values differ, with recursive partial comparison for dicts.
        """
        # Special handling for name-value lists (integration configuration)
        if isinstance(new_val, list) and isinstance(current_val, list) and is_name_value_list(new_val):
            new_dict = list_to_dict(new_val)
            current_dict = list_to_dict(current_val)
            # Only compare keys present in new_dict that have values in current_dict (ignore empty/unset fields)
            return any(
                values_differ(new_dict[k], current_dict[k])
                for k in new_dict
                if k in current_dict and current_dict[k] is not None
            )
        return normalize(new_val) != normalize(current_val)

    def emit_mismatch_warning(field, desired, current):
        """Emit best-effort mismatch details for troubleshooting without aborting execution."""
        if not module:
            return

        message = (
            "Instance mismatch detected "
            f"(field={field}, desired={desired}, current={current}, "
            f"normalized_desired={normalize(desired)}, normalized_current={normalize(current)})"
        )

        # Prefer warn() so callers keep the bool return contract and can still inspect differences.
        if hasattr(module, "warn"):
            module.warn(message)
            return

        # Fallback for non-Ansible test doubles that expose no warning interface.
        elif hasattr(module, "log"):
            module.log(message)
            return
        return

    for field, new_value in desired_params:
        current_value = current_instance.get(field)
        if values_differ(new_value, current_value):
            emit_mismatch_warning(field=field, desired=new_value, current=current_value)
            return True

    return False
