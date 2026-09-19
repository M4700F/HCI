from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="data/processed/run_metrics.csv"); parser.add_argument("--output", default="data/processed/analysis.json"); args = parser.parse_args()
    rows = list(csv.DictReader(open(args.input)))
    grouped = defaultdict(list)
    metrics = {"ped_mean_wait_s", "veh_mean_wait_s", "ped_p95_wait_s", "veh_p95_wait_s", "jain", "mean_wait_disparity", "tail_wait_disparity", "starvation_violations", "wall_time_s"}
    for row in rows:
        for key, value in row.items():
            if key in metrics and value not in ("", "None"):
                grouped[(row["controller"], key)].append(float(value))
    result = {"status": "descriptive_only", "note": "This standard-library output does not make confirmatory significance claims.", "controllers": {}}
    for (controller, metric), values in grouped.items():
        result["controllers"].setdefault(controller, {})[metric] = {"n": len(values), "mean": sum(values) / len(values), "min": min(values), "max": max(values)}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); print("wrote", output)


if __name__ == "__main__":
    main()
