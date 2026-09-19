from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_sumo_actual import check_reusable, run, run_fingerprint
from efpb.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the time-boxed real SUMO/TraCI matrix sequentially.")
    parser.add_argument("--config", default="configs/experiments/sumo_emergency.yaml")
    parser.add_argument("--machine", type=int, choices=[1, 2], default=1)
    parser.add_argument("--machines", type=int, choices=[1, 2], default=2)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args()
    if args.machine > args.machines:
        raise SystemExit("--machine must be <= --machines")
    cfg = load_config(args.config)
    scenarios = [x for x in cfg.get("scenarios", []) if args.scenario is None or x.get("id") == args.scenario]
    jobs = [(s["id"], controller, int(seed)) for s in scenarios for controller in cfg["controllers"] for seed in cfg["seeds"]]
    assigned = [job for index, job in enumerate(jobs) if index % args.machines == args.machine - 1]
    print(json.dumps({"assigned_runs": len(assigned), "machine": args.machine, "machines": args.machines}, indent=2))
    for index, (scenario_id, controller, seed) in enumerate(assigned, start=1):
        output = Path("data/sumo_runs") / f"sumo_actual__{scenario_id}__{controller}__{seed}" / "metrics.json"
        if output.exists():
            check_reusable(output, run_fingerprint(args.config, controller, seed, scenario_id))
            print(f"SKIP {index}/{len(assigned)} {output}")
            continue
        print(f"RUN {index}/{len(assigned)} scenario={scenario_id} controller={controller} seed={seed}", flush=True)
        result = run(args.config, controller, seed, scenario_id=scenario_id)
        print(json.dumps({"run_id": result["run_id"], "wall_time_s": result["wall_time_s"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
