from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from efpb.cli import run_config


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", default="configs/experiments/benchmark.yaml"); args = parser.parse_args()
    start = time.perf_counter(); result = run_config(args.config); elapsed = time.perf_counter() - start
    runs = max(1, result["jobs"])
    payload = {"benchmark_wall_s": elapsed, "jobs": runs, "seconds_per_run": elapsed / runs, "runs_per_hour": runs * 3600 / elapsed, "source": "measured surrogate benchmark"}
    output = Path("data/processed/benchmark.json"); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(payload, indent=2) + "\n"); print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
