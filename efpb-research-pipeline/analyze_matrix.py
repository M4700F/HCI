"""Descriptive analysis of the surrogate and SUMO matrix runs: per-cell means, per-group means and paired differences of efpb
against each other controller (same scenario and seed). No significance tests: the preregistered models are not implemented."""
from __future__ import annotations

import csv
import glob
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from efpb.config import load_config
from efpb.sweep import derived_metrics

CONTROLLERS = ["fixed_time", "efficiency", "equal_bargaining", "efpb"]
OUT = Path("data/results")
# Excluded for validity, decided from the code and not from the outcomes: with sensor_profile "accessibility" the simulator keeps
# accessibility_extension on for the whole run, which marks every vehicle plan unsafe, so vehicles are never served by any controller.
EXCLUDED = {"S11_accessibility": "controller marks every vehicle plan unsafe for the whole run; vehicles are never served"}


def surrogate_rows():
    rows = []
    for experiment, group in (("confirmatory_core", "nominal"), ("stress", "stress"), ("robustness", "robustness")):
        base = load_config("configs/experiments/%s.yaml" % experiment)
        for path in glob.glob("data/matrix/**/run_metrics.json", recursive=True):
            m = json.loads(Path(path).read_text())
            if m["experiment_id"] != experiment:
                continue
            d = derived_metrics(m, base)
            rows.append({"backend": "surrogate", "group": group, "scenario": m["scenario_id"], "controller": m["controller"], "seed": m["seed"],
                         "person_delay_s": d["person_delay_s"], "max_norm_wait": d["max_norm_wait"], "ped_mean_wait_s": m["ped_mean_wait_s"], "veh_mean_wait_s": m["veh_mean_wait_s"],
                         "starvation_violations": m["starvation_violations"], "ped_service_ratio": m["ped_service_ratio"], "veh_service_ratio": m["veh_service_ratio"], "jain": m["jain"] if m["jain"] is not None else float("nan")})
    return rows


def sumo_rows():
    from sweep_sumo_calibration import derived
    base = load_config("configs/experiments/sumo_matrix.yaml")
    rows = []
    for path in glob.glob("data/sumo_matrix/runs/*/metrics.json"):
        m = json.loads(Path(path).read_text())
        d = derived(m, base)
        rows.append({"backend": "SUMO", "group": "nominal" if m["scenario_id"].startswith("C_") else "stress", "scenario": m["scenario_id"], "controller": m["controller"], "seed": m["seed"],
                     "person_delay_s": d["person_delay_s"], "max_norm_wait": d["max_norm_wait"], "ped_mean_wait_s": m["pedestrian_wait_mean_s"], "veh_mean_wait_s": d["vehicle_stop_time_mean_s"],
                     "collisions": m["collisions"], "emergency_stops": m["emergency_stops"], "ped_unserved": m["pedestrian_unserved"], "veh_unfinished": m["vehicle_unfinished"]})
    return rows


def mean_se(values):
    values = [v for v in values if not math.isnan(v)]
    return (statistics.mean(values), statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0) if values else (float("nan"), 0.0)


def analyse(rows, backend, extra):
    keys = ["person_delay_s", "max_norm_wait", "ped_mean_wait_s", "veh_mean_wait_s"] + extra
    by = defaultdict(list)
    for r in rows:
        by[(r["group"], r["scenario"], r["controller"])].append(r)
    cells = []
    for (group, scenario, controller), items in sorted(by.items()):
        cells.append(dict({"backend": backend, "group": group, "scenario": scenario, "controller": controller, "runs": len(items)}, **{k: statistics.mean(i[k] for i in items) for k in keys}))
    groups = sorted({c["group"] for c in cells}) + ["all"]
    overall = []
    for group in groups:
        for controller in CONTROLLERS:
            sel = [c for c in cells if c["controller"] == controller and (group == "all" or c["group"] == group)]
            if sel:
                overall.append(dict({"backend": backend, "group": group, "controller": controller, "cells": len(sel)}, **{k: statistics.mean(c[k] for c in sel) for k in keys}))
    paired = []
    for group in groups:
        for other in CONTROLLERS[:-1]:
            for metric in ("person_delay_s", "max_norm_wait", "ped_mean_wait_s", "veh_mean_wait_s"):
                pairs, wins, cell_ids = [], 0, 0
                for scenario in sorted({r["scenario"] for r in rows if group == "all" or r["group"] == group}):
                    a = {r["seed"]: r[metric] for r in rows if r["scenario"] == scenario and r["controller"] == "efpb"}
                    b = {r["seed"]: r[metric] for r in rows if r["scenario"] == scenario and r["controller"] == other}
                    diffs = [a[s] - b[s] for s in a if s in b]
                    pairs += diffs
                    if diffs:
                        cell_ids += 1
                        wins += statistics.mean(diffs) < 0
                m, se = mean_se(pairs)
                paired.append({"backend": backend, "group": group, "comparison": "efpb - " + other, "metric": metric, "pairs": len(pairs), "mean_diff": m, "se": se, "cells_efpb_lower": wins, "cells": cell_ids})
    return cells, overall, paired


def write(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, loader, extra, expected in (("surrogate", surrogate_rows, ["starvation_violations", "ped_service_ratio", "veh_service_ratio"], 1080 + 360 + 480), ("sumo", sumo_rows, ["collisions", "emergency_stops", "ped_unserved", "veh_unfinished"], 520)):
        rows = loader()
        if len(rows) != expected:
            raise SystemExit("%s: %d runs found, expected %d" % (name, len(rows), expected))
        write(OUT / ("runs_%s.csv" % name), rows)  # all runs, including the excluded scenarios
        rows = [r for r in rows if r["scenario"] not in EXCLUDED]
        cells, overall, paired = analyse(rows, name, extra)
        write(OUT / ("cells_%s.csv" % name), cells)
        write(OUT / ("overall_%s.csv" % name), overall)
        write(OUT / ("paired_%s.csv" % name), paired)
        print(name, len(rows), "runs analysed, excluded scenarios:", sorted(EXCLUDED) if name == "surrogate" else "none")
    (OUT / "excluded.json").write_text(json.dumps(EXCLUDED, indent=1) + "\n")


if __name__ == "__main__":
    main()
