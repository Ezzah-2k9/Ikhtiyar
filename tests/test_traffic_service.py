"""Unit tests for the TomTom tile proxy; provider HTTP calls are mocked."""

import json
import sys
import types
import unittest
from unittest.mock import Mock, patch


# The review snapshot contains only the files under test. Inject a test-only
# Config while importing the service, then remove it so other tests can import
# the real application configuration independently.
_missing = object()
_previous_config = sys.modules.get("config", _missing)
_previous_requests = sys.modules.get("requests", _missing)
_config_stub = types.ModuleType("config")
_requests_stubbed = False
try:
    import requests
except ModuleNotFoundError:
    requests = types.ModuleType("requests")
    _requests_stubbed = True


class _RequestException(Exception):
    pass


class _Timeout(_RequestException):
    pass


if _requests_stubbed:
    requests.RequestException = _RequestException
    requests.Timeout = _Timeout
    requests.get = Mock()


class _TestConfig:
    TOMTOM_KEY = "test-only-tomtom-secret"


_config_stub.Config = _TestConfig
sys.modules["config"] = _config_stub
sys.modules["requests"] = requests
try:
    from services.traffic_service import TrafficService
finally:
    if _previous_config is _missing:
        sys.modules.pop("config", None)
    else:
        sys.modules["config"] = _previous_config
    if _previous_requests is _missing:
        sys.modules.pop("requests", None)
    else:
        sys.modules["requests"] = _previous_requests


class FakeResponse:
    def __init__(self, status_code=200, *, content=b"\x89PNG\r\n\x1a\n", content_type="image/png", payload=None):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}
        self._payload = payload
        self.text = ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class TrafficServiceTests(unittest.TestCase):
    def setUp(self):
        _TestConfig.TOMTOM_KEY = "test-only-tomtom-secret"

    @patch("services.traffic_service.requests.get")
    def test_valid_png_tile_uses_tomtom_z_x_y_url(self, get):
        body = b"\x89PNG\r\n\x1a\nmock tile"
        get.return_value = FakeResponse(content=body)

        image, error, status, details = TrafficService.get_tile(12, 2200, 1450)

        self.assertEqual((image, error, status), (body, None, 200))
        self.assertEqual(details, {"source": "provider", "provider": "TomTom", "upstream_status": 200})
        args, kwargs = get.call_args
        self.assertEqual(args[0], f"{TrafficService.TOMTOM_BASE_URL}/12/2200/1450.png")
        self.assertEqual(kwargs["params"], {"key": "test-only-tomtom-secret", "tileSize": 256})
        self.assertEqual(kwargs["timeout"], (3, 6))

    @patch("services.traffic_service.requests.get")
    def test_provider_401_and_403_include_safe_detail_without_key(self, get):
        for upstream_status in (401, 403):
            with self.subTest(upstream_status=upstream_status):
                get.return_value = FakeResponse(
                    upstream_status,
                    content=b"",
                    content_type="application/json",
                    payload={"detailedError": {"code": "Forbidden", "message": "API key=test-only-tomtom-secret is not authorized"}},
                )

                image, error, status, details = TrafficService.get_tile(12, 2200, 1450)
                serialized = json.dumps({"error": error, **details})

                self.assertIsNone(image)
                self.assertEqual(status, upstream_status)
                self.assertEqual(details["source"], "provider")
                self.assertEqual(details["provider"], "TomTom")
                self.assertEqual(details["upstream_status"], upstream_status)
                self.assertIn("[redacted]", details["detail"])
                self.assertNotIn("test-only-tomtom-secret", serialized)

    @patch("services.traffic_service.requests.get")
    def test_quota_429_is_preserved(self, get):
        get.return_value = FakeResponse(429, content=b"", payload={"error": "Rate limit exceeded"})

        image, error, status, details = TrafficService.get_tile(12, 2200, 1450)

        self.assertIsNone(image)
        self.assertEqual(status, 429)
        self.assertEqual(details["upstream_status"], 429)
        self.assertIn("quota", error.lower())

    @patch("services.traffic_service.requests.get")
    def test_provider_5xx_is_proxy_502_with_original_upstream_status(self, get):
        get.return_value = FakeResponse(503, content=b"", payload={"error": "Service unavailable"})

        image, error, status, details = TrafficService.get_tile(12, 2200, 1450)

        self.assertIsNone(image)
        self.assertEqual(status, 502)
        self.assertEqual(details["upstream_status"], 503)
        self.assertIn("temporarily unavailable", error)

    @patch("services.traffic_service.requests.get", side_effect=requests.Timeout("provider timed out"))
    def test_timeout_is_identified_without_leaking_request_credentials(self, get):
        image, error, status, details = TrafficService.get_tile(12, 2200, 1450)

        self.assertIsNone(image)
        self.assertEqual(status, 502)
        self.assertEqual(details["code"], "UPSTREAM_TIMEOUT")
        self.assertIsNone(details["upstream_status"])
        self.assertIn("timed out", error)
        self.assertNotIn("test-only-tomtom-secret", json.dumps({"error": error, **details}))

    @patch("services.traffic_service.requests.get")
    def test_non_png_success_is_rejected(self, get):
        get.return_value = FakeResponse(content=b"html", content_type="text/html")

        image, error, status, details = TrafficService.get_tile(12, 2200, 1450)

        self.assertIsNone(image)
        self.assertEqual(status, 502)
        self.assertEqual(details["code"], "UNEXPECTED_TILE_FORMAT")
        self.assertIn("unexpected tile format", error)

    @patch("services.traffic_service.requests.get")
    def test_missing_key_and_bad_coordinates_never_call_provider(self, get):
        _TestConfig.TOMTOM_KEY = "  "
        _, error, status, details = TrafficService.get_tile(12, 2200, 1450)
        self.assertEqual(status, 503)
        self.assertEqual(details["code"], "TRAFFIC_PROVIDER_NOT_CONFIGURED")
        self.assertIn("TOMTOM_KEY", error)

        _TestConfig.TOMTOM_KEY = "test-only-tomtom-secret"
        _, _, invalid_status, invalid_details = TrafficService.get_tile(12, 4096, 0)
        self.assertEqual(invalid_status, 400)
        self.assertEqual(invalid_details["code"], "INVALID_TILE_COORDINATES")
        get.assert_not_called()

    def test_only_tomtom_key_enables_traffic(self):
        _TestConfig.TOMTOM_KEY = ""
        self.assertFalse(TrafficService.is_configured())
        _TestConfig.TOMTOM_KEY = "test-key"
        self.assertTrue(TrafficService.is_configured())


if __name__ == "__main__":
    unittest.main()

