import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests

from status_relay.cli import main
from status_relay.config import ConfigError, parse_probe, read_config
from status_relay.probes import check_probe

CONFIG = {
    "name": "readiness",
    "url": "https://service.example.invalid/ready",
    "timeout_seconds": 2.5,
    "expected_statuses": [200, 204],
}


class ConfigurationTests(unittest.TestCase):
    def test_defaults(self):
        probe = parse_probe({"name": "root", "url": "https://example.com"}, 1)
        self.assertEqual(probe.timeout_seconds, 5)
        self.assertEqual(probe.expected_statuses, {200})

    def test_bad_probe_values(self):
        for overrides in (
            {"url": "http://example.com"},
            {"url": "https://name:credential@service.example.invalid"},
            {"url": "https://example.com:99999"},
            {"timeout_seconds": 0},
            {"timeout_seconds": True},
            {"expected_statuses": []},
            {"expected_statuses": [700]},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ConfigError) as error:
                parse_probe({**CONFIG, **overrides}, 1)
            self.assertNotIn("name:credential", str(error.exception))

    def test_duplicate_probe_names(self):
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "probes.json"
            config.write_text(json.dumps({"probes": [CONFIG, CONFIG]}), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "unique"):
                read_config(config)


class ProbeTests(unittest.TestCase):
    @patch("status_relay.probes.requests.get")
    def test_healthy_probe_uses_timeout_and_closes_response(self, get):
        response = Mock(status_code=204)
        get.return_value.__enter__.return_value = response
        result = check_probe(parse_probe(CONFIG, 1))
        self.assertTrue(result.healthy)
        self.assertEqual(result.status, 204)
        self.assertIsNone(result.reason)
        self.assertEqual(get.call_args.args, (CONFIG["url"],))
        self.assertEqual(get.call_args.kwargs["timeout"], 2.5)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])
        get.return_value.__exit__.assert_called_once()

    @patch("status_relay.probes.requests.get")
    def test_unexpected_http_status(self, get):
        get.return_value.__enter__.return_value = Mock(status_code=503)
        result = check_probe(parse_probe(CONFIG, 1))
        self.assertFalse(result.healthy)
        self.assertEqual(result.status, 503)
        self.assertEqual(result.reason, "unexpected_status")

    @patch("status_relay.probes.requests.get")
    def test_request_failures_are_classified(self, get):
        for error, reason in (
            (requests.exceptions.Timeout, "timeout"),
            (requests.exceptions.SSLError, "tls_error"),
            (requests.exceptions.ConnectionError, "connection_error"),
            (requests.exceptions.RequestException, "request_error"),
        ):
            with self.subTest(error=error):
                get.side_effect = error("internal detail")
                result = check_probe(parse_probe(CONFIG, 1))
                self.assertFalse(result.healthy)
                self.assertIsNone(result.status)
                self.assertEqual(result.reason, reason)


class CliTests(unittest.TestCase):
    @patch("status_relay.probes.requests.get")
    def test_report_output_and_aggregate_exit_code(self, get):
        get.side_effect = [requests.exceptions.Timeout("private detail")]
        with TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as stdout:
            config = Path(tmp) / "probes.json"
            config.write_text(json.dumps({"probes": [CONFIG]}), encoding="utf-8")
            self.assertEqual(main(["--config", str(config)]), 1)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["healthy"])
            self.assertEqual(report["probes"][0]["reason"], "timeout")
            self.assertNotIn(CONFIG["url"], stdout.getvalue())
            self.assertNotIn("private detail", stdout.getvalue())

    def test_invalid_config_prints_actionable_error(self):
        with TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(main(["--config", str(Path(tmp) / "missing.json")]), 2)
            self.assertIn("Configuration error", stderr.getvalue())
