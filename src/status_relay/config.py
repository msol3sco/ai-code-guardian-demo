import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}")


class ConfigError(ValueError):
    """An error in the local probe configuration."""


@dataclass(frozen=True)
class Probe:
    name: str
    url: str
    timeout_seconds: float
    expected_statuses: frozenset[int]


def parse_probe(entry: object, index: int) -> Probe:
    label = f"Probe {index}"
    fields = {"name", "url", "timeout_seconds", "expected_statuses"}
    if not isinstance(entry, dict) or entry.keys() - fields:
        raise ConfigError(f"{label} must be an object with supported probe settings.")
    name = entry.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ConfigError(f"{label} needs a short name using letters, digits, dashes, or underscores.")
    url = entry.get("url")
    if not isinstance(url, str) or not url or any(char.isspace() or ord(char) < 32 for char in url):
        raise ConfigError(f"{label} needs a valid HTTPS URL.")
    try:
        parsed = urlsplit(url)
        parsed.port  # Validate a port when present.
        valid_url = (
            parsed.scheme == "https" and parsed.hostname is not None
            and parsed.username is None and not parsed.fragment
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ConfigError(f"{label} needs an HTTPS URL without credentials or a fragment.")
    timeout = entry.get("timeout_seconds", 5)
    if type(timeout) not in (int, float) or not 0 < timeout <= 60:
        raise ConfigError(f"{label} needs a timeout above zero and at most 60 seconds.")
    statuses = entry.get("expected_statuses", [200])
    if not isinstance(statuses, list) or not statuses or any(
        type(status) is not int or not 100 <= status <= 599 for status in statuses
    ):
        raise ConfigError(f"{label} needs a non-empty list of HTTP status codes.")
    return Probe(name, url, float(timeout), frozenset(statuses))


def read_config(path: Path) -> list[Probe]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        raise ConfigError("Could not read the probe configuration as UTF-8 JSON.") from None
    if not isinstance(payload, dict) or payload.keys() != {"probes"}:
        raise ConfigError("The configuration must contain a 'probes' array.")
    entries = payload["probes"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        raise ConfigError("Configure between 1 and 100 probes.")
    probes = [parse_probe(entry, index) for index, entry in enumerate(entries, 1)]
    if len({probe.name for probe in probes}) != len(probes):
        raise ConfigError("Probe names must be unique.")
    return probes
