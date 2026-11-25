from dataclasses import dataclass
from time import monotonic

import requests

from .config import Probe


@dataclass(frozen=True)
class ProbeResult:
    name: str
    healthy: bool
    status: int | None
    latency_ms: int
    reason: str | None


def check_probe(probe: Probe) -> ProbeResult:
    start = monotonic()
    status = None
    try:
        with requests.get(
            probe.url,
            timeout=probe.timeout_seconds,
            headers={"User-Agent": "StatusRelay/0.1"},
            allow_redirects=False,
            stream=True,
        ) as response:
            status = response.status_code
        reason = None if status in probe.expected_statuses else "unexpected_status"
    except requests.exceptions.Timeout:
        reason = "timeout"
    except requests.exceptions.SSLError:
        reason = "tls_error"
    except requests.exceptions.ConnectionError:
        reason = "connection_error"
    except requests.exceptions.RequestException:
        reason = "request_error"
    return ProbeResult(probe.name, reason is None, status, round((monotonic() - start) * 1000), reason)
