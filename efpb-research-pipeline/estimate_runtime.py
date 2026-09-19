from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="data/processed/benchmark.json")
    parser.add_argument("--seconds-per-run", type=float)
    parser.add_argument("--runs", type=int, default=1540)
    parser.add_argument("--sim-seconds", type=float, default=4200.0)
    parser.add_argument("--benchmark-sim-seconds", type=float, default=660.0)
    parser.add_argument("--machines", type=int, default=2)
    args = parser.parse_args()
    measured = args.seconds_per_run
    if measured is None:
        measured = json.loads(Path(args.benchmark).read_text())["seconds_per_run"]
    scaled = measured * args.sim_seconds / args.benchmark_sim_seconds
    total_cpu = scaled * args.runs
    wall = total_cpu / args.machines
    result = {"source": "measured benchmark extrapolation", "measured_seconds_per_benchmark_run": measured, "assumed_sim_seconds_per_research_run": args.sim_seconds, "research_runs": args.runs, "estimated_seconds_per_research_run": scaled, "estimated_total_cpu_hours": total_cpu / 3600.0, "estimated_two_machine_wall_hours": wall / 3600.0, "upper_bound_1_5x_hours": wall * 1.5 / 3600.0, "upper_bound_2x_hours": wall * 2.0 / 3600.0, "warning": "This is surrogate-backend extrapolation until a SUMO benchmark is measured on both computers."}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
