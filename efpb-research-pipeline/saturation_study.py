"""Where do the surrogate and SUMO saturate? Runs a ladder of demand levels (multiples of the current top level X) with all
controllers at their current defaults and reports service ratios, waits and throughput, so that new demand levels can be
chosen near and above saturation. Calibration seeds only; nothing is frozen."""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import statistics
from pathlib import Path

from efpb.config import load_config
from efpb.sim import CONTROLLERS, make_manifest, run_one
from efpb.sweep import check_calibration_only

LADDER = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
SUMO_LADDER = [1.0, 1.5, 2.0, 2.5, 3.0]


def ladder_config(base: dict, multiplier: float) -> tuple:
    """A copy of the config whose demand table has an extra level 'Q' at `multiplier` times the top level X, and its scenario."""
    cfg = json.loads(json.dumps(base))
    cfg["demand"]["pedestrian_rates_per_s"]["Q"] = multiplier * base["demand"]["pedestrian_rates_per_s"]["X"]
    cfg["demand"]["vehicle_rates_per_s"]["Q"] = multiplier * base["demand"]["vehicle_rates_per_s"]["X"]
    scenario = {"id": "Q%.1f" % multiplier, "pedestrian_demand": "Q", "vehicle_demand": "Q", "process": "poisson_approximation", "sensor_profile": "nominal", "emergency": False}
    return cfg, scenario


def surrogate_rows(base: dict, seeds: list) -> list:
    rows = []
    for multiplier in LADDER:
        cfg, scenario = ladder_config(base, multiplier)
        for controller in CONTROLLERS:
            for seed in seeds:
                with __import__("tempfile").TemporaryDirectory() as tmp:
                    m = run_one(cfg, scenario, controller, seed, tmp, make_manifest(cfg, scenario, seed), lean=True)["metrics"]
                rows.append({"backend": "surrogate", "multiplier": multiplier, "ped_rate": cfg["demand"]["pedestrian_rates_per_s"]["Q"], "veh_rate": cfg["demand"]["vehicle_rates_per_s"]["Q"], "controller": controller, "seed": seed,
                             "ped_service_ratio": m["ped_service_ratio"], "veh_service_ratio": m["veh_service_ratio"], "max_norm_wait": max(m["ped_max_wait_s"] / 100.0, m["veh_max_wait_s"] / 100.0),
                             "ped_p95_wait_s": m["ped_p95_wait_s"], "veh_p95_wait_s": m["veh_p95_wait_s"], "veh_throughput_h": m["veh_throughput_h"], "starvation_violations": m["starvation_violations"]})
    return rows


_W = {}


def _sumo_init(base, root):
    _W.update(base=base, root=root)


def _sumo_job(job):
    import run_sumo_actual as runner
    multiplier, controller, seed = job
    cfg, scenario = ladder_config(_W["base"], multiplier)
    cfg["scenarios"] = [scenario]
    out = Path(_W["root"]) / ("m%.1f" % multiplier) / controller
    m = runner.run_config(cfg, controller, seed, scenario_id=scenario["id"], output_root=str(out), lean=True)
    demand_veh_h = cfg["demand"]["vehicle_rates_per_s"]["Q"] * 3600.0
    return {"backend": "sumo", "multiplier": multiplier, "ped_rate": cfg["demand"]["pedestrian_rates_per_s"]["Q"], "veh_rate": cfg["demand"]["vehicle_rates_per_s"]["Q"], "controller": controller, "seed": seed,
            "veh_completion_ratio": m["vehicle_throughput_per_hour"] / demand_veh_h, "vehicle_throughput_per_hour": m["vehicle_throughput_per_hour"], "mean_vehicle_queue": m["mean_vehicle_queue"],
            "vehicle_stop_time_mean_s": m["vehicle_stop_time_mean_s"], "vehicle_stopped_wait_max_s": m["vehicle_stopped_wait_max_s"], "pedestrian_wait_max_s": m["pedestrian_wait_max_s"],
            "ped_service_ratio": m["pedestrian_served_virtual"] / max(1.0, cfg["demand"]["pedestrian_rates_per_s"]["Q"] * m["steps"]),
            "max_norm_wait": max(m["pedestrian_wait_max_s"] / 100.0, m["vehicle_stopped_wait_max_s"] / 100.0), "emergency_stops": m["emergency_stops"], "collisions": m["collisions"]}


def sumo_rows(base: dict, seeds: list, root: str, workers: int) -> list:
    jobs = [(mult, controller, seed) for mult in SUMO_LADDER for controller in ("fixed_time", "efficiency", "efpb") for seed in seeds]
    with multiprocessing.Pool(workers, initializer=_sumo_init, initargs=(base, root)) as pool:
        return list(pool.imap_unordered(_sumo_job, jobs))


def summarise(rows: list, keys: list) -> list:
    out = []
    for multiplier in sorted({r["multiplier"] for r in rows}):
        for controller in sorted({r["controller"] for r in rows}):
            group = [r for r in rows if r["multiplier"] == multiplier and r["controller"] == controller]
            out.append(dict({"multiplier": multiplier, "controller": controller, "ped_rate": group[0]["ped_rate"], "veh_rate": group[0]["veh_rate"], "runs": len(group)}, **{k: statistics.mean(r[k] for r in group) for k in keys}))
    return out


def write_csv(path: Path, rows: list) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/experiments/calibration_sweep.yaml")
    parser.add_argument("--sumo-config", default="configs/experiments/sumo_calibration.yaml")
    parser.add_argument("--output-root", default="data/saturation_study")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--skip-sumo", action="store_true")
    args = parser.parse_args()
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    base = load_config(args.config)
    check_calibration_only(base)
    base["signal"]["fixed_timing"], base["signal"]["fixed_cycle_s"] = "demand_based", 37  # the calibrated fixed-time plan; also the sensor fallback
    rows = surrogate_rows(base, base["seeds"])
    keys = ["ped_service_ratio", "veh_service_ratio", "max_norm_wait", "ped_p95_wait_s", "veh_p95_wait_s", "veh_throughput_h", "starvation_violations"]
    write_csv(root / "surrogate_runs.csv", rows)
    write_csv(root / "surrogate_summary.csv", summarise(rows, keys))
    print("surrogate ladder done:", len(rows), "runs", flush=True)
    if not args.skip_sumo:
        sbase = load_config(args.sumo_config)
        check_calibration_only(sbase)
        sbase["signal"]["fixed_timing"], sbase["signal"]["fixed_cycle_s"] = "demand_based", 37
        srows = sumo_rows(sbase, sbase["seeds"][:3], str(root / "sumo_runs"), args.workers)
        skeys = ["veh_completion_ratio", "vehicle_throughput_per_hour", "mean_vehicle_queue", "vehicle_stop_time_mean_s", "vehicle_stopped_wait_max_s", "pedestrian_wait_max_s", "ped_service_ratio", "max_norm_wait", "emergency_stops", "collisions"]
        write_csv(root / "sumo_runs.csv", srows)
        write_csv(root / "sumo_summary.csv", summarise(srows, skeys))
        print("SUMO ladder done:", len(srows), "runs", flush=True)


if __name__ == "__main__":
    main()
