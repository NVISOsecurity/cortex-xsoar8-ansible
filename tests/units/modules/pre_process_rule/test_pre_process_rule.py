"""
Unit tests for plugins/modules/pre_process_rule.py — XSOARPreProcessRuleManager
and state functions.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_connection, mock_module, provider_params) come from
tests/conftest.py and are resolved automatically by pytest.
"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest
from ansible_collections.cortex.xsoar8.plugins.module_utils.xsoar import XSOARAPIError

from plugins.modules.pre_process_rule import (
    XSOARPreProcessRuleManager,
    ensure_absent,
    ensure_present,
    gather_pre_process_rules,
    main,
)
from tests.conftest import AnsibleModuleExit, AnsibleModuleFail

# ===========================================================================
# XSOARPreProcessRuleManager.get_rule_filters
# ===========================================================================

class TestGetRuleFilters:
    def test_returns_response(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        response = {"isEqualString": {"type": "string", "isSingleValue": False}}
        manager.connection.request.return_value = response

        assert manager.get_rule_filters() is response
        manager.connection.request.assert_called_once_with("GET", "/xsoar/preprocess/filters")
        manager.module.log.assert_not_called()

    def test_logs_api_failure_and_returns_empty_dict(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        assert manager.get_rule_filters() == {}
        manager.module.log.assert_called_once_with(msg="Failed to get pre-process rule filters: network error")


# ===========================================================================
# XSOARPreProcessRuleManager.validate_filters and build_filters
# ===========================================================================


@pytest.mark.usefixtures("operator_metadata")
class TestRuleFilters:
    @pytest.mark.parametrize("condition_groups", [
        ((0,),),
        ((0, 1),),
        ((0,), (1,), (2,)),
        ((0, 1), (2,)),
    ], ids=["single-filter", "or-only", "and-only", "and-or"])
    def test_converts_and_or_groups_to_payload(self, make_pre_process_rule_manager, conditions, condition_groups):
        filters = {"and": [{"or": [conditions[index] for index in group]} for group in condition_groups]}
        original = deepcopy(filters)
        manager = make_pre_process_rule_manager(filters=filters)

        expected = [
            {
                "operator": condition["operator"],
                "left": {"value": {"simple": "sourceBrand"}, "isContext": True},
                "right": {"value": {"simple": condition["right"]["value"]}, "isContext": False},
                "type": "sourceBrand",
            }
            for condition in conditions
        ]
        expected_groups = [[expected[index] for index in group] for group in condition_groups]
        payload = manager.build_rule_data()
        assert payload["newEventFilters"] == expected_groups
        assert payload["readyNewEventFilters"] == expected_groups
        assert filters == original

    def test_build_filters_does_not_fetch_metadata(self, make_pre_process_rule_manager, conditions, operator_metadata):
        manager = make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})
        operator_metadata.reset_mock()

        assert manager.build_filters() == manager.rule_filters
        operator_metadata.assert_not_called()

    def test_validate_filters_does_not_mutate_input(self, make_pre_process_rule_manager, conditions, operator_metadata):
        manager = make_pre_process_rule_manager()
        manager.filters = {"and": [{"or": conditions}]}
        original = deepcopy(manager.filters)

        assert manager.validate_filters() is None

        assert manager.filters == original
        assert manager.rule_filters == []
        operator_metadata.assert_called_once()
        manager.module.log.assert_not_called()

    def test_validate_filters_rejects_invalid_input_independently(self, make_pre_process_rule_manager, conditions):
        manager = make_pre_process_rule_manager()
        conditions[0]["operator"] = "unknown"
        manager.filters = {"and": [{"or": conditions}]}

        with pytest.raises(AnsibleModuleFail, match="unknown operator 'unknown'"):
            manager.validate_filters()
        manager.module.log.assert_not_called()
        manager.module.fail_json.assert_called_once_with(
            msg="filters.and[0].or[0].operator: unknown operator 'unknown'."
        )

    @pytest.mark.parametrize("filters", [None, {"and": []}])
    def test_empty_filters_validate_without_metadata(self, make_pre_process_rule_manager, operator_metadata, filters):
        manager = make_pre_process_rule_manager(filters=filters)

        if filters is not None:
            assert manager.validate_filters() is None
            assert manager.build_filters() == []
        assert manager.rule_filters == []
        operator_metadata.assert_not_called()
        manager.module.log.assert_not_called()

    @pytest.mark.parametrize("failure", ["empty_group", "missing_metadata", "missing_right", "unary_right"])
    def test_validation_terminates_for_each_failure(self, make_pre_process_rule_manager, conditions, operator_metadata, failure):
        manager = make_pre_process_rule_manager()
        manager.filters = {"and": [{"or": conditions}]}
        if failure == "empty_group":
            manager.filters["and"][0]["or"] = []
        elif failure == "missing_metadata":
            operator_metadata.return_value = {}
        elif failure == "missing_right":
            del conditions[0]["right"]
        else:
            conditions[0]["operator"] = "isTrue"

        with pytest.raises(AnsibleModuleFail) as error:
            manager.validate_filters()
        manager.module.log.assert_not_called()
        manager.module.fail_json.assert_called_once_with(msg=error.value.kwargs["msg"])

    def test_invalid_filters_stop_before_building(self, make_pre_process_rule_manager, conditions):
        conditions[0]["operator"] = "unknown"
        with patch.object(XSOARPreProcessRuleManager, "build_filters") as build:
            with pytest.raises(AnsibleModuleFail, match="unknown operator"):
                make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})
            build.assert_not_called()

    @pytest.mark.parametrize("right", [None, {}, {"value": None}])
    @pytest.mark.parametrize("operator", ["isTrue", "isFalse", "isEmpty", "isNotEmpty"])
    def test_unary_operator_allows_empty_right(self, make_pre_process_rule_manager, operator, right):
        condition = {"operator": operator, "left": {"value": "testing"}, "type": "testing"}
        if right is not None:
            condition["right"] = right
        manager = make_pre_process_rule_manager(filters={"and": [{"or": [condition]}]})

        assert manager.rule_filters == [[{
            "operator": operator,
            "left": {"value": {"simple": "testing"}, "isContext": True},
            "right": {},
            "type": "testing",
        }]]

    @pytest.mark.parametrize("right", [None, {}, {"value": None}, {"value": ""}])
    def test_binary_operator_requires_right_value(self, make_pre_process_rule_manager, conditions, right):
        conditions[0]["right"] = right
        with pytest.raises(AnsibleModuleFail, match=r"filters.and\[0\].or\[0\].right.value is required"):
            make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})

    @pytest.mark.parametrize("operator", ["isTrue", "isFalse", "isEmpty", "isNotEmpty"])
    def test_unary_operator_rejects_right_value(self, make_pre_process_rule_manager, operator):
        condition = {"operator": operator, "left": {"value": "testing"}, "right": {"value": "true"}, "type": "testing"}
        with pytest.raises(AnsibleModuleFail, match="requires an empty operand"):
            make_pre_process_rule_manager(filters={"and": [{"or": [condition]}]})

    def test_rejects_unknown_operator(self, make_pre_process_rule_manager, conditions):
        conditions[0]["operator"] = "unknown"
        with pytest.raises(AnsibleModuleFail, match="unknown operator 'unknown'"):
            make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})

    @pytest.mark.parametrize("metadata", [
        {}, [], {"isNotEqualString": "string"},
    ])
    def test_rejects_unavailable_or_invalid_metadata(self, make_pre_process_rule_manager, conditions, operator_metadata, metadata):
        operator_metadata.return_value = metadata
        with pytest.raises(AnsibleModuleFail, match="metadata"):
            make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})

    def test_update_uses_converted_filters(self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions, operator_metadata):
        manager = make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})

        payload = manager.build_rule_data(api_pre_process_rule_response)
        assert payload["newEventFilters"] == manager.rule_filters
        assert payload["readyNewEventFilters"] == manager.rule_filters
        assert dict(manager.fields_to_compare)["newEventFilters"] == manager.rule_filters
        assert api_pre_process_rule_response["newEventFilters"] == []
        operator_metadata.assert_called_once()

    def test_update_preserves_omitted_filters(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions
    ):
        manager = make_pre_process_rule_manager()
        api_pre_process_rule_response["newEventFilters"] = [conditions]
        api_pre_process_rule_response["readyNewEventFilters"] = [conditions]

        payload = manager.build_rule_data(api_pre_process_rule_response)
        assert payload["newEventFilters"] == [conditions]
        assert payload["readyNewEventFilters"] == [conditions]
        assert "newEventFilters" not in dict(manager.fields_to_compare)

    def test_explicit_empty_and_clears_filters(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions
    ):
        manager = make_pre_process_rule_manager(filters={"and": []})
        api_pre_process_rule_response["newEventFilters"] = [conditions]
        api_pre_process_rule_response["readyNewEventFilters"] = [conditions]

        payload = manager.build_rule_data(api_pre_process_rule_response)
        assert payload["newEventFilters"] == []
        assert payload["readyNewEventFilters"] == []
        assert api_pre_process_rule_response["newEventFilters"] == [conditions]
        assert api_pre_process_rule_response["readyNewEventFilters"] == [conditions]
        assert dict(manager.fields_to_compare)["newEventFilters"] == []

    def test_clearing_filters_is_idempotent(self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions):
        manager = make_pre_process_rule_manager(filters={"and": []})
        api_pre_process_rule_response["newEventFilters"] = [conditions]
        api_pre_process_rule_response["readyNewEventFilters"] = [conditions]

        def request(method, endpoint, data=None):
            if method == "POST":
                api_pre_process_rule_response.update(data)
            return [api_pre_process_rule_response]

        manager.connection.request.side_effect = request

        assert ensure_present(manager.module, manager)["changed"] is True
        assert api_pre_process_rule_response["newEventFilters"] == []
        assert api_pre_process_rule_response["readyNewEventFilters"] == []
        assert ensure_present(manager.module, manager)["changed"] is False

    @pytest.mark.parametrize("has_existing_filters", [False, True])
    def test_clearing_filters_in_check_mode(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions, operator_metadata,
        has_existing_filters,
    ):
        manager = make_pre_process_rule_manager(filters={"and": []})
        manager.module.check_mode = True
        existing_filters = [conditions] if has_existing_filters else []
        api_pre_process_rule_response["newEventFilters"] = existing_filters
        api_pre_process_rule_response["readyNewEventFilters"] = existing_filters
        original = deepcopy(api_pre_process_rule_response)
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = ensure_present(manager.module, manager)

        assert result["changed"] is has_existing_filters
        assert result["pre_process_rule"] == original
        assert api_pre_process_rule_response == original
        manager.connection.request.assert_called_once_with("GET", "/xsoar/preprocess/rules")
        operator_metadata.assert_not_called()

    @pytest.mark.parametrize("group_index, condition_index", [(0, 1), (1, 0), (1, 1)])
    @pytest.mark.parametrize("invalid_field", ["operator", "right", "unary_right"])
    def test_rejects_errors_in_later_conditions(
        self, make_pre_process_rule_manager, conditions, mock_module, group_index, condition_index, invalid_field,
    ):
        filters = {"and": [{"or": deepcopy(conditions[:2])}, {"or": deepcopy(conditions[1:])}]}
        invalid_condition = filters["and"][group_index]["or"][condition_index]
        if invalid_field == "operator":
            invalid_condition["operator"] = "unknown"
        elif invalid_field == "right":
            del invalid_condition["right"]
        else:
            invalid_condition["operator"] = "isTrue"
        error_path = rf"filters\.and\[{group_index}\]\.or\[{condition_index}\]"

        with patch.object(XSOARPreProcessRuleManager, "build_filters") as build:
            with pytest.raises(AnsibleModuleFail, match=error_path):
                make_pre_process_rule_manager(filters=filters)
            build.assert_not_called()
        mock_module.fail_json.assert_called_once()

    def test_rejects_empty_or_group(self, make_pre_process_rule_manager):
        with pytest.raises(AnsibleModuleFail, match="at least one condition"):
            make_pre_process_rule_manager(filters={"and": [{"or": []}]})

    @pytest.mark.parametrize("check_mode", [False, True])
    @pytest.mark.parametrize("new_filters_match", [False, True])
    @pytest.mark.parametrize("ready_filters_match", [False, True])
    def test_ensure_present_compares_filters(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, conditions, check_mode,
        new_filters_match, ready_filters_match,
    ):
        manager = make_pre_process_rule_manager(filters={"and": [{"or": conditions}]})
        manager.module.check_mode = check_mode
        api_pre_process_rule_response["newEventFilters"] = manager.rule_filters if new_filters_match else []
        api_pre_process_rule_response["readyNewEventFilters"] = manager.rule_filters if ready_filters_match else []
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = ensure_present(manager.module, manager)

        filters_match = new_filters_match and ready_filters_match
        assert result["changed"] is (not filters_match)
        post_calls = [call for call in manager.connection.request.call_args_list if call.args[0] == "POST"]
        assert len(post_calls) == (0 if filters_match or check_mode else 1)
        if post_calls:
            assert post_calls[0].kwargs["data"]["newEventFilters"] == manager.rule_filters
            assert post_calls[0].kwargs["data"]["readyNewEventFilters"] == manager.rule_filters


# ===========================================================================
# main argument validation
# ===========================================================================


class TestFilterArguments:
    @pytest.mark.parametrize("operator", ["isEqualString", "isTrue", "isEmpty", "isNotEmpty"])
    @pytest.mark.parametrize("missing_field", [None, "and", "or", "operator", "left", "left.value", "right", "type"])
    def test_ansible_validates_nested_conditions(self, provider_params, mock_connection, missing_field, operator):
        condition = {
            "operator": operator,
            "left": {"value": "sourceBrand"},
            "right": {"value": "Microsoft Graph"} if operator == "isEqualString" else {},
            "type": "sourceBrand",
        }
        if missing_field == "left.value":
            del condition["left"]["value"]
        elif missing_field not in (None, "and", "or"):
            del condition[missing_field]
        filter_group = {} if missing_field == "or" else {"or": [condition]}
        params = {
            "provider": provider_params,
            "name": "test-rule",
            "action": "drop",
            "filters": {} if missing_field == "and" else {"and": [filter_group]},
            "_ansible_check_mode": True,
        }

        def connect(module):
            mock_connection.module = module
            mock_connection.request.side_effect = lambda method, endpoint: {
                "isEqualString": {"type": "string", "isSingleValue": False},
                "isTrue": {"type": "boolean", "isSingleValue": True},
                "isEmpty": {"type": "general", "isSingleValue": True},
                "isNotEmpty": {"type": "general", "isSingleValue": True},
            } if endpoint == "/xsoar/preprocess/filters" else []
            return mock_connection

        with (
            patch("ansible.module_utils.basic._load_params", return_value=params),
            patch(
                "ansible.module_utils.basic.AnsibleModule.exit_json",
                side_effect=lambda **kwargs: (_ for _ in ()).throw(AnsibleModuleExit(**kwargs)),
            ),
            patch(
                "ansible.module_utils.basic.AnsibleModule.fail_json",
                side_effect=lambda **kwargs: (_ for _ in ()).throw(AnsibleModuleFail(**kwargs)),
            ),
            patch("plugins.modules.pre_process_rule.get_connection", side_effect=connect) as get_connection,
        ):
            if missing_field and not (missing_field == "right" and operator != "isEqualString"):
                missing_argument = missing_field.split(".")[-1]
                with pytest.raises(AnsibleModuleFail, match=missing_argument):
                    main()
                if missing_field == "right":
                    get_connection.assert_called_once()
                else:
                    get_connection.assert_not_called()
            else:
                with pytest.raises(AnsibleModuleExit) as result:
                    main()
                right = {"value": {"simple": "Microsoft Graph"}, "isContext": False} if operator == "isEqualString" else {}
                assert result.value.kwargs["pre_process_rule"]["newEventFilters"] == [[{
                    "operator": operator,
                    "left": {"value": {"simple": "sourceBrand"}, "isContext": True},
                    "right": right,
                    "type": "sourceBrand",
                }]]
                assert result.value.kwargs["changed"] is True

# ===========================================================================
# XSOARPreProcessRuleManager.get_pre_process_rules
# ===========================================================================


class TestGetPreProcessRules:
    def test_returns_rules_from_api(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        A list response from the API must be returned as-is.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = manager.get_pre_process_rules()

        assert result == [api_pre_process_rule_response]
        manager.connection.request.assert_called_once_with("GET", "/xsoar/preprocess/rules")

    def test_returns_empty_list_when_response_is_not_list(self, make_pre_process_rule_manager):
        """
        Non-list responses (e.g. ``{}`` on an empty result) must be normalised to ``[]``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = {}

        assert manager.get_pre_process_rules() == []

    def test_raises_on_request_failure(self, make_pre_process_rule_manager):
        """
        Any exception from the connection must be re-raised as :class:`XSOARAPIError`.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("network error")

        with pytest.raises(XSOARAPIError, match="Failed to get available pre-process rules"):
            manager.get_pre_process_rules()


# ===========================================================================
# XSOARPreProcessRuleManager.get_pre_process_rule_by_name
# ===========================================================================


class TestGetPreProcessRuleByName:
    def test_returns_matching_rule(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager()
        other = {"id": "other-id", "name": "other-rule"}
        manager.connection.request.return_value = [other, api_pre_process_rule_response]

        result = manager.get_pre_process_rule_by_name("test-rule")

        assert result == api_pre_process_rule_response

    def test_returns_none_when_not_found(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [{"id": "x", "name": "other-rule"}]

        assert manager.get_pre_process_rule_by_name("test-rule") is None

    def test_returns_none_on_empty_response(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = []

        assert manager.get_pre_process_rule_by_name("test-rule") is None


# ===========================================================================
# XSOARPreProcessRuleManager.build_rule_data
# ===========================================================================


class TestBuildRuleData:
    def test_create_payload_contains_required_fields(self, make_pre_process_rule_manager):
        """
        ``build_rule_data()`` with no arguments produces a create payload with
        all fields derived from module params and module-level defaults.
        """
        manager = make_pre_process_rule_manager()

        payload = manager.build_rule_data()

        assert payload["name"] == "test-rule"
        assert payload["action"] == "link"
        assert payload["enabled"]
        assert payload["propagationLabels"] == []
        assert payload["scriptID"] is None
        assert payload["shouldPublish"]
        assert payload["shouldCommit"]
        assert payload["commitMessage"] == "Preprocess rule edited"
        assert payload["newEventFilters"] == []
        assert payload["readyNewEventFilters"] == []

    def test_update_payload(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        Verify the core structure of the update payload built from ``raw_rule_data``:

        - ``version`` is forced to ``-1`` to bypass XSOAR optimistic locking.
        - The existing ``id`` is preserved.
        - ``action``, ``enabled``, ``propagationLabels``, and ``scriptID`` are
          overridden from module params.
        """
        manager = make_pre_process_rule_manager(action="drop", propagation_labels=["all"])
        payload = manager.build_rule_data(raw_rule_data=api_pre_process_rule_response)

        assert payload["version"] == -1
        assert payload["id"] == "rule-abc123"
        assert payload["action"] == "drop"
        assert payload["propagationLabels"] == ["all"]
        assert payload["enabled"]

    def test_update_payload_does_not_mutate_input(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        """
        ``build_rule_data`` must not mutate the ``raw_rule_data`` dict that was
        passed in — the caller still needs the original.
        """
        manager = make_pre_process_rule_manager()
        original_version = api_pre_process_rule_response["version"]

        new_rule_data = manager.build_rule_data(raw_rule_data=api_pre_process_rule_response)

        assert api_pre_process_rule_response["version"] == original_version
        assert new_rule_data["version"] == -1


# ===========================================================================
# XSOARPreProcessRuleManager.create_pre_process_rule
# ===========================================================================


class TestCreatePreProcessRule:
    def test_posts_to_correct_endpoint_and_returns_matching_rule(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        rule_data = manager.build_rule_data()
        result = manager.create_pre_process_rule(rule_data)

        assert result == api_pre_process_rule_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/preprocess/rule"

    def test_returns_none_when_rule_not_in_response_list(self, make_pre_process_rule_manager):
        """
        When the API response list does not contain a rule matching ``self.name``,
        ``create_pre_process_rule`` must return ``None``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [{"id": "other-id", "name": "other-rule"}]

        result = manager.create_pre_process_rule(manager.build_rule_data())

        assert result is None

    def test_raises_on_request_failure(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to create pre-process rule"):
            manager.create_pre_process_rule(manager.build_rule_data())


# ===========================================================================
# XSOARPreProcessRuleManager.update_pre_process_rule
# ===========================================================================


class TestUpdatePreProcessRule:
    def test_posts_to_correct_endpoint_and_returns_matching_rule(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        result = manager.update_pre_process_rule(api_pre_process_rule_response)

        assert result == api_pre_process_rule_response
        args, _ = manager.connection.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/xsoar/preprocess/rule"

    def test_posts_built_payload_with_version_minus_one(
        self, make_pre_process_rule_manager, api_pre_process_rule_response
    ):
        """
        The payload sent to the API must carry ``version: -1`` and preserve
        the existing rule ``id``.
        """
        manager = make_pre_process_rule_manager()
        manager.connection.request.return_value = [api_pre_process_rule_response]

        manager.update_pre_process_rule(api_pre_process_rule_response)

        payload = manager.connection.request.call_args.kwargs["data"]
        assert payload["version"] == -1
        assert payload["id"] == "rule-abc123"

    def test_raises_on_request_failure(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager()
        manager.connection.request.side_effect = XSOARAPIError("timeout")

        with pytest.raises(XSOARAPIError, match="Failed to update pre-process rule"):
            manager.update_pre_process_rule(api_pre_process_rule_response)


# ===========================================================================
# XSOARPreProcessRuleManager.delete_pre_process_rule
# ===========================================================================


class TestDeletePreProcessRule:
    def test_sends_delete_to_correct_endpoint(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="absent")
        manager.connection.request.return_value = {}

        manager.delete_pre_process_rule("rule-abc123")

        manager.connection.request.assert_called_once_with(
            "DELETE",
            "/xsoar/preprocess/rule/rule-abc123",
        )

    def test_calls_fail_json_on_request_failure(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="absent")
        manager.connection.request.side_effect = XSOARAPIError("forbidden")

        with pytest.raises(AnsibleModuleFail, match="Failed to delete Pre-Process Rule rule-abc123"):
            manager.delete_pre_process_rule("rule-abc123")


# ===========================================================================
# ensure_present
# ===========================================================================


class TestEnsurePresent:
    def test_creates_rule_when_absent(self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module):
        manager = make_pre_process_rule_manager()

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=None),
            patch.object(manager, "create_pre_process_rule", return_value=api_pre_process_rule_response) as mock_create,
        ):
            result = ensure_present(mock_module, manager)

        mock_create.assert_called_once()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} created successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_updates_rule_when_action_differs(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        stale = {**api_pre_process_rule_response, "action": "drop"}

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=stale),
            patch.object(manager, "update_pre_process_rule", return_value=api_pre_process_rule_response) as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_called_once_with(current_rule_data=stale)
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} updated successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_no_change_when_rule_is_up_to_date(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        """
        ``api_pre_process_rule_response`` matches ``pre_process_rule_params``
        defaults — no update expected.
        """
        manager = make_pre_process_rule_manager()

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "update_pre_process_rule") as mock_update,
        ):
            result = ensure_present(mock_module, manager)

        mock_update.assert_not_called()
        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule {api_pre_process_rule_response['name']} is already up to date"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_check_mode_reports_create_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=None),
            patch.object(manager, "create_pre_process_rule") as mock_create,
        ):
            result = ensure_present(module, manager)

        mock_create.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} would be created"

    def test_check_mode_reports_update_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)
        stale = {**api_pre_process_rule_response, "action": "drop"}

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=stale),
            patch.object(manager, "update_pre_process_rule") as mock_update,
        ):
            result = ensure_present(module, manager)

        mock_update.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} would be updated"

    def test_check_mode_no_change_when_up_to_date(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager()
        module = mock_module(check_mode=True)

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response):
            result = ensure_present(module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule {manager.name} is already up to date (check mode)"


# ===========================================================================
# ensure_absent
# ===========================================================================


class TestEnsureAbsent:
    def test_deletes_existing_rule(self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module):
        manager = make_pre_process_rule_manager(state="absent")

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "delete_pre_process_rule") as mock_delete,
        ):
            result = ensure_absent(mock_module, manager)

        mock_delete.assert_called_once_with(api_pre_process_rule_response["id"])
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {api_pre_process_rule_response['name']} deleted successfully"
        assert result["pre_process_rule"] == api_pre_process_rule_response

    def test_no_change_when_rule_already_absent(self, make_pre_process_rule_manager, mock_module):
        manager = make_pre_process_rule_manager(state="absent")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=None):
            result = ensure_absent(mock_module, manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {manager.name} does not exist"
        assert "pre_process_rule" not in result

    def test_check_mode_reports_delete_without_calling_api(
        self, make_pre_process_rule_manager, api_pre_process_rule_response, mock_module
    ):
        manager = make_pre_process_rule_manager(state="absent")
        module = mock_module(check_mode=True)

        with (
            patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response),
            patch.object(manager, "delete_pre_process_rule") as mock_delete,
        ):
            result = ensure_absent(module, manager)

        mock_delete.assert_not_called()
        assert result["changed"]
        assert result["msg"] == f"Pre-Process Rule: {manager.name} would be deleted"


# ===========================================================================
# gather_pre_process_rules
# ===========================================================================


class TestGatherPreProcessRules:
    def test_returns_named_rule_when_found(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager(state="gathered")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=api_pre_process_rule_response):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["pre_process_rule"] == api_pre_process_rule_response
        assert result["msg"] == f"Pre-Process Rule '{manager.name}' retrieved successfully."

    def test_reports_not_found_for_missing_named_rule(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(state="gathered")

        with patch.object(manager, "get_pre_process_rule_by_name", return_value=None):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["msg"] == f"Pre-Process Rule '{manager.name}' not found."
        assert "pre_process_rule" not in result

    def test_returns_all_rules_when_name_is_none(self, make_pre_process_rule_manager, api_pre_process_rule_response):
        manager = make_pre_process_rule_manager(name=None, state="gathered")

        with patch.object(manager, "get_pre_process_rules", return_value=[api_pre_process_rule_response]) as mock_get:
            result = gather_pre_process_rules(manager)

        mock_get.assert_called_once_with()
        assert not result["changed"]
        assert result["pre_process_rules"] == [api_pre_process_rule_response]
        assert result["msg"] == "Retrieved 1 pre-process rules."

    def test_reports_no_rules_found_when_empty(self, make_pre_process_rule_manager):
        manager = make_pre_process_rule_manager(name=None, state="gathered")

        with patch.object(manager, "get_pre_process_rules", return_value=[]):
            result = gather_pre_process_rules(manager)

        assert not result["changed"]
        assert result["msg"] == "No pre-process rules found."
        assert "pre_process_rules" not in result
