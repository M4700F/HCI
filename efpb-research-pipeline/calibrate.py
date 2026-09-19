from __future__ import annotations

import argparse
import json
from pathlib import Path

from efpb.cli import run_config


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--config", default="configs/experiments/calibration.yaml"); parser.add_argument("--output-root", default="data/runs"); args = parser.parse_args()
    result = run_config(args.config, output_root=args.output_root)
    output = Path("data/processed/calibration_summary.json"); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, default=str) + "\n"); print("Calibration runs complete; inspect outputs before freezing parameters.")


if __name__ == "__main__":
    main()
