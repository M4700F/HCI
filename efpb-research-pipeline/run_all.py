from __future__ import annotations

import argparse
from pathlib import Path

from efpb.cli import run_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", type=int, choices=[1, 2], required=True)
    parser.add_argument("--machines", type=int, default=2)
    parser.add_argument("--config", action="append", default=[])
    args = parser.parse_args()
    configs = args.config or ["configs/experiments/calibration.yaml", "configs/experiments/confirmatory.yaml"]
    for config in configs:
        if Path(config).exists():
            run_config(config, machine=args.machine - 1, machines=args.machines)


if __name__ == "__main__":
    main()
