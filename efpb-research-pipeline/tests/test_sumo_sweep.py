import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from efpb.config import load_config
from efpb.sweep import build_configs, check_calibration_only

CONFIG = "configs/experiments/sumo_calibration.yaml"


def load_sweep():
    spec = importlib.util.spec_from_file_location("sweep_sumo_calibration", Path("sweep_sumo_calibration.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["sweep_sumo_calibration"] = module  # worker processes look the module up by name
    spec.loader.exec_module(module)
    return module


def test_calibration_seeds_and_scenarios_are_protected_from_the_pilot():
    base = load_config(CONFIG)
    check_calibration_only(base)
    confirm = base["sweep"]["confirm_seeds"]
    check_calibration_only(dict(base, seeds=confirm))
    assert not set(confirm) & set(base["seeds"])
    with pytest.raises(SystemExit):
        check_calibration_only(dict(base, seeds=base["seeds"] + [9001]))  # a pilot seed


def test_all_controllers_get_the_same_budget_cap():
    base = load_config(CONFIG)
    configs = build_configs(base)
    counts = {c: sum(1 for item in configs if item["controller"] == c) for c in base["sweep"]["controllers"]}
    assert all(n <= base["sweep"]["budget"] for n in counts.values()) and counts["efpb"] == base["sweep"]["budget"]
    assert all(sum(item["is_default"] for item in configs if item["controller"] == c) == 1 for c in counts)  # every controller keeps its default


def test_derived_metrics_count_everyone_including_the_unserved():
    sweep = load_sweep()
    base = load_config(CONFIG)
    metrics = {"pedestrian_served_virtual": 55, "pedestrian_unserved": 5, "vehicle_completed": 190, "vehicle_unfinished": 10, "pedestrian_wait_mean_s": 10.0, "vehicle_stop_time_all_mean_s": 5.0, "pedestrian_wait_max_s": 40.0,
               "vehicle_stopped_wait_max_s": 25.0, "vehicle_stopped_wait_p95_s": 18.0, "mean_vehicle_queue": 1.5, "phase_switches": 70, "clearance_steps": 180, "emergency_stops": 0, "collisions": 0}
    out = sweep.derived(metrics, base)
    assert out["person_delay_s"] == pytest.approx((60 * 10.0 + 1.3 * 200 * 5.0) / (60 + 1.3 * 200))
    assert out["max_norm_wait"] == 0.4 and out["clearance_share"] == 0.2


@pytest.mark.skipif(shutil.which("sumo") is None, reason="SUMO is not installed")
def test_small_sumo_sweep_end_to_end(tmp_path):
    sweep = load_sweep()
    base = load_config(CONFIG)
    base.update(warmup_s=20, evaluation_s=60, scenarios=base["scenarios"][:1], seeds=[301])
    base["sweep"]["controllers"] = {"fixed_time": [{"signal.fixed_timing": ["static"], "signal.fixed_cycle_s": [90]}, {"signal.fixed_timing": ["demand_based"], "signal.fixed_cycle_s": [37]}],
                                    "efficiency": {"controller.horizon_s": [30, 60]}}
    configs = build_configs(base)
    sweep.run_stage(base, configs, [301], str(tmp_path), workers=1)
    sweep.run_stage(base, configs, [301], str(tmp_path), workers=1)  # matching stored runs are reused without error
    rows, summaries = sweep.collect(base, configs, [301], str(tmp_path))
    assert len(rows) == len(configs) == len(summaries) == 4
    assert {row["controller"] for row in rows} == {"fixed_time", "efficiency"}
    default = next(row for row in summaries if row["is_default"] and row["controller"] == "efficiency")
    assert default["d_maxwait_vs_default"] == 0 and all(row["collisions"] == 0 for row in rows)
