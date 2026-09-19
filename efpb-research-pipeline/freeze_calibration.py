"""Select, confirm and freeze calibrated parameters for one backend, following the pre-declared rules.

1. Read the selection-stage results (already run by sweep_calibration.py / sweep_sumo_calibration.py) and apply the
   closest-to-ideal rule per controller. The picks are written to selection.json BEFORE any confirmation run and are never
   re-picked (a rerun must reproduce them from the same results).
2. Run only the picked and default configurations on fresh confirmation seeds, plus efpb's delta sensitivity set.
3. Adopt a pick unless it is worse than the default in both objectives; write configs/frozen_<backend>.yaml and a report.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import statistics
import sys
from pathlib import Path

import yaml

from efpb.config import load_config
from efpb.selection import adopt, frozen_settings, pick_closest_to_ideal
from efpb.sweep import build_configs, check_calibration_only

DELTA_SET = [0, 0.02, 0.05, 0.10, 0.20]  # the sensitivity set required by the research plan


def surrogate_backend():
    from efpb import sweep
    return {"selection_root": lambda root: root, "confirmation_root": lambda root: root / "confirmation", "exclude": lambda row: False,
            "collect": lambda base, configs, seeds, root: sweep.collect(dict(base, seeds=seeds), configs, str(root)),
            "run": lambda base, configs, seeds, root, workers: sweep.run_sweep(dict(base, seeds=seeds), configs, str(root), workers)}


def sumo_backend():
    import sweep_sumo_calibration as sumo
    return {"selection_root": lambda root: root / "selection", "confirmation_root": lambda root: root / "confirmation", "exclude": lambda row: float(row.get("collisions_total", 0)) > 0,
            "collect": lambda base, configs, seeds, root: sumo.collect(base, configs, seeds, str(root)),
            "run": lambda base, configs, seeds, root, workers: sumo.run_stage(base, configs, seeds, str(root), workers)}


def digest(summaries: list) -> str:
    slim = [{k: (round(v, 9) if isinstance(v, float) else v) for k, v in sorted(row.items())} for row in sorted(summaries, key=lambda r: r["config_id"])]
    return hashlib.sha256(json.dumps(slim, sort_keys=True, default=str).encode()).hexdigest()


def paired(rows: list, a: str, b: str, key: str):
    x = {(r["scenario_id"], r["seed"]): float(r[key]) for r in rows if r["config_id"] == a}
    y = {(r["scenario_id"], r["seed"]): float(r[key]) for r in rows if r["config_id"] == b}
    d = [y[k] - x[k] for k in x]
    return statistics.mean(d), (statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["surrogate", "sumo"], required=True)
    parser.add_argument("--config")
    parser.add_argument("--output-root")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--force", action="store_true", help="allow replacing an existing selection.json (breaks pre-commitment; say why in the report)")
    args = parser.parse_args()
    config = args.config or ("configs/experiments/calibration_sweep.yaml" if args.backend == "surrogate" else "configs/experiments/sumo_calibration.yaml")
    root = Path(args.output_root or ("data/calibration_sweep" if args.backend == "surrogate" else "data/sumo_calibration"))
    backend = surrogate_backend() if args.backend == "surrogate" else sumo_backend()
    base = load_config(config)
    confirm_seeds = base["sweep"]["confirm_seeds"]
    check_calibration_only(base)
    check_calibration_only(dict(base, seeds=confirm_seeds))
    if set(confirm_seeds) & set(base["seeds"]):
        raise SystemExit("confirmation seeds must be new")
    configs = build_configs(base)
    by_id = {item["config_id"]: item for item in configs}
    controllers = list(base["sweep"]["controllers"])
    _, summaries = backend["collect"](base, configs, base["seeds"], backend["selection_root"](root))

    # 1. selection (pre-committed)
    selection_path = root / "selection.json"
    picks = {}
    for controller in controllers:
        rows = [s for s in summaries if s["controller"] == controller]
        picks[controller] = pick_closest_to_ideal(rows, backend["exclude"])["config_id"]
    record = {"rule": "closest to ideal after min-max scaling within each controller (delay, max wait); safety exclusions applied", "selection_seeds": base["seeds"], "picks": picks, "selection_summary_sha256": digest(summaries),
              "recorded": datetime.datetime.now().isoformat(timespec="seconds")}
    if selection_path.exists() and not args.force:
        stored = json.loads(selection_path.read_text())
        if stored["picks"] != picks or stored["selection_summary_sha256"] != record["selection_summary_sha256"]:
            raise SystemExit("selection.json exists and the selection results differ; not re-picking (use --force and explain in the report).")
        record = stored
    else:
        selection_path.write_text(json.dumps(record, indent=1) + "\n")
    print("picks:", picks, flush=True)

    # 2. confirmation on fresh seeds
    specs = {}
    for controller in controllers:
        default = next(item for item in configs if item["controller"] == controller and item["is_default"])
        for cid in {default["config_id"], picks[controller]}:
            specs[cid] = by_id[cid]
    sens = []
    if "efpb" in picks:
        chosen = by_id[picks["efpb"]]
        for delta in DELTA_SET:
            overrides = dict(chosen["overrides"], **{"controller.delta": delta})
            existing = next((item for item in configs if item["controller"] == "efpb" and item["overrides"] == overrides), None)
            spec = existing or {"config_id": "efpb__sens_d%s" % delta, "controller": "efpb", "overrides": overrides, "is_default": False}
            specs[spec["config_id"]] = spec
            sens.append((delta, spec["config_id"]))
    confirm_root = backend["confirmation_root"](root)
    print("confirmation: %d configurations on %d new seeds" % (len(specs), len(confirm_seeds)), flush=True)
    backend["run"](base, list(specs.values()), confirm_seeds, confirm_root, args.workers)
    rows, conf = backend["collect"](base, list(specs.values()), confirm_seeds, confirm_root)
    conf_by_id = {row["config_id"]: row for row in conf}

    # 3. adoption and freeze
    adopted, defaults, decisions = {}, {}, {}
    for controller in controllers:
        default = next(item for item in configs if item["controller"] == controller and item["is_default"])
        defaults[controller] = default["overrides"]
        pick = by_id[picks[controller]]
        if pick["config_id"] == default["config_id"]:
            dd = dw = 0.0
            se_d = se_w = 0.0
        else:
            dd, se_d = paired(rows, default["config_id"], pick["config_id"], "person_delay_s")
            dw, se_w = paired(rows, default["config_id"], pick["config_id"], "max_norm_wait")
        take = adopt(dd, dw)
        adopted[controller] = pick["overrides"] if take else default["overrides"]
        decisions[controller] = {"pick": pick["config_id"], "default": default["config_id"], "delay_diff": dd, "delay_se": se_d, "wait_diff": dw, "wait_se": se_w, "adopted": take}
    global_settings, per_controller = frozen_settings(adopted, defaults)
    frozen = {"extends": "design_base.yaml", "frozen": {"backend": args.backend, "date": datetime.date.today().isoformat(), "config": config, "rule": record["rule"], "selection_seeds": base["seeds"],
                                                       "confirmation_seeds": confirm_seeds, "selection_sha256": record["selection_summary_sha256"], "budget": base["sweep"].get("budget")}}
    if global_settings:
        frozen.update(global_settings)
    if per_controller:
        frozen["per_controller"] = per_controller
    out = Path("configs") / ("frozen_%s.yaml" % args.backend)
    out.write_text("# Frozen calibration parameters for the %s backend. Generated by freeze_calibration.py from %s.\n# Do not edit by hand: a change is a deviation and must be recorded (docs/preregistration_calibration.md).\n%s" % (args.backend, config, yaml.safe_dump(frozen, sort_keys=False)))

    lines = ["# Freeze report (%s)" % args.backend, "", "Rule: %s." % record["rule"], "Selection seeds: %s. Confirmation seeds: %d new seeds (%s-%s)." % (", ".join(map(str, base["seeds"])), len(confirm_seeds), confirm_seeds[0], confirm_seeds[-1]), "",
             "## Picks and decisions", "", "| controller | default | pick | delay pick-default (s) | max wait pick-default | adopted |", "|---|---|---|---|---|---|"]
    for controller, d in decisions.items():
        lines.append("| %s | %s | %s | %+.3f ± %.3f | %+.4f ± %.4f | %s |" % (controller, d["default"], d["pick"], d["delay_diff"], d["delay_se"], d["wait_diff"], d["wait_se"], "yes" if d["adopted"] else "no (kept default)"))
    lines += ["", "## Frozen settings", "", "```yaml", yaml.safe_dump({k: v for k, v in frozen.items() if k in ("signal", "per_controller")}, sort_keys=False).rstrip(), "```", ""]
    if sens:
        lines += ["## EFPB delta sensitivity (other efpb parameters at the picked values; confirmation seeds)", "", "| delta | person delay (s) | max normalised wait | starvation violations (surrogate) / collisions (SUMO) | max wait vs picked |", "|---|---|---|---|---|"]
        for delta, cid in sens:
            row = conf_by_id[cid]
            dw, se = paired(rows, picks["efpb"], cid, "max_norm_wait")
            lines.append("| %s | %.3f | %.4f | %.2f | %+.4f ± %.4f |" % (delta, float(row["person_delay_s"]), float(row["max_norm_wait"]), float(row.get("starvation_violations", row.get("collisions_total", 0))), dw, se))
        lines.append("")
    lines += ["## Confirmation results", "", "| config | controller | person delay (s) | max normalised wait | worst scenario |", "|---|---|---|---|---|"]
    for cid, row in sorted(conf_by_id.items()):
        lines.append("| %s | %s | %.3f | %.4f | %.3f |" % (cid, row["controller"], float(row["person_delay_s"]), float(row["max_norm_wait"]), float(row["worst_scenario_max_norm_wait"])))
    (root / "freeze_report.md").write_text("\n".join(lines) + "\n")
    print("wrote", out, "and", root / "freeze_report.md")


if __name__ == "__main__":
    main()
