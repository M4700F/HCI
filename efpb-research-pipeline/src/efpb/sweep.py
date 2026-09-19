"""Calibration sweep: controller parameter grids on calibration-only scenarios and seeds, summarised as Pareto tables.

The sweep only measures and suggests. It never edits the intersection config; freezing parameters is a reviewed decision.
"""
from __future__ import annotations

import copy
import csv
import itertools
import json
import multiprocessing
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import load_config, sha256_json, write_json
from .sim import make_manifest, run_one

PROTECTED_CONFIGS = ("confirmatory_core.yaml", "confirmatory.yaml", "robustness.yaml", "ablations.yaml", "stress.yaml", "sumo_matrix.yaml", "sumo_emergency.yaml")
# Parameters the research plan asks to select on calibration data, and the values used when a grid leaves them out.
DELTA_CURVE_KEYS = ("controller.debt_kappa", "controller.debt_eta", "controller.switch_cost", "controller.horizon_s", "signal.service_duration_s")


# Parameters a config may omit; the omitted value is the current behaviour.
IMPLICIT_DEFAULTS = {"signal.fixed_timing": "static"}


def get_path(config: Dict[str, Any], dotted: str) -> Any:
    node = config
    try:
        for part in dotted.split("."):
            node = node[part]
    except KeyError:
        if dotted in IMPLICIT_DEFAULTS:
            return IMPLICIT_DEFAULTS[dotted]
        raise
    return node


def set_path(config: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = config
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value


def scaled_splits(splits: Dict[str, int], base_cycle: int, cycle: int) -> Dict[str, int]:
    """Fixed-time splits kept proportional when the cycle length changes; the largest split absorbs rounding."""
    scaled = {phase: int(round(value * cycle / float(base_cycle))) for phase, value in splits.items()}
    scaled[max(scaled, key=scaled.get)] += cycle - sum(scaled.values())
    if min(scaled.values()) < 1:
        raise ValueError("cycle %d s leaves a phase without time: %s" % (cycle, scaled))
    return scaled


def apply_overrides(base: Dict[str, Any], overrides: Dict[str, Any], config_id: str) -> Dict[str, Any]:
    config = copy.deepcopy(base)
    for dotted, value in overrides.items():
        set_path(config, dotted, value)
    if "signal.fixed_cycle_s" in overrides:
        # scale by the splits' own total, which is not necessarily the config's fixed_cycle_s (the calibrated plan may be 37 s)
        config["signal"]["fixed_splits_s"] = scaled_splits(base["signal"]["fixed_splits_s"], sum(base["signal"]["fixed_splits_s"].values()), int(overrides["signal.fixed_cycle_s"]))
    config["experiment_id"] = "%s__%s" % (base["experiment_id"], config_id)
    config.pop("config_hash", None)
    config["config_hash"] = sha256_json(config)
    return config


def expand_grid(base: Dict[str, Any], controller: str, grid: Any, budget: Optional[int] = None) -> List[Dict[str, Any]]:
    """All parameter combinations for one controller, plus the current defaults if the grids do not contain them.

    `grid` is one grid or a list of grids (their union is used); every combination names every swept parameter.
    """
    grids = grid if isinstance(grid, list) else [grid or {}]
    keys = sorted({key for item in grids for key in item})
    defaults = {key: get_path(base, key) for key in keys}
    combos = []
    for item in grids:
        item_keys = sorted(item)
        for values in itertools.product(*(item[key] for key in item_keys)):
            overrides = dict(defaults)
            overrides.update(zip(item_keys, values))
            if overrides.get("controller.debt_kappa") == 0 and "controller.debt_eta" in overrides:
                overrides["controller.debt_eta"] = base["controller"]["debt_eta"]  # eta has no effect when kappa is 0
            if overrides not in combos:
                combos.append(overrides)
    if defaults not in combos:
        combos.append(defaults)
    if budget and len(combos) > budget:
        rng = random.Random(0)
        others = [combo for combo in combos if combo != defaults]
        combos = [defaults] + rng.sample(others, budget - 1)
    return [{"config_id": "%s__%03d" % (controller, index), "controller": controller, "overrides": combo, "is_default": combo == defaults} for index, combo in enumerate(combos)]


def build_configs(base: Dict[str, Any]) -> List[Dict[str, Any]]:
    spec = base["sweep"]
    configs: List[Dict[str, Any]] = []
    for controller, grid in spec["controllers"].items():
        configs += expand_grid(base, controller, grid, spec.get("budget"))
    return configs


def check_calibration_only(base: Dict[str, Any]) -> None:
    """Refuse to tune on the seeds or scenarios of the confirmatory, robustness, ablation or SUMO experiments."""
    directory = Path(base["_config_path"]).parent
    seeds, scenarios = set(base["seeds"]), {item["id"] for item in base["scenarios"]}
    for name in PROTECTED_CONFIGS:
        path = directory / name
        if not path.exists():
            continue
        other = load_config(str(path))
        shared_seeds = seeds & set(other.get("seeds", []))
        shared_scenarios = scenarios & {item["id"] for item in other.get("scenarios", [])}
        if shared_seeds or shared_scenarios:
            raise SystemExit("Calibration must not reuse %s seeds/scenarios: %s %s" % (name, sorted(shared_seeds), sorted(shared_scenarios)))


def check_config_table(configs: List[Dict[str, Any]], output_root: str) -> None:
    """A stored run is identified by its config id only, so an output folder must not be reused with another configuration set."""
    path = Path(output_root) / "configs.json"
    table = {item["config_id"]: item["overrides"] for item in configs}
    if path.exists() and json.loads(path.read_text()) != table:
        raise SystemExit("%s was made with a different configuration set; move it aside before running this sweep." % output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n")


_WORKER: Dict[str, Any] = {}


def _init_worker(base: Dict[str, Any], configs: List[Dict[str, Any]], output_root: str) -> None:
    _WORKER.update(base=base, configs={item["config_id"]: item for item in configs}, root=output_root, manifests={})


def _run_job(job: Tuple[str, str, int]) -> str:
    config_id, scenario_id, seed = job
    spec = _WORKER["configs"][config_id]
    scenario = next(item for item in _WORKER["base"]["scenarios"] if item["id"] == scenario_id)
    manifests = _WORKER["manifests"]
    if (scenario_id, seed) not in manifests:  # same demand for every configuration (common random numbers)
        manifests[(scenario_id, seed)] = make_manifest(_WORKER["base"], scenario, seed)
    config = apply_overrides(_WORKER["base"], spec["overrides"], config_id)
    run_one(config, scenario, spec["controller"], seed, str(Path(_WORKER["root"]) / "runs"), manifests[(scenario_id, seed)], lean=True)
    return config_id


def run_sweep(base: Dict[str, Any], configs: List[Dict[str, Any]], output_root: str, workers: int) -> None:
    jobs = [(item["config_id"], scenario["id"], int(seed)) for item in configs for scenario in base["scenarios"] for seed in base["seeds"]]
    if workers <= 1:
        _init_worker(base, configs, output_root)
        for index, job in enumerate(jobs, start=1):
            _run_job(job)
            if index % 200 == 0:
                print("  %d / %d runs" % (index, len(jobs)), flush=True)
        return
    with multiprocessing.Pool(workers, initializer=_init_worker, initargs=(base, configs, output_root)) as pool:
        for index, _ in enumerate(pool.imap_unordered(_run_job, jobs, chunksize=4), start=1):
            if index % 200 == 0:
                print("  %d / %d runs" % (index, len(jobs)), flush=True)


def derived_metrics(metrics: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, float]:
    """Person delay (occupancy-weighted mean wait of the people served) and the largest wait relative to its limit."""
    occupancy = float(base["demand"]["occupancy_mean"])
    ref_p, ref_v = float(base["controller"]["ped_wait_limit_s"]), float(base["controller"]["vehicle_wait_limit_s"])
    # waits cover everyone who arrived after warm-up, including people still queued at the end (their wait so far)
    people = metrics["requested_p"] + occupancy * metrics["requested_v"]
    delay = metrics["ped_mean_wait_s"] * metrics["requested_p"] + occupancy * metrics["veh_mean_wait_s"] * metrics["requested_v"]
    return {
        "person_delay_s": delay / max(1.0, people),
        "max_norm_wait": max(metrics["ped_max_wait_s"] / ref_p, metrics["veh_max_wait_s"] / ref_v),
        "starvation_violations": float(metrics["starvation_violations"]),
        "ped_mean_wait_s": metrics["ped_mean_wait_s"],
        "veh_mean_wait_s": metrics["veh_mean_wait_s"],
        "phase_switches": float(metrics["phase_switches"]),
        "clearance_share": metrics["clearance_steps"] / float(base["evaluation_s"]),
    }


def collect(base: Dict[str, Any], configs: List[Dict[str, Any]], output_root: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Per-run rows and per-configuration summaries (seeds averaged within a scenario, then scenarios weighted equally)."""
    by_id = {item["config_id"]: item for item in configs}
    prefix = base["experiment_id"] + "__"
    rows = []
    for path in sorted(Path(output_root, "runs").glob("**/run_summary.json")):
        metrics = json.loads(path.read_text())["metrics"]
        config_id = metrics["experiment_id"][len(prefix):]
        if config_id in by_id:
            rows.append(dict(config_id=config_id, controller=metrics["controller"], scenario_id=metrics["scenario_id"], seed=metrics["seed"], **derived_metrics(metrics, base)))
    expected = len(base["scenarios"]) * len(base["seeds"])
    keys = ["person_delay_s", "max_norm_wait", "starvation_violations", "ped_mean_wait_s", "veh_mean_wait_s", "phase_switches", "clearance_share"]
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
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
        for dotted, value in by_id[config_id]["overrides"].items():
            summary["p:" + dotted] = value
        summaries.append(summary)
    add_paired_differences(rows, summaries)
    return rows, summaries


def add_paired_differences(rows: List[Dict[str, Any]], summaries: List[Dict[str, Any]]) -> None:
    """Difference to the same controller's default configuration on identical demand (same scenario and seed), with its standard error."""
    by_config: Dict[str, Dict[Tuple[str, int], Dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_config[row["config_id"]][(row["scenario_id"], row["seed"])] = row
    defaults = {row["controller"]: row["config_id"] for row in summaries if row["is_default"]}
    for summary in summaries:
        reference = by_config[defaults[summary["controller"]]] if summary["controller"] in defaults else None
        for key, name in (("person_delay_s", "delay"), ("max_norm_wait", "maxwait")):
            if reference is None:
                summary["d_%s_vs_default" % name], summary["d_%s_se" % name] = "", ""
                continue
            diffs = [item[key] - reference[pair][key] for pair, item in by_config[summary["config_id"]].items()]
            summary["d_%s_vs_default" % name] = statistics.mean(diffs)
            summary["d_%s_se" % name] = statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else 0.0


def pareto_front(points: Sequence[Tuple[float, float]]) -> List[int]:
    """Indices of points not dominated when both coordinates are minimised (ties keep both)."""
    front = []
    for i, (x, y) in enumerate(points):
        if not any((x2 <= x and y2 <= y) and (x2 < x or y2 < y) for j, (x2, y2) in enumerate(points) if j != i):
            front.append(i)
    return front


def knee_index(points: Sequence[Tuple[float, float]]) -> Optional[int]:
    """Point farthest from the chord between the first and last point, after scaling both axes to 0-1."""
    if len(points) < 3:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    if max(xs) == min(xs) or max(ys) == min(ys):
        return None
    norm = [((x - min(xs)) / (max(xs) - min(xs)), (y - min(ys)) / (max(ys) - min(ys))) for x, y in points]
    (x0, y0), (x1, y1) = norm[0], norm[-1]
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length == 0:
        return None
    distances = [abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / length for x, y in norm]
    return max(range(len(points)), key=lambda i: distances[i])


def delta_curve(base: Dict[str, Any], summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """EFPB configurations that differ from the defaults only in delta."""
    curve = []
    for row in summaries:
        if row["controller"] != "efpb" or "p:controller.delta" not in row:
            continue
        if all(row.get("p:" + key, get_path(base, key)) == get_path(base, key) for key in DELTA_CURVE_KEYS):
            curve.append(row)
    return sorted(curve, key=lambda row: row["p:controller.delta"])


def write_outputs(base: Dict[str, Any], configs: List[Dict[str, Any]], rows: List[Dict[str, Any]], summaries: List[Dict[str, Any]], output_root: str) -> Dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "run_metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    fields = sorted({key for row in summaries for key in row}, key=lambda key: (key.startswith("p:"), key))
    with (root / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(summaries, key=lambda row: row["config_id"]))
    points = [(row["person_delay_s"], row["max_norm_wait"]) for row in summaries]
    overall = {summaries[i]["config_id"] for i in pareto_front(points)}
    per_controller: Dict[str, List[str]] = {}
    for controller in sorted({row["controller"] for row in summaries}):
        members = [row for row in summaries if row["controller"] == controller]
        per_controller[controller] = [members[i]["config_id"] for i in pareto_front([(row["person_delay_s"], row["max_norm_wait"]) for row in members])]
    curve = delta_curve(base, summaries)
    knee = knee_index([(row["person_delay_s"], row["max_norm_wait"]) for row in curve])
    result = {
        "status": "suggestion_only_not_frozen",
        "note": "Nothing here changes configs/intersection.yaml. Review the curves, then freeze and preregister parameters yourself.",
        "seeds": base["seeds"], "scenarios": [item["id"] for item in base["scenarios"]], "configurations": len(configs), "runs": len(rows),
        "pareto_all_configurations": sorted(overall), "pareto_per_controller": per_controller,
        "delta_curve": [{"delta": row["p:controller.delta"], "person_delay_s": row["person_delay_s"], "max_norm_wait": row["max_norm_wait"], "starvation_violations": row["starvation_violations"]} for row in curve],
        "delta_knee_suggestion": curve[knee]["p:controller.delta"] if knee is not None else None,
    }
    write_json(str(root / "pareto.json"), result)
    (root / "report.md").write_text(render_report(base, summaries, result))
    plot_pareto(summaries, overall, root / "pareto.png")
    return result


def fmt(value: Any) -> str:
    return ("%.3f" % value) if isinstance(value, float) else str(value)


def render_report(base: Dict[str, Any], summaries: List[Dict[str, Any]], result: Dict[str, Any]) -> str:
    lines = ["# Calibration sweep report", "", "**Suggestions only. Nothing was frozen.** Values come from calibration scenarios and seeds only, on the surrogate backend.", "",
             "- Scenarios: %s" % ", ".join(result["scenarios"]), "- Seeds: %s" % ", ".join(str(seed) for seed in result["seeds"]),
             "- Configurations: %d, runs: %d" % (result["configurations"], result["runs"]),
             "- Person delay = occupancy-weighted mean wait of the people served; max normalised wait = largest wait / its limit. Scenarios are weighted equally.",
             "- `d_maxwait_vs_default` / `d_maxwait_se`: paired difference to the same controller's default configuration on identical demand, and its standard error. A difference under about 2 standard errors is not distinguishable from seed noise. `summary.csv` has the same columns for person delay.",
             "- A best value on the edge of a swept grid means the grid should be widened before the value is trusted.", ""]
    counts = defaultdict(int)
    for row in summaries:
        counts[row["controller"]] += 1
    lines += ["## Configurations per controller (parameter-selection budget)", ""] + ["- %s: %d" % (name, count) for name, count in sorted(counts.items())] + [""]
    columns = ["config_id", "person_delay_s", "max_norm_wait", "d_maxwait_vs_default", "d_maxwait_se", "worst_scenario_max_norm_wait", "starvation_violations", "phase_switches", "clearance_share"]
    for controller, ids in result["pareto_per_controller"].items():
        members = sorted((row for row in summaries if row["config_id"] in ids), key=lambda row: row["person_delay_s"])
        params = sorted({key for row in members for key in row if key.startswith("p:")})
        lines += ["## %s: non-dominated configurations" % controller, "", "| " + " | ".join(columns + params) + " |", "|" + "---|" * (len(columns) + len(params))]
        for row in members:
            lines.append("| " + " | ".join(fmt(row.get(key, "")) for key in columns + params) + " |")
        default = next((row for row in summaries if row["controller"] == controller and row["is_default"]), None)
        if default:
            lines.append("")
            lines.append("Current defaults (%s): person delay %s, max normalised wait %s, starvation violations %s." % (default["config_id"], fmt(default["person_delay_s"]), fmt(default["max_norm_wait"]), fmt(default["starvation_violations"])))
        lines.append("")
    if result["delta_curve"]:
        lines += ["## EFPB delta sensitivity (other parameters at their defaults)", "", "| delta | person delay (s) | max normalised wait | starvation violations |", "|---|---|---|---|"]
        for row in result["delta_curve"]:
            lines.append("| %s | %s | %s | %s |" % (row["delta"], fmt(row["person_delay_s"]), fmt(row["max_norm_wait"]), fmt(row["starvation_violations"])))
        lines += ["", "Chord-knee suggestion for delta: %s. This is a starting point for judgement, not a selection." % result["delta_knee_suggestion"], ""]
    lines += ["## Limits", "", "- Surrogate backend; the plan also calibrates the delay predictor against SUMO.",
              "- Person delay covers people served before the end of the run; people still waiting are not counted.",
              "- Parameters that are safety timings (minimum green, yellow, all-red) are not swept.",
              "- equal_bargaining has no tunable parameter in this sweep; fixed_time is tuned only through its cycle length.", ""]
    return "\n".join(lines)


def plot_pareto(summaries: List[Dict[str, Any]], overall: set, path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    colors = {"fixed_time": "#7f7f7f", "efficiency": "#2a6f97", "equal_bargaining": "#5aa469", "efpb": "#c44536"}
    figure, axis = plt.subplots(figsize=(8, 5.5))
    for controller in sorted({row["controller"] for row in summaries}):
        members = [row for row in summaries if row["controller"] == controller]
        axis.scatter([row["person_delay_s"] for row in members], [row["max_norm_wait"] for row in members], s=18, alpha=0.45, color=colors.get(controller), label=controller)
        front = [row for row in members if row["config_id"] in overall]
        axis.scatter([row["person_delay_s"] for row in front], [row["max_norm_wait"] for row in front], s=60, facecolors="none", edgecolors="black")
        defaults = [row for row in members if row["is_default"]]
        axis.scatter([row["person_delay_s"] for row in defaults], [row["max_norm_wait"] for row in defaults], s=70, marker="x", color="black")
    axis.set_xlabel("mean person delay (s)")
    axis.set_ylabel("max wait / limit")
    axis.set_title("Calibration sweep: circled = non-dominated overall, x = current defaults")
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=130)
    plt.close(figure)
