from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def number(row, key):
    try:
        return float(row.get(key, 0))
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Create descriptive summaries from real SUMO metrics.")
    parser.add_argument("--input", default="data/processed/sumo_metrics.csv")
    parser.add_argument("--output", default="data/processed/sumo_analysis.json")
    args = parser.parse_args()
    with Path(args.input).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("scenario_id", "unknown"), row.get("controller", "unknown"))].append(row)
    summary = {}
    for (scenario, controller), group in sorted(groups.items()):
        summary[f"{scenario}__{controller}"] = {
            "scenario_id": scenario,
            "controller": controller,
            "n": len(group),
            "vehicle_throughput_per_hour_mean": statistics.mean(number(x, "vehicle_throughput_per_hour") for x in group),
            "vehicle_trip_time_mean_s": statistics.mean(number(x, "vehicle_trip_time_mean_s") for x in group),
            "vehicle_stopped_wait_mean_s": statistics.mean(number(x, "vehicle_stopped_wait_mean_s") for x in group),
            "vehicle_stopped_wait_p95_s": statistics.mean(number(x, "vehicle_stopped_wait_p95_s") for x in group),
            "mean_vehicle_queue": statistics.mean(number(x, "mean_vehicle_queue") for x in group),
            "vehicle_stop_time_mean_s": statistics.mean(number(x, "vehicle_stop_time_mean_s") for x in group),
            "pedestrian_served_virtual": statistics.mean(number(x, "pedestrian_served_virtual") for x in group),
            "pedestrian_wait_mean_s": statistics.mean(number(x, "pedestrian_wait_mean_s") for x in group),
            "phase_switches": statistics.mean(number(x, "phase_switches") for x in group),
            "emergency_stops": statistics.mean(number(x, "emergency_stops") for x in group),
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"n_runs": len(rows), "groups": summary, "note": "Descriptive pilot summary only; no inferential significance is claimed."}, indent=2))
    print("wrote", output, "groups", len(summary))


if __name__ == "__main__":
    main()
