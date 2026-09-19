"""SUMO/TraCI calibration sweep (selection stage): every controller's configurations on calibration scenarios and seeds.

Confirmation on fresh seeds and the freeze are done by freeze_calibration.py --backend sumo. Nothing here is frozen.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import statistics
from collections import defaultdict
from pathlib import Path

from efpb.config import load_config
from efpb.sweep import add_paired_differences, apply_overrides, build_configs, check_calibration_only, check_config_table
from run_sumo_actual import RUNNER_VERSION, check_reusable, pick_scenario, result_fingerprint, run_config, sumo_files_hash

_WORKER = {}
PORT_BASE = 42000  # one TraCI port per worker process; a run checks that it reached its own SUMO instance


def derived(metrics: dict, base: dict) -> dict:
    """Person delay = occupancy-weighted mean of vehicle stop time and pedestrian wait over everyone, including pedestrians still
    waiting and vehicles still in the network at the end; max wait = largest wait over its limit."""
    occupancy = float(base["demand"]["occupancy_mean"])
    ped, veh = metrics["pedestrian_served_virtual"] + metrics["pedestrian_unserved"], metrics["vehicle_completed"] + metrics["vehicle_unfinished"]
    people = ped + occupancy * veh
    delay = ped * metrics["pedestrian_wait_mean_s"] + occupancy * veh * metrics["vehicle_stop_time_all_mean_s"]
    return {
        "person_delay_s": delay / max(1.0, people),
        "max_norm_wait": max(metrics["pedestrian_wait_max_s"] / float(base["controller"]["ped_wait_limit_s"]), metrics["vehicle_stopped_wait_max_s"] / float(base["controller"]["vehicle_wait_limit_s"])),
        "vehicle_stop_time_mean_s": metrics["vehicle_stop_time_all_mean_s"],
        "pedestrian_wait_mean_s": metrics["pedestrian_wait_mean_s"],
        "vehicle_stopped_wait_p95_s": metrics["vehicle_stopped_wait_p95_s"],
        "mean_vehicle_queue": metrics["mean_vehicle_queue"],
        "phase_switches": float(metrics["phase_switches"]),
        "clearance_share": metrics["clearance_steps"] / float(base["evaluation_s"]),
        "emergency_stops": float(metrics["emergency_stops"]),
        "collisions": float(metrics["collisions"]),
    }


def _init(base, configs, root):
    _WORKER.update(base=base, configs={item["config_id"]: item for item in configs}, root=root)


def _job(job):
    config_id, scenario_id, seed = job
    spec, base = _WORKER["configs"][config_id], _WORKER["base"]
    controller = spec["controller"]
    cfg = apply_overrides(base, spec["overrides"], config_id)
    out = Path(_WORKER["root"]) / "runs" / config_id
    metrics_path = out / ("sumo_actual__%s__%s__%s" % (scenario_id, controller, seed)) / "metrics.json"
    if metrics_path.exists():  # a stored run is reused only if its configuration, runner and SUMO files match
        fingerprint = result_fingerprint(cfg, pick_scenario(cfg, scenario_id), controller, seed, {"runner": RUNNER_VERSION, "sumo_files": sumo_files_hash()})
        check_reusable(metrics_path, fingerprint)
        return config_id
    identity = multiprocessing.current_process()._identity
    run_config(cfg, controller, seed, port=PORT_BASE + (identity[0] if identity else 0), scenario_id=scenario_id, output_root=str(out), lean=True)
    return config_id


def run_stage(base: dict, configs: list, seeds: list, root: str, workers: int) -> None:
    stage = dict(base, seeds=seeds)
    jobs = [(item["config_id"], scenario["id"], int(seed)) for item in configs for scenario in stage["scenarios"] for seed in seeds]
    print("  %d runs" % len(jobs), flush=True)
    if workers <= 1:
        _init(stage, configs, root)
        for job in jobs:
            _job(job)
        return
    with multiprocessing.Pool(workers, initializer=_init, initargs=(stage, configs, root)) as pool:
        for index, _ in enumerate(pool.imap_unordered(_job, jobs, chunksize=2), start=1):
            if index % 200 == 0:
                print("  %d / %d runs" % (index, len(jobs)), flush=True)


def collect(base: dict, configs: list, seeds: list, root: str):
    by_id = {item["config_id"]: item for item in configs}
    rows = []
    for path in sorted(Path(root, "runs").glob("*/*/metrics.json")):
        config_id = path.parent.parent.name
        if config_id not in by_id:
            continue
        metrics = json.loads(path.read_text())
        if metrics["seed"] in seeds:
            rows.append(dict(config_id=config_id, controller=by_id[config_id]["controller"], scenario_id=metrics["scenario_id"], seed=metrics["seed"], **derived(metrics, base)))
    expected = len(base["scenarios"]) * len(seeds)
    keys = ["person_delay_s", "max_norm_wait", "vehicle_stop_time_mean_s", "pedestrian_wait_mean_s", "vehicle_stopped_wait_p95_s", "mean_vehicle_queue", "phase_switches", "clearance_share", "emergency_stops", "collisions"]
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["config_id"]][row["scenario_id"]].append(row)
    summaries = []
    for config_id, per_scenario in grouped.items():
        runs = sum(len(items) for items in per_scenario.values())
        if runs != expected:
            raise SystemExit("%s has %d of %d runs; finish the sweep before summarising." % (config_id, runs, expected))
        scenario_means = {sid: {key: statistics.mean(item[key] for item in items) for key in keys} for sid, items in per_scenario.items()}
        summary = {"config_id": config_id, "controller": by_id[config_id]["controller"], "is_default": by_id[config_id]["is_default"], "runs": runs}
        for key in keys:
            summary[key] = statistics.mean(value[key] for value in scenario_means.values())
        summary["worst_scenario_max_norm_wait"] = max(value["max_norm_wait"] for value in scenario_means.values())
        summary["emergency_stops_total"] = sum(item["emergency_stops"] for items in per_scenario.values() for item in items)
        summary["collisions_total"] = sum(item["collisions"] for items in per_scenario.values() for item in items)
        for dotted, value in by_id[config_id]["overrides"].items():
            summary["p:" + dotted] = value
        summaries.append(summary)
    add_paired_differences(rows, summaries)
    return rows, summaries


def write_csv(path: Path, rows: list) -> None:
    fields = sorted({key for row in rows for key in row}, key=lambda key: (key.startswith("p:"), key))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/experiments/sumo_calibration.yaml")
    parser.add_argument("--output-root", default="data/sumo_calibration")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    base = load_config(args.config)
    check_calibration_only(base)
    check_calibration_only(dict(base, seeds=base["sweep"]["confirm_seeds"]))
    configs = build_configs(base)
    counts = {}
    for item in configs:
        counts[item["controller"]] = counts.get(item["controller"], 0) + 1
    print(json.dumps({"configurations": len(configs), "per_controller": counts, "selection_runs": len(configs) * len(base["scenarios"]) * len(base["seeds"])}, indent=2))
    if args.dry_run:
        return
    root = Path(args.output_root)
    check_config_table(configs, str(root))
    run_stage(base, configs, base["seeds"], str(root / "selection"), args.workers)
    rows, summaries = collect(base, configs, base["seeds"], str(root / "selection"))
    write_csv(root / "summary_selection.csv", sorted(summaries, key=lambda r: r["config_id"]))
    write_csv(root / "run_metrics_selection.csv", rows)
    print("wrote", root / "summary_selection.csv", "(selection stage only; run freeze_calibration.py --backend sumo next)")


if __name__ == "__main__":
    main()
