from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from efpb.config import load_config
from efpb.sweep import build_configs, check_calibration_only, check_config_table, collect, run_sweep, write_outputs


def main():
    parser = argparse.ArgumentParser(description="Calibration-only parameter sweep with Pareto summaries; suggests values, freezes nothing.")
    parser.add_argument("--config", default="configs/experiments/calibration_sweep.yaml")
    parser.add_argument("--output-root", default="data/calibration_sweep")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--dry-run", action="store_true", help="list the configurations and run counts without running")
    parser.add_argument("--summarize-only", action="store_true", help="skip running and summarise the runs already on disk")
    args = parser.parse_args()
    base = load_config(args.config)
    check_calibration_only(base)
    configs = build_configs(base)
    per_config = len(base["scenarios"]) * len(base["seeds"])
    counts = {}
    for item in configs:
        counts[item["controller"]] = counts.get(item["controller"], 0) + 1
    print(json.dumps({"configurations": len(configs), "per_controller": counts, "runs_per_configuration": per_config, "total_runs": len(configs) * per_config}, indent=2))
    if args.dry_run:
        return
    check_config_table(configs, args.output_root)
    if not args.summarize_only:
        run_sweep(base, configs, args.output_root, args.workers)
    rows, summaries = collect(base, configs, args.output_root)
    result = write_outputs(base, configs, rows, summaries, args.output_root)
    print("wrote", Path(args.output_root) / "report.md", "| delta knee suggestion:", result["delta_knee_suggestion"], "(suggestion only; nothing frozen)")


if __name__ == "__main__":
    main()
