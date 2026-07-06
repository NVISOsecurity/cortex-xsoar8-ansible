#!/usr/bin/python

# Copyright: (c) 2026, NVISO (@NVISOSecurity)
# Apache License v2.0 (see LICENSE file)


import hashlib
import secrets
import string
from datetime import UTC, datetime
from urllib.parse import urljoin

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from ansible.module_utils.common.text.converters import to_text


class XSOARError(Exception):
    """Base exception for XSOAR API errors."""

    pass


class XSOARAuthError(XSOARError):
    """Authentication error for XSOAR API."""

    pass


class XSOARAPIError(XSOARError):
    """API error for XSOAR API operations."""

    pass


class XSOARConnection:
    """
    Base class for XSOAR 8 SaaS API connections and common operations.
    """

    def __init__(self, module):
        """
        Initialize XSOAR connection.

        Args:
            module: AnsibleModule instance
        """
        self.module = module
        self.server = None
        self.api_key = None
        self.api_key_id = None
        self.security_level = "standard"
        self.verify_ssl = True
        self.timeout = 30
        self.session = None

        self._validate_requirements()
        self._parse_provider()
        self._setup_session()

    def _validate_requirements(self):
        """Validate that required libraries are available."""
        if not HAS_REQUESTS:
            self.module.fail_json(msg="The 'requests' library is required for this module")

    def _parse_provider(self):
        """Parse provider configuration from module parameters."""
        provider = self.module.params.get("provider", {})

        # Required parameters
        self.server = provider.get("server") or self.module.params.get("server")
        if not self.server:
            self.module.fail_json(msg="Server URL is required")

        # Ensure server URL has proper format
        if not self.server.startswith(("http://", "https://")):
            self.server = f"https://{self.server}"

        # Authentication parameters - both required for XSOAR 8 SaaS
        self.api_key = provider.get("api_key") or self.module.params.get("api_key")
        self.api_key_id = provider.get("api_key_id") or self.module.params.get("api_key_id")

        # Validate authentication method
        if not self.api_key or not self.api_key_id:
            self.module.fail_json(msg="Both api_key and api_key_id are required for authentication")

        # Security level - 'standard' or 'advanced'
        self.security_level = provider.get("security_level") or self.module.params.get("security_level") or "standard"
        if self.security_level not in ["standard", "advanced"]:
            self.module.fail_json(msg="security_level must be either 'standard' or 'advanced'")

        # Optional parameters
        self.verify_ssl = provider.get("verify_ssl", self.module.params.get("verify_ssl", True))
        if isinstance(self.verify_ssl, str):
            self.verify_ssl = self.verify_ssl.lower() in ("true", "yes", "1")

        self.timeout = provider.get("timeout", self.module.params.get("timeout", 30))

    def _setup_session(self):
        """Set up HTTP session with retry strategy."""
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set common headers
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Ansible-XSOAR-SaaS/1.0.0"}
        )

        # Configure SSL verification
        self.session.verify = self.verify_ssl

    def _authenticate_standard(self):
        """Standard API key authentication for XSOAR 8 SaaS."""
        self.session.headers.update({"x-xdr-auth-id": str(self.api_key_id), "Authorization": self.api_key})

    def _authenticate_advanced(self):
        """Advanced API key authentication with nonce and timestamp."""
        nonce = "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(64)])
        timestamp = int(datetime.now(UTC).timestamp() * 1000)
        auth_string = f"{self.api_key}{nonce}{timestamp}"
        auth_hash = hashlib.sha256(auth_string.encode("utf-8")).hexdigest()

        self.session.headers.update(
            {
                "x-xdr-timestamp": str(timestamp),
                "x-xdr-nonce": nonce,
                "x-xdr-auth-id": str(self.api_key_id),
                "Authorization": auth_hash,
            }
        )

    def _authenticate(self):
        """Authenticate with XSOAR instance based on security level."""
        if self.security_level == "advanced":
            self._authenticate_advanced()
        else:
            self._authenticate_standard()

    def request(self, method, endpoint, data=None, params=None):
        """
        Make HTTP request to XSOAR API.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint path
            data (dict): Request body data
            params (dict): Query parameters

        Returns:
            dict: Response data

        Raises:
            XSOARAPIError: On API errors
        """
        self._authenticate()

        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        # The "/xsoar/" prefix is intentionally broad so modules can target
        # non-/public/v1 paths (for example /xsoar/system/config or /xsoar/preprocess/rule)
        # without the auto-prefix logic rewriting them.
        if not endpoint.startswith(("/xsoar/public/v1/", "/public_api/v1/", "/xsoar/")):
            endpoint = f"/xsoar/public/v1{endpoint}"

        url = urljoin(self.server, endpoint)

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=self.timeout)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, params=params, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, params=params, timeout=self.timeout)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=self.timeout)
            else:
                raise XSOARAPIError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise XSOARAuthError(
                    f"Authentication failed or token expired (security_level={self.security_level}, "
                    f"auth_id={self.api_key_id}, endpoint={endpoint})"
                )
            elif response.status_code == 403:
                raise XSOARAPIError("Insufficient permissions for this operation")
            elif response.status_code == 404:
                raise XSOARAPIError("Resource not found")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = None

                if isinstance(error_data, dict):
                    reply = error_data.get("reply")
                    if isinstance(reply, dict):
                        err_msg = reply.get("err_msg")
                        err_extra = reply.get("err_extra")
                    else:
                        err_msg = None
                        err_extra = None
                    err_msg = err_msg or error_data.get("message") or error_data.get("error") or "Unknown error"
                    details = f"{err_msg}: {err_extra}" if err_extra else err_msg
                    error_msg = f"HTTP {response.status_code}: {details}"
                elif error_data is not None:
                    error_msg = f"HTTP {response.status_code}: {error_data}"
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                raise XSOARAPIError(error_msg) from None

            if response.content:
                try:
                    return response.json()
                except ValueError as e:
                    raise XSOARAPIError(f"Invalid JSON response: {to_text(e)}") from e
            else:
                return {}

        except requests.exceptions.Timeout:
            raise XSOARAPIError("Request timeout") from None
        except requests.exceptions.ConnectionError as e:
            raise XSOARAPIError(f"Connection error: {to_text(e)}") from e
        except requests.exceptions.RequestException as e:
            raise XSOARAPIError(f"Request failed: {to_text(e)}") from e

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()


def get_connection(module):
    """
    Get XSOAR connection instance.

    Args:
        module: AnsibleModule instance

    Returns:
        XSOARConnection: Connection instance
    """
    return XSOARConnection(module)


def xsoar_argument_spec():
    """
    Return common argument spec for XSOAR modules.

    Returns:
        dict: Argument specification
    """
    # Defaults live only on the top-level parameters so precedence is well-defined:
    # provider.<key> wins when explicitly set; otherwise the top-level value (which
    # carries the default) is used. Defaulting both layers makes it impossible to
    # tell whether the user opted in.
    return dict(
        provider=dict(
            type="dict",
            options=dict(
                api_key=dict(type="str", no_log=True),
                api_key_id=dict(type="str"),
                security_level=dict(type="str", choices=["standard", "advanced"]),
                server=dict(type="str"),
                timeout=dict(type="int"),
                verify_ssl=dict(type="bool"),
            ),
        ),
        # Legacy support for top-level parameters
        api_key=dict(type="str", no_log=True),
        api_key_id=dict(type="str"),
        security_level=dict(type="str", choices=["standard", "advanced"], default="standard"),
        server=dict(type="str"),
        timeout=dict(type="int", default=30),
        verify_ssl=dict(type="bool", default=True),
    )
