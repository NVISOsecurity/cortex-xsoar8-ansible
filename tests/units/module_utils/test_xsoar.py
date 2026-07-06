"""
Unit tests for plugins/module_utils/xsoar.py — XSOARConnection.

Fixtures are auto-discovered from conftest.py in this package.
Global fixtures (mock_module, provider_params) come from tests/conftest.py
and are resolved automatically by pytest.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests as real_requests

from plugins.module_utils.xsoar import XSOARAPIError, XSOARAuthError, XSOARConnection
from tests.conftest import AnsibleModuleFail

# ===========================================================================
# Helpers
# ===========================================================================


def _make_module(**provider_overrides):
    """MagicMock AnsibleModule with default provider params; override fields via kwargs."""
    provider = {
        "server": "https://api-test.xdr.paloaltonetworks.com",
        "api_key": "test-api-key-value",
        "api_key_id": "42",
        "security_level": "standard",
        "verify_ssl": True,
        "timeout": 30,
    }
    provider.update(provider_overrides)
    module = MagicMock()
    module.params = {"provider": provider}
    module.fail_json.side_effect = lambda **kw: (_ for _ in ()).throw(AnsibleModuleFail(**kw))
    return module


def _make_response(status_code=200, json_data=None, text="", has_content=True):
    """Minimal mock HTTP response.  Pass ``has_content=False`` to simulate an empty body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = b"..." if has_content else b""
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


# ===========================================================================
# XSOARConnection._parse_provider
# ===========================================================================


class TestParseProvider:
    def test_provider_params_stored_on_connection(self, xsoar_connection):
        assert xsoar_connection.server == "https://api-test.xdr.paloaltonetworks.com"
        assert xsoar_connection.api_key == "test-api-key-value"
        assert xsoar_connection.api_key_id == "42"
        assert xsoar_connection.timeout == 30

    def test_https_prepended_when_scheme_missing(self):
        module = _make_module(server="api-test.xdr.paloaltonetworks.com")
        with patch("plugins.module_utils.xsoar.requests.Session"):
            conn = XSOARConnection(module)
        assert conn.server == "https://api-test.xdr.paloaltonetworks.com"

    def test_fails_when_server_missing(self):
        module = _make_module(server=None)
        with patch("plugins.module_utils.xsoar.requests.Session"):
            with pytest.raises(AnsibleModuleFail, match="Server URL is required"):
                XSOARConnection(module)

    def test_fails_when_api_key_missing(self):
        module = _make_module(api_key=None)
        with patch("plugins.module_utils.xsoar.requests.Session"):
            with pytest.raises(AnsibleModuleFail, match="api_key"):
                XSOARConnection(module)

    def test_fails_when_api_key_id_missing(self):
        module = _make_module(api_key_id=None)
        with patch("plugins.module_utils.xsoar.requests.Session"):
            with pytest.raises(AnsibleModuleFail, match="api_key"):
                XSOARConnection(module)

    def test_fails_when_security_level_invalid(self):
        module = _make_module(security_level="invalid")
        with patch("plugins.module_utils.xsoar.requests.Session"):
            with pytest.raises(AnsibleModuleFail, match="security_level"):
                XSOARConnection(module)

    def test_verify_ssl_string_true_coerced_to_bool(self):
        module = _make_module(verify_ssl="true")
        with patch("plugins.module_utils.xsoar.requests.Session"):
            conn = XSOARConnection(module)
        assert conn.verify_ssl is True

    def test_verify_ssl_string_false_coerced_to_bool(self):
        module = _make_module(verify_ssl="false")
        with patch("plugins.module_utils.xsoar.requests.Session"):
            conn = XSOARConnection(module)
        assert conn.verify_ssl is False


# ===========================================================================
# XSOARConnection._authenticate
# ===========================================================================


class TestAuthenticate:
    def _latest_headers(self, xsoar_connection):
        """Return the dict passed to the most recent headers.update() call."""
        return xsoar_connection.session.headers.update.call_args[0][0]

    def test_standard_sets_auth_id_header(self, xsoar_connection):
        xsoar_connection._authenticate_standard()
        headers = self._latest_headers(xsoar_connection)
        assert headers.get("x-xdr-auth-id") == "42"
        assert headers.get("Authorization") == "test-api-key-value"

    def test_advanced_sets_required_headers(self, xsoar_connection):
        fixed_now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
        expected_ts = str(int(fixed_now.timestamp() * 1000))

        with (
            patch("plugins.module_utils.xsoar.secrets.choice", return_value="test_secret"),
            patch("plugins.module_utils.xsoar.datetime") as mock_dt,
        ):
            mock_dt.now.return_value = fixed_now
            xsoar_connection._authenticate_advanced()

        headers = self._latest_headers(xsoar_connection)
        assert headers["x-xdr-auth-id"] == "42"
        assert headers["Authorization"] == "7e19a8c6c5136aeb3a6cd7ae184e0a470b94a9371e1c6013a97588e051477485"
        assert headers["x-xdr-nonce"] == "test_secret" * 64
        assert headers["x-xdr-timestamp"] == expected_ts


# ===========================================================================
# XSOARConnection.request
# ===========================================================================


class TestRequest:
    def test_get_dispatched_to_session_get(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(json_data={"ok": True})
        result = xsoar_connection.request("GET", "/test")
        xsoar_connection.session.get.assert_called_once()
        assert result == {"ok": True}

    def test_post_dispatched_with_json_body(self, xsoar_connection):
        xsoar_connection.session.post.return_value = _make_response(json_data={"id": "1"})
        result = xsoar_connection.request("POST", "/test", data={"key": "val"})
        xsoar_connection.session.post.assert_called_once()
        assert result == {"id": "1"}

    def test_put_dispatched_to_session_put(self, xsoar_connection):
        xsoar_connection.session.put.return_value = _make_response(json_data={})
        xsoar_connection.request("PUT", "/test", data={})
        xsoar_connection.session.put.assert_called_once()

    def test_delete_dispatched_to_session_delete(self, xsoar_connection):
        xsoar_connection.session.delete.return_value = _make_response(json_data={})
        xsoar_connection.request("DELETE", "/test")
        xsoar_connection.session.delete.assert_called_once()

    def test_endpoint_prefix_added_for_bare_path(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(json_data={})
        xsoar_connection.request("GET", "/lists")
        url = xsoar_connection.session.get.call_args[0][0]
        assert url == "https://api-test.xdr.paloaltonetworks.com/xsoar/public/v1/lists"

    def test_endpoint_prefix_not_doubled(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(json_data={})
        xsoar_connection.request("GET", "/xsoar/public/v1/lists")
        url = xsoar_connection.session.get.call_args[0][0]
        assert url.count("/xsoar/public/v1") == 1

    def test_public_api_path_not_prefixed(self, xsoar_connection):
        """Paths starting with ``/public_api/v1/`` must not receive the XSOAR prefix."""
        xsoar_connection.session.post.return_value = _make_response(json_data={})
        xsoar_connection.request("POST", "/public_api/v1/api_keys/get_api_keys")
        url = xsoar_connection.session.post.call_args[0][0]
        assert url == "https://api-test.xdr.paloaltonetworks.com/public_api/v1/api_keys/get_api_keys"

    def test_xsoar_path_not_prefixed(self, xsoar_connection):
        """Paths already starting with ``/xsoar/`` must not receive the XSOAR prefix."""
        xsoar_connection.session.get.return_value = _make_response(json_data={})
        xsoar_connection.request("GET", "/xsoar/some/custom/path")
        url = xsoar_connection.session.get.call_args[0][0]
        assert url == "https://api-test.xdr.paloaltonetworks.com/xsoar/some/custom/path"

    def test_leading_slash_added_when_missing(self, xsoar_connection):
        """An endpoint without a leading ``/`` must have one inserted before prefix logic runs."""
        xsoar_connection.session.get.return_value = _make_response(json_data={})
        xsoar_connection.request("GET", "lists")
        url = xsoar_connection.session.get.call_args[0][0]
        assert url == "https://api-test.xdr.paloaltonetworks.com/xsoar/public/v1/lists"

    def test_empty_response_body_returns_empty_dict(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(has_content=False)
        result = xsoar_connection.request("GET", "/test")
        assert result == {}

    def test_401_raises_xsoar_auth_error(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(status_code=401)
        with pytest.raises(XSOARAuthError):
            xsoar_connection.request("GET", "/test")

    def test_403_raises_xsoar_api_error(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(status_code=403)
        with pytest.raises(XSOARAPIError, match="Insufficient permissions"):
            xsoar_connection.request("GET", "/test")

    def test_404_raises_xsoar_api_error(self, xsoar_connection):
        xsoar_connection.session.get.return_value = _make_response(status_code=404)
        with pytest.raises(XSOARAPIError, match="not found"):
            xsoar_connection.request("GET", "/test")

    def test_4xx_uses_message_field_from_json_body(self, xsoar_connection):
        resp = _make_response(status_code=422, json_data={"message": "Validation error"})
        xsoar_connection.session.get.return_value = resp
        with pytest.raises(XSOARAPIError, match="Validation error"):
            xsoar_connection.request("GET", "/test")

    def test_4xx_falls_back_to_status_code_when_json_unparseable(self, xsoar_connection):
        resp = _make_response(status_code=500, text="Internal Server Error")
        resp.json.side_effect = ValueError("no json")
        xsoar_connection.session.get.return_value = resp
        with pytest.raises(XSOARAPIError, match="500"):
            xsoar_connection.request("GET", "/test")

    def test_invalid_json_in_success_response_raises_xsoar_api_error(self, xsoar_connection):
        resp = _make_response(status_code=200)
        resp.json.side_effect = ValueError("bad json")
        xsoar_connection.session.get.return_value = resp
        with pytest.raises(XSOARAPIError, match="Invalid JSON"):
            xsoar_connection.request("GET", "/test")

    def test_request_timeout_raises_xsoar_api_error(self, xsoar_connection):
        xsoar_connection.session.get.side_effect = real_requests.exceptions.Timeout()
        with pytest.raises(XSOARAPIError, match="timeout"):
            xsoar_connection.request("GET", "/test")

    def test_connection_error_raises_xsoar_api_error(self, xsoar_connection):
        xsoar_connection.session.get.side_effect = real_requests.exceptions.ConnectionError("refused")
        with pytest.raises(XSOARAPIError, match="Connection error"):
            xsoar_connection.request("GET", "/test")

    def test_unsupported_method_raises_xsoar_api_error(self, xsoar_connection):
        with pytest.raises(XSOARAPIError, match="Unsupported HTTP method"):
            xsoar_connection.request("PATCH", "/test")

    def test_4xx_with_non_dict_reply_does_not_crash(self, xsoar_connection):
        """
        When the API returns a 4xx/5xx body whose ``reply`` key is not a dict
        (or whose top-level body itself is not a dict), the connection must
        raise :class:`XSOARAPIError` instead of an :class:`AttributeError`
        from ``reply.get(...)``.
        """
        resp = _make_response(status_code=500, json_data={"reply": "boom"})
        xsoar_connection.session.get.return_value = resp
        with pytest.raises(XSOARAPIError, match="HTTP 500"):
            xsoar_connection.request("GET", "/test")

    def test_5xx_with_non_dict_top_level_body_does_not_crash(self, xsoar_connection):
        """A non-dict JSON body (e.g. a top-level list) must not break error parsing."""
        resp = _make_response(status_code=500, json_data=[1, 2, 3])
        xsoar_connection.session.get.return_value = resp
        with pytest.raises(XSOARAPIError, match="HTTP 500"):
            xsoar_connection.request("GET", "/test")


# ===========================================================================
# XSOARConnection._parse_provider — top-level fallback
# ===========================================================================


class TestTopLevelFallback:
    def test_top_level_keys_used_when_provider_dict_absent(self):
        """
        ``xsoar_argument_spec`` documents a legacy fallback where the user may
        supply ``server``/``api_key``/``api_key_id`` at the top level instead of
        nested under ``provider``. The connection must accept that form.
        """
        module = MagicMock()
        module.params = {
            "server": "https://api-test.xdr.paloaltonetworks.com",
            "api_key": "top-level-key",
            "api_key_id": "99",
            "security_level": "standard",
            "verify_ssl": True,
            "timeout": 30,
        }
        module.fail_json.side_effect = lambda **kw: (_ for _ in ()).throw(AnsibleModuleFail(**kw))

        with patch("plugins.module_utils.xsoar.requests.Session"):
            conn = XSOARConnection(module)

        assert conn.server == "https://api-test.xdr.paloaltonetworks.com"
        assert conn.api_key == "top-level-key"
        assert conn.api_key_id == "99"

    def test_provider_dict_takes_precedence_over_top_level(self):
        """When both layers are set, the provider dict wins."""
        module = MagicMock()
        module.params = {
            "provider": {
                "server": "https://nested.example.com",
                "api_key": "nested-key",
                "api_key_id": "1",
                "security_level": "standard",
                "verify_ssl": True,
                "timeout": 30,
            },
            "server": "https://toplevel.example.com",
            "api_key": "toplevel-key",
            "api_key_id": "2",
        }
        module.fail_json.side_effect = lambda **kw: (_ for _ in ()).throw(AnsibleModuleFail(**kw))

        with patch("plugins.module_utils.xsoar.requests.Session"):
            conn = XSOARConnection(module)

        assert conn.server == "https://nested.example.com"
        assert conn.api_key == "nested-key"
        assert conn.api_key_id == "1"


# ===========================================================================
# XSOARConnection._setup_session
# ===========================================================================


class TestSetupSession:
    def test_retry_strategy_includes_429_and_5xx(self):
        """
        The retry strategy installed on the session must cover throttling (429)
        and the standard server-error class (500, 502, 503, 504), so transient
        failures are retried automatically.
        """
        module = _make_module()

        with (
            patch("plugins.module_utils.xsoar.requests.Session"),
            patch("plugins.module_utils.xsoar.HTTPAdapter"),
            patch("plugins.module_utils.xsoar.Retry") as MockRetry,
        ):
            XSOARConnection(module)

        kwargs = MockRetry.call_args.kwargs
        assert kwargs["total"] == 3
        assert kwargs["backoff_factor"] == 1
        assert set(kwargs["status_forcelist"]) >= {429, 500, 502, 503, 504}


# ===========================================================================
# XSOARConnection.close
# ===========================================================================


class TestClose:
    def test_close_calls_session_close(self, xsoar_connection):
        xsoar_connection.close()
        xsoar_connection.session.close.assert_called_once()
