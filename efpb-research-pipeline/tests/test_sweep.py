import json

import pytest

from efpb.config import load_config
from efpb.sim import CONTROLLERS, make_manifest, run_one
from efpb.sweep import apply_overrides, build_configs, check_config_table, check_calibration_only, collect, expand_grid, knee_index, pareto_front, run_sweep, scaled_splits, write_outputs

SWEEP = "configs/experiments/calibration_sweep.yaml"


def test_lean_runs_match_full_runs(tmp_path):
    cfg = load_config("configs/experiments/smoke.yaml")
    for scenario in cfg["scenarios"]:  # includes the emergency scenario
        manifest = make_manifest(cfg, scenario, 1)
        for controller in CONTROLLERS:
            full = run_one(cfg, scenario, controller, 1, str(tmp_path / "full"), manifest)["metrics"]
            lean = run_one(cfg, scenario, controller, 1, str(tmp_path / "lean"), manifest, lean=True)["metrics"]
            full.pop("wall_time_s"), lean.pop("wall_time_s")
            assert full == lean
    assert not list((tmp_path / "lean").glob("**/decisions.jsonl"))


def test_scaled_splits_keep_the_cycle_length():
    for cycle in (60, 90, 120):
        splits = scaled_splits({"P_ALL": 20, "V_NS": 35, "V_EW": 35}, 90, cycle)
        assert sum(splits.values()) == cycle
    assert scaled_splits({"P_ALL": 20, "V_NS": 35, "V_EW": 35}, 90, 90) == {"P_ALL": 20, "V_NS": 35, "V_EW": 35}


def test_grid_contains_defaults_and_drops_irrelevant_eta():
    base = load_config(SWEEP)
    configs = build_configs(base)
    efpb = [item for item in configs if item["controller"] == "efpb"]
    assert len(efpb) == base["sweep"]["budget"] == 30  # the tuning budget caps the large efpb space; defaults are always included
    assert sum(item["is_default"] for item in efpb) == 1
    assert all(item["overrides"]["controller.debt_eta"] == base["controller"]["debt_eta"] for item in efpb if item["overrides"]["controller.debt_kappa"] == 0)
    assert len({item["config_id"] for item in configs}) == len(configs)
    capped = expand_grid(base, "efpb", base["sweep"]["controllers"]["efpb"], budget=10)
    assert len(capped) == 10 and capped[0]["is_default"]


def test_overrides_change_only_the_named_parameters():
    base = load_config(SWEEP)
    changed = apply_overrides(base, {"controller.delta": 0.2}, "efpb__000")
    assert changed["controller"]["delta"] == 0.2 and base["controller"]["delta"] == 0.05
    assert changed["experiment_id"] == "calibration_sweep__efpb__000" and changed["config_hash"] != base["config_hash"]


def test_calibration_refuses_protected_seeds_and_scenarios():
    base = load_config(SWEEP)
    check_calibration_only(base)
    base["seeds"] = base["seeds"] + [1001]
    with pytest.raises(SystemExit):
        check_calibration_only(base)


def test_pareto_and_knee():
    assert pareto_front([(1, 5), (2, 3), (3, 3), (4, 1), (2, 6)]) == [0, 1, 3]
    assert knee_index([(0, 10), (1, 2), (10, 1)]) == 1
    assert knee_index([(0, 1), (1, 1), (2, 1)]) is None


def test_small_sweep_end_to_end(tmp_path):
    base = load_config(SWEEP)
    base.update(warmup_s=20, evaluation_s=120, scenarios=base["scenarios"][:2], seeds=[301, 302])
    base["sweep"]["controllers"] = {"fixed_time": {"signal.fixed_cycle_s": [60, 90]}, "equal_bargaining": {}, "efpb": {"controller.delta": [0, 0.05, 0.2]}}
    configs = build_configs(base)
    run_sweep(base, configs, str(tmp_path), workers=1)
    rows, summaries = collect(base, configs, str(tmp_path))
    assert len(rows) == len(configs) * 2 * 2 and len(summaries) == len(configs)
    result = write_outputs(base, configs, rows, summaries, str(tmp_path))
    assert result["status"] == "suggestion_only_not_frozen" and len(result["delta_curve"]) == 3
    assert {"summary.csv", "run_metrics.csv", "pareto.json", "report.md"} <= {p.name for p in tmp_path.iterdir()}
    assert "Nothing was frozen" in (tmp_path / "report.md").read_text()
    default = next(row for row in summaries if row["controller"] == "efpb" and row["is_default"])
    assert default["d_maxwait_vs_default"] == 0 and default["d_maxwait_se"] == 0
    assert load_config(SWEEP)["controller"]["delta"] == 0.05  # configs are never edited


def test_fixed_time_grids_are_merged_and_defaults_kept():
    base = load_config(SWEEP)
    configs = [item for item in build_configs(base) if item["controller"] == "fixed_time"]
    assert len(configs) == 6 + 8  # six static cycles plus eight demand-based cycles; the two families never coincide
    modes = {item["overrides"]["signal.fixed_timing"] for item in configs}
    assert modes == {"static", "demand_based"}
    assert sum(item["is_default"] for item in configs) == 1
    default = next(item for item in configs if item["is_default"])
    assert default["overrides"] == {"signal.fixed_timing": "demand_based", "signal.fixed_cycle_s": 37}  # the currently calibrated plan


def test_config_table_guard(tmp_path):
    base = load_config(SWEEP)
    configs = build_configs(base)
    check_config_table(configs, str(tmp_path))
    check_config_table(configs, str(tmp_path))  # same set again is fine
    with pytest.raises(SystemExit):
        check_config_table(configs[:-1], str(tmp_path))


def test_static_splits_scale_by_their_own_total_not_by_fixed_cycle_s():
    base = load_config(SWEEP)
    assert base["signal"]["fixed_cycle_s"] == 37 and sum(base["signal"]["fixed_splits_s"].values()) == 90  # the calibrated plan differs from the split total
    changed = apply_overrides(base, {"signal.fixed_timing": "static", "signal.fixed_cycle_s": 45}, "fixed_time__x")
    splits = changed["signal"]["fixed_splits_s"]
    assert sum(splits.values()) == 45 and min(splits.values()) >= 1
    assert abs(splits["V_NS"] - splits["V_EW"]) <= 1 and splits["P_ALL"] == 10  # proportional to 20:35:35
    with pytest.raises(ValueError):
        scaled_splits({"P_ALL": 20, "V_NS": 35, "V_EW": 35}, 90, 2)
