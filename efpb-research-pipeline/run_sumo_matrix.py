"""Run a SUMO/TraCI experiment config (scenarios x controllers x seeds) in lean mode on several workers.

Each worker uses its own TraCI port and every run checks it reached its own SUMO instance. Stored runs are reused only if their
configuration, runner version and SUMO input files match (config fingerprint); otherwise the run stops with an error.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import time
from pathlib import Path

from efpb.config import load_config
from run_sumo_actual import RUNNER_VERSION, check_reusable, pick_scenario, result_fingerprint, run_config, sumo_files_hash

PORT_BASE = 43000
_W = {}


def _init(cfg, root):
    _W.update(cfg=cfg, root=root)


def _job(job):
    scenario_id, controller, seed = job
    cfg, root = _W["cfg"], Path(_W["root"])
    metrics_path = root / ("sumo_actual__%s__%s__%s" % (scenario_id, controller, seed)) / "metrics.json"
    if metrics_path.exists():
        check_reusable(metrics_path, result_fingerprint(cfg, pick_scenario(cfg, scenario_id), controller, seed, {"runner": RUNNER_VERSION, "sumo_files": sumo_files_hash()}))
        return job
    identity = multiprocessing.current_process()._identity
    run_config(cfg, controller, seed, port=PORT_BASE + (identity[0] if identity else 0), scenario_id=scenario_id, output_root=str(root), lean=True)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/experiments/sumo_matrix.yaml")
    parser.add_argument("--output-root", default="data/sumo_matrix/runs")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--seeds", type=int, help="use only the first N seeds (for a quick timing)")
    parser.add_argument("--scenarios", nargs="*")
    parser.add_argument("--controllers", nargs="*")
    args = parser.parse_args()
    cfg = load_config(args.config)
    seeds = cfg["seeds"][: args.seeds] if args.seeds else cfg["seeds"]
    jobs = [(s["id"], c, int(seed)) for s in cfg["scenarios"] if not args.scenarios or s["id"] in args.scenarios for c in (args.controllers or cfg["controllers"]) for seed in seeds]
    print("%d runs on %d workers" % (len(jobs), args.workers), flush=True)
    start = time.time()
    with multiprocessing.Pool(args.workers, initializer=_init, initargs=(cfg, args.output_root)) as pool:
        for index, _ in enumerate(pool.imap_unordered(_job, jobs, chunksize=1), start=1):
            if index % 50 == 0:
                print("  %d / %d runs, %.0f s" % (index, len(jobs), time.time() - start), flush=True)
    print("done in %.0f s" % (time.time() - start))


if __name__ == "__main__":
    main()
