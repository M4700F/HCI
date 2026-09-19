from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .config import load_config, write_json
from .sim import CONTROLLERS, make_manifest, run_one


def run_config(config_path: str, output_root: str = "data/runs", only_controllers: Optional[Sequence[str]] = None, machine: int = 0, machines: int = 1, lean: bool = False) -> Dict[str, Any]:
    cfg = load_config(config_path)
    controllers = list(only_controllers or cfg.get("controllers", list(CONTROLLERS)))
    jobs = [(scenario, controller, seed) for scenario in cfg.get("scenarios", []) for controller in controllers for seed in cfg.get("seeds", [1])]
    jobs = [job for index, job in enumerate(jobs) if index % machines == machine]
    results = []
    for scenario, controller, seed in jobs:
        manifest = make_manifest(cfg, scenario, int(seed))
        manifest_dir = Path("data/manifests") / cfg["experiment_id"]
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / ("%s__%s.json" % (scenario["id"], seed))).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        results.append(run_one(cfg, scenario, controller, int(seed), output_root, manifest, lean=lean))
    result = {"experiment_id": cfg["experiment_id"], "machine": machine, "machines": machines, "jobs": len(jobs), "runs": results}
    write_json(str(Path(output_root) / cfg["experiment_id"] / ("machine_%d_summary.json" % machine)), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="data/runs")
    parser.add_argument("--controllers", nargs="*")
    parser.add_argument("--machine", type=int, default=0)
    parser.add_argument("--machines", type=int, default=1)
    parser.add_argument("--lean", action="store_true", help="metrics only: no traces, explanations or per-second files (identical metrics, much faster)")
    args = parser.parse_args()
    print(json.dumps(run_config(args.config, args.output_root, args.controllers, args.machine, args.machines, args.lean), indent=2))
