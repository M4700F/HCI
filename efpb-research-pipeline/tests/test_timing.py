import pytest

from efpb.config import load_config
from efpb.sim import make_manifest, run_one
from efpb.timing import clearance_into, cycle_floor, demand_based_splits, flow_ratios, webster_cycle

SWEEP = "configs/experiments/calibration_sweep.yaml"


def scenario(cfg, sid):
    return next(item for item in cfg["scenarios"] if item["id"] == sid)


def test_floor_is_three_minimum_greens_plus_clearance():
    cfg = load_config(SWEEP)
    assert clearance_into(cfg["signal"]) == {"P_ALL": 3, "V_NS": 0, "V_EW": 4}
    assert cycle_floor(cfg) == 3 * 10 + 7


def test_demand_based_splits_fit_the_cycle_and_follow_demand():
    cfg = load_config(SWEEP)
    for cycle in (37, 45, 60, 90):
        for item in cfg["scenarios"]:
            splits = demand_based_splits(cfg, item, cycle)
            assert sum(splits.values()) == cycle
            assert splits["P_ALL"] >= 10 + 3 and splits["V_NS"] >= 10 and splits["V_EW"] >= 10 + 4
    ped_heavy, veh_heavy = demand_based_splits(cfg, scenario(cfg, "K_HL"), 60), demand_based_splits(cfg, scenario(cfg, "K_LH"), 60)
    assert ped_heavy["P_ALL"] > veh_heavy["P_ALL"] and veh_heavy["V_NS"] > ped_heavy["V_NS"]
    assert demand_based_splits(cfg, scenario(cfg, "K_MM"), 37) == {"P_ALL": 13, "V_NS": 10, "V_EW": 14}
    with pytest.raises(ValueError):
        demand_based_splits(cfg, scenario(cfg, "K_MM"), 36)


def test_webster_cycle_is_below_the_floor_at_light_demand_and_above_it_under_stress():
    cfg = load_config(SWEEP)
    light = [item for item in cfg["scenarios"] if item["id"] not in ("K_SS", "K_OO")]
    assert all(webster_cycle(cfg, item) < cycle_floor(cfg) for item in light)
    assert all(webster_cycle(cfg, scenario(cfg, sid)) > cycle_floor(cfg) for sid in ("K_SS", "K_OO"))  # near and over saturation want a longer cycle
    assert flow_ratios(cfg, scenario(cfg, "K_HH_burst"))["P_ALL"] > flow_ratios(cfg, scenario(cfg, "K_HH"))["P_ALL"]


def test_demand_based_fixed_time_uses_the_scenario_plan(tmp_path):
    cfg = load_config(SWEEP)
    cfg["signal"]["fixed_timing"], cfg["signal"]["fixed_cycle_s"] = "demand_based", 60
    cfg.update(warmup_s=20, evaluation_s=120)
    plans = {}
    for sid in ("K_HL", "K_LH"):
        item = scenario(cfg, sid)
        summary = run_one(cfg, item, "fixed_time", 301, str(tmp_path), make_manifest(cfg, item, 301))
        plans[sid] = summary["metrics"]["experiment_id"], sorted(tmp_path.glob("**/%s/**/resolved_config.json" % sid))
    import json
    split = {sid: json.loads(files[0].read_text())["signal"]["fixed_splits_s"] for sid, (_, files) in plans.items()}
    assert split["K_HL"] != split["K_LH"] and sum(split["K_HL"].values()) == 60


def load_runner():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("run_sumo_actual", Path("run_sumo_actual.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_approach_shares_shift_time_to_the_busier_vehicle_phase():
    runner = load_runner()
    shares = runner.route_approach_shares()
    assert set(shares) == set("NSEW") and abs(sum(shares.values()) - 1) < 1e-9
    cfg = load_config("configs/experiments/sumo_emergency.yaml")
    item = cfg["scenarios"][0]
    ratios = flow_ratios(cfg, item, shares)
    assert ratios["V_NS"] > ratios["V_EW"]  # approaches 1 and 2 carry more of the bundled demand than 3 and 4
    even, uneven = demand_based_splits(cfg, item, 60), demand_based_splits(cfg, item, 60, shares)
    assert sum(uneven.values()) == 60
    assert uneven["V_NS"] - uneven["V_EW"] > even["V_NS"] - even["V_EW"]


def test_pilot_config_uses_the_tuned_fixed_time_plan():
    signal = load_config("configs/experiments/sumo_emergency.yaml")["signal"]
    assert signal["fixed_timing"] == "demand_based" and signal["fixed_cycle_s"] == 37 and signal["fixed_cycle_s"] == cycle_floor(load_config("configs/experiments/sumo_emergency.yaml"))


def test_surrogate_experiment_configs_use_the_tuned_plan():
    for name in ("confirmatory_core", "confirmatory", "robustness", "ablations", "stress"):
        cfg = load_config("configs/experiments/%s.yaml" % name)
        assert cfg["signal"]["fixed_timing"] == "demand_based" and cfg["signal"]["fixed_cycle_s"] == cycle_floor(cfg), name
        assert cfg["frozen"]["backend"] == "surrogate" and cfg["per_controller"]["efpb"]["controller"]["debt_kappa"] == 4, name  # the frozen calibration is in force
    for name in ("calibration", "smoke", "benchmark"):  # the plain calibration, smoke and benchmark configs keep the untuned defaults
        assert load_config("configs/experiments/%s.yaml" % name)["signal"].get("fixed_timing", "static") == "static", name


def test_sensor_fallback_follows_the_tuned_plan_for_every_controller(tmp_path):
    import csv
    import json

    cfg = load_config("configs/experiments/robustness.yaml")
    cfg.update(warmup_s=20, evaluation_s=140)
    item = next(x for x in cfg["scenarios"] if x["sensor_profile"] == "degraded")
    for controller in ("efpb", "efficiency", "equal_bargaining", "fixed_time"):
        summary = run_one(cfg, item, controller, 301, str(tmp_path), make_manifest(cfg, item, 301))
        run_dir = next(tmp_path.glob("**/%s/301/*" % controller))
        signal = json.loads((run_dir / "resolved_config.json").read_text())["signal"]
        assert sum(signal["fixed_splits_s"].values()) == signal["fixed_cycle_s"] == 37
        phases = {row["phase"] for row in csv.DictReader((run_dir / "states.csv").open())}
        assert phases == {"P_ALL", "V_NS", "V_EW"}, (controller, phases)  # the fallback serves all three phases
