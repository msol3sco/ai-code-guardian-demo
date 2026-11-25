import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .config import ConfigError, read_config
from .probes import check_probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check configured HTTPS endpoints.")
    parser.add_argument("--config", type=Path, required=True, help="path to the JSON probe configuration")
    args = parser.parse_args(argv)
    try:
        probes = read_config(args.config)
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    results = [check_probe(probe) for probe in probes]
    healthy = all(result.healthy for result in results)
    print(json.dumps({"healthy": healthy, "probes": [asdict(result) for result in results]}, indent=2))
    return int(not healthy)
