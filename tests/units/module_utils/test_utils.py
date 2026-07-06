"""
Unit tests for plugins/module_utils/utils.py — instance_needs_update.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_module, provider_params) come from tests/conftest.py
and are resolved automatically by pytest.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from plugins.module_utils.utils import instance_needs_update


class TestInstanceNeedsUpdate:
    def test_returns_false_when_all_values_match(self):
        current = {"name": "test", "enabled": "true", "version": 1}
        params = [("name", "test"), ("enabled", "true")]
        assert instance_needs_update(current, params) is False

    def test_returns_true_when_string_field_differs(self):
        current = {"name": "old-name"}
        params = [("name", "new-name")]
        assert instance_needs_update(current, params) is True

    def test_returns_false_for_empty_desired_params(self):
        current = {"name": "test"}
        assert instance_needs_update(current, []) is False

    def test_returns_true_when_field_absent_in_current(self):
        """A field that doesn't exist in current is treated as None, which differs."""
        current = {}
        params = [("name", "test")]
        assert instance_needs_update(current, params) is True

    def test_returns_false_when_both_values_are_none(self):
        current = {"engine": None}
        params = [("engine", None)]
        assert instance_needs_update(current, params) is False

    def test_bool_true_matches_string_true(self):
        """``True`` normalises to ``'true'`` so it equals the API string value."""
        current = {"enabled": "true"}
        params = [("enabled", True)]
        assert instance_needs_update(current, params) is False

    def test_bool_false_matches_string_false(self):
        current = {"enabled": "false"}
        params = [("enabled", False)]
        assert instance_needs_update(current, params) is False

    def test_list_order_does_not_matter(self):
        """Lists are sorted element-wise before comparison."""
        current = {"labels": ["b", "a", "c"]}
        params = [("labels", ["a", "b", "c"])]
        assert instance_needs_update(current, params) is False

    def test_list_differs_when_elements_differ(self):
        current = {"labels": ["a", "b"]}
        params = [("labels", ["a", "c"])]
        assert instance_needs_update(current, params) is True

    def test_list_differs_when_lengths_differ(self):
        current = {"labels": ["a"]}
        params = [("labels", ["a", "b"])]
        assert instance_needs_update(current, params) is True

    def test_name_value_list_no_update_when_matching(self):
        """Configuration lists are compared via name→value lookup, not position."""
        current_config = [
            {"name": "apikey", "value": "secret"},
            {"name": "threshold", "value": 10},
        ]
        desired_config = [
            {"name": "apikey", "value": "secret"},
            {"name": "threshold", "value": 10},
        ]
        assert instance_needs_update({"data": current_config}, [("data", desired_config)]) is False

    def test_name_value_list_update_when_value_differs(self):
        current_config = [{"name": "apikey", "value": "old-secret"}]
        desired_config = [{"name": "apikey", "value": "new-secret"}]
        assert instance_needs_update({"data": current_config}, [("data", desired_config)]) is True

    def test_name_value_list_type_9_items_excluded(self):
        """Credential (type 9) entries are never compared."""
        current_config = [{"name": "creds", "value": {"password": "old"}, "type": 9}]
        desired_config = [{"name": "creds", "value": {"password": "new"}, "type": 9}]
        assert instance_needs_update({"data": current_config}, [("data", desired_config)]) is False

    def test_name_value_list_type_4_items_excluded(self):
        """Type 4 entries are also excluded from comparison."""
        current_config = [{"name": "enc", "value": "old", "type": 4}]
        desired_config = [{"name": "enc", "value": "new", "type": 4}]
        assert instance_needs_update({"data": current_config}, [("data", desired_config)]) is False

    def test_name_value_list_skips_keys_absent_in_current(self):
        """Desired keys absent in current are silently skipped to avoid false positives."""
        current_config = [{"name": "known", "value": "val"}]
        desired_config = [
            {"name": "known", "value": "val"},
            {"name": "unknown", "value": "x"},
        ]
        assert instance_needs_update({"data": current_config}, [("data", desired_config)]) is False

    def test_module_debug_calls_warn_when_update_needed(self):
        """When module is provided and a diff is detected, warn is called with context."""
        module = MagicMock()
        result = instance_needs_update({"name": "old"}, [("name", "new")], module=module)

        assert result is True
        module.warn.assert_called_once()

    def test_module_debug_warn_includes_field_and_values(self):
        """warn message carries field, desired, current, and both normalized values."""
        module = MagicMock()

        instance_needs_update({"status": "disabled"}, [("status", "enabled")], module=module)

        module.warn.assert_called_once()
        warning_message = module.warn.call_args.args[0]
        assert "field=status" in warning_message
        assert "desired=enabled" in warning_message
        assert "current=disabled" in warning_message
        assert "normalized_desired=enabled" in warning_message
        assert "normalized_current=disabled" in warning_message

    def test_no_warn_when_values_match_with_module(self):
        """module.warn must not be called when there is no diff."""
        module = MagicMock()
        result = instance_needs_update({"name": "same"}, [("name", "same")], module=module)
        assert result is False
        module.warn.assert_not_called()

    def test_module_warn_handles_name_value_lists_with_nested_dicts(self):
        """
        Regression test: when module warnings are enabled and integration
        configuration differs, mismatch formatting must not crash while
        normalizing list items that are dicts.
        """
        module = MagicMock()
        current_config = [
            {"name": "basic_credentials", "value": {"credential": "jira-cred-old"}, "type": 9},
            {"name": "cloud_id", "value": "old"},
        ]
        desired_config = [
            {"name": "basic_credentials", "value": {"credential": "jira-cred-new"}, "type": 9},
            {"name": "cloud_id", "value": "new"},
        ]

        result = instance_needs_update({"data": current_config}, [("data", desired_config)], module=module)

        assert result is True
        module.warn.assert_called_once()
