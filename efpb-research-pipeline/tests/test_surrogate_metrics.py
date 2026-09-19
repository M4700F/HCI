import json

import pytest

from efpb.config import load_config
from efpb.sim import SIM_VERSION, make_manifest, run_one


def smoke_run(tmp_path, controller="fixed_time"):
    cfg = load_config("configs/experiments/smoke.yaml")
    scenario = cfg["scenarios"][0]
    manifest = make_manifest(cfg, scenario, 1)
    return cfg, scenario, manifest, run_one(cfg, scenario, controller, 1, str(tmp_path), manifest)


def test_metrics_cover_the_evaluation_window(tmp_path):
    cfg, _, manifest, summary = smoke_run(tmp_path)
    metrics, warmup = summary["metrics"], cfg["warmup_s"]
    assert metrics["sim_version"] == SIM_VERSION
    assert metrics["requested_p"] == sum(1 for x in manifest["pedestrians"] if x["t"] >= warmup)
    assert metrics["requested_v"] == sum(1 for x in manifest["vehicles"] if x["t"] >= warmup)
    assert metrics["served_p"] <= metrics["requested_p"] and metrics["served_v"] <= metrics["requested_v"]
    for key in ("ped_throughput_h", "veh_throughput_h"):
        events = metrics[key] * cfg["evaluation_s"] / 3600.0
        assert abs(events - round(events)) < 1e-6


def test_controller_receives_the_scenario_arrival_rates(tmp_path):
    cfg, scenario, _, summary = smoke_run(tmp_path, "efpb")
    trace = json.loads(next((tmp_path).glob("**/decisions.jsonl")).read_text().splitlines()[0])
    assert trace["state"]["ped_arrival_rate"] == cfg["demand"]["pedestrian_rates_per_s"][scenario["pedestrian_demand"]]
    assert trace["state"]["veh_arrival_rate"] == cfg["demand"]["vehicle_rates_per_s"][scenario["vehicle_demand"]]


def test_stale_output_is_not_reused(tmp_path):
    cfg, scenario, manifest, summary = smoke_run(tmp_path)
    summary_path = next(tmp_path.glob("**/run_summary.json"))
    stale = json.loads(summary_path.read_text())
    stale["metrics"].pop("sim_version")
    summary_path.write_text(json.dumps(stale))
    with pytest.raises(RuntimeError):
        run_one(cfg, scenario, "fixed_time", 1, str(tmp_path), manifest)


def test_fractional_capacity_is_served_at_the_configured_rate():
    from efpb.sim import _serve_count

    credit = {"N": 0.0}
    assert sum(_serve_count(credit, "N", 0.8, 1000) for _ in range(100)) == 80  # 0.8 per second, not rounded up to 1
    credit = {"N": 0.0}
    assert sum(_serve_count(credit, "N", 1.0, 1000) for _ in range(100)) == 100
    credit = {"N": 0.0}
    assert [_serve_count(credit, "N", 0.8, 0) for _ in range(3)] == [0, 0, 0] and credit["N"] == 0.0  # no credit behind an empty queue
    assert _serve_count(credit, "N", 0.8, 5) == 0 and _serve_count(credit, "N", 0.8, 5) == 1


def test_saturated_run_serves_no_more_than_the_configured_capacity(tmp_path):
    cfg = load_config("configs/experiments/smoke.yaml")
    cfg.update(warmup_s=20, evaluation_s=300)
    cfg["demand"]["vehicle_rates_per_s"]["Q"] = 3.0  # far above capacity
    item = dict(cfg["scenarios"][0], id="Q", vehicle_demand="Q")
    metrics = run_one(cfg, item, "fixed_time", 1, str(tmp_path), make_manifest(cfg, item, 1), lean=True)["metrics"]
    # each approach is served 35 s of the default 90 s cycle at 0.8/s; the old rounded-up capacity of 1/s would allow 5,600 per hour
    ceiling = 4 * 0.8 * (35 / 90.0) * 3600
    assert 0.9 * ceiling < metrics["veh_throughput_h"] <= ceiling + 1
    assert metrics["veh_service_ratio"] < 0.5


def test_arrival_generator_reaches_rates_above_one_per_second():
    import random

    from efpb.sim import _arrival_count

    for rate in (0.3, 0.9, 1.5, 3.0):
        rng = random.Random(7)
        mean = sum(_arrival_count(rng, rate) for _ in range(20000)) / 20000.0
        assert abs(mean - rate) < 0.03, (rate, mean)


def test_people_still_queued_at_the_end_count_in_the_waits(tmp_path):
    cfg = load_config("configs/experiments/smoke.yaml")
    cfg.update(warmup_s=20, evaluation_s=300)
    cfg["demand"]["vehicle_rates_per_s"]["Q"] = 3.0  # far above capacity: a long queue is left at the end
    item = dict(cfg["scenarios"][0], id="Q", vehicle_demand="Q")
    metrics = run_one(cfg, item, "fixed_time", 1, str(tmp_path), make_manifest(cfg, item, 1), lean=True)["metrics"]
    assert metrics["unserved_v"] == metrics["requested_v"] - metrics["served_v"] > 300
    assert metrics["veh_max_wait_s"] > 200  # the oldest queued vehicle has waited most of the evaluation window
    assert metrics["starvation_violations"] > 0
