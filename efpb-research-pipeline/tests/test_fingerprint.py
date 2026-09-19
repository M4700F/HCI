import copy
import json

import pytest

from efpb.config import load_config, result_fingerprint
from efpb.sim import make_manifest, run_one
from test_timing import load_runner

ITEM = {"id": "K_MM", "pedestrian_demand": "M", "vehicle_demand": "M", "process": "poisson_approximation", "sensor_profile": "nominal", "emergency": False}


def test_fingerprint_ignores_names_and_run_lists_but_not_settings():
    core, robustness = load_config("configs/experiments/confirmatory_core.yaml"), load_config("configs/experiments/robustness.yaml")
    base = result_fingerprint(core, ITEM, "efpb", 1)
    assert base == result_fingerprint(robustness, ITEM, "efpb", 1)  # same settings, other experiment id, seeds and scenarios
    changed = copy.deepcopy(core)
    changed["controller"]["delta"] = 0.2
    other_signal = copy.deepcopy(core)
    other_signal["signal"]["fixed_cycle_s"] = 45
    other_length = dict(core, evaluation_s=core["evaluation_s"] + 1)
    for other in (changed, other_signal, other_length):
        assert result_fingerprint(other, ITEM, "efpb", 1) != base
    assert result_fingerprint(core, dict(ITEM, vehicle_demand="H"), "efpb", 1) != base
    assert result_fingerprint(core, ITEM, "efficiency", 1) != base and result_fingerprint(core, ITEM, "efpb", 2) != base


def test_surrogate_reuses_matching_runs_and_refuses_changed_settings(tmp_path):
    cfg = load_config("configs/experiments/smoke.yaml")
    item = cfg["scenarios"][0]
    manifest = make_manifest(cfg, item, 1)
    first = run_one(cfg, item, "efpb", 1, str(tmp_path), manifest, lean=True)
    again = run_one(cfg, item, "efpb", 1, str(tmp_path), manifest, lean=True)
    assert again["metrics"]["config_fingerprint"] == first["metrics"]["config_fingerprint"]
    changed = copy.deepcopy(cfg)
    changed["controller"]["delta"] = 0.2
    with pytest.raises(RuntimeError, match="different configuration"):
        run_one(changed, item, "efpb", 1, str(tmp_path), manifest, lean=True)
    renamed = dict(cfg, experiment_id="smoke")  # a name alone does not change the fingerprint
    assert run_one(renamed, item, "efpb", 1, str(tmp_path), manifest, lean=True)["metrics"]["config_fingerprint"] == first["metrics"]["config_fingerprint"]


def test_sumo_fingerprint_and_reuse_check(tmp_path):
    runner = load_runner()
    config = "configs/experiments/sumo_emergency.yaml"
    base = runner.run_fingerprint(config, "efpb", 9001, "S1_balanced")
    assert base == runner.run_fingerprint(config, "efpb", 9001, "S1_balanced")
    assert base != runner.run_fingerprint(config, "efficiency", 9001, "S1_balanced")
    assert base != runner.run_fingerprint(config, "efpb", 9002, "S1_balanced")
    assert base != runner.run_fingerprint(config, "efpb", 9001, "S2_pedestrian_heavy")
    other = tmp_path / "other.yaml"
    other.write_text("extends: %s\ncontroller:\n  delta: 0.2\n" % (load_config(config)["_config_path"]))
    assert base != runner.run_fingerprint(str(other), "efpb", 9001, "S1_balanced")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"config_fingerprint": base}))
    runner.check_reusable(metrics, base)
    with pytest.raises(SystemExit):
        runner.check_reusable(metrics, "different")


def test_sumo_files_hash_covers_input_files_only(tmp_path):
    runner = load_runner()
    (tmp_path / "run.sumocfg").write_text('<configuration><input><net-file value="net.xml"/><route-files value="routes.xml"/>'
                                          '<additional-files value="tls.xml,extra.xml"/></input></configuration>')
    for name in ("net.xml", "routes.xml", "tls.xml", "extra.xml"):
        (tmp_path / name).write_text(name)
    before = runner.sumo_files_hash(str(tmp_path), "run.sumocfg")
    (tmp_path / "netstate.xml").write_text("written by SUMO during a run")  # an output file must not change the hash
    assert runner.sumo_files_hash(str(tmp_path), "run.sumocfg") == before
    for name in ("routes.xml", "extra.xml", "run.sumocfg"):
        old = (tmp_path / name).read_text()
        (tmp_path / name).write_text(old + " ")
        assert runner.sumo_files_hash(str(tmp_path), "run.sumocfg") != before, name
        (tmp_path / name).write_text(old)
    assert runner.sumo_files_hash(str(tmp_path), "run.sumocfg") == before


def test_sumo_fingerprint_is_stable_across_runs():
    runner = load_runner()
    assert runner.sumo_files_hash() == runner.sumo_files_hash()  # the real sumo/actual folder, whatever outputs it holds


class FakeTraci:
    """Stands in for traci: reports the options of the SUMO it 'connected' to."""

    def __init__(self, options):
        import types

        self.options, self.closed, self.started = options, False, None
        self.simulation = types.SimpleNamespace(getOption=lambda name: self.options[name])

    def start(self, command, port=None):
        self.started = (command, port)

    def close(self):
        self.closed = True


def test_sumo_start_checks_that_it_reached_its_own_instance(tmp_path):
    runner = load_runner()
    log = tmp_path / "sumo.log"
    own = FakeTraci({"seed": "9001", "log": str(log), "scale": "0.389485"})
    runner.start_sumo(own, ["sumo"], 0, log, 9001, 0.389485)
    assert own.started == (["sumo"], None) and not own.closed
    other = FakeTraci({"seed": "9001", "log": str(tmp_path / "other.log"), "scale": "0.389485"})  # another run's SUMO
    with pytest.raises(RuntimeError, match="different SUMO instance"):
        runner.start_sumo(other, ["sumo"], 0, log, 9001, 0.389485)
    assert other.closed


def test_per_controller_settings_are_merged_and_only_affect_their_controller():
    from efpb.config import effective_config

    cfg = load_config("configs/design_base.yaml")
    cfg["per_controller"] = {"efpb": {"controller": {"delta": 0.2}, "signal": {"service_duration_s": 35}}}
    efpb, other = effective_config(cfg, "efpb"), effective_config(cfg, "efficiency")
    assert efpb["controller"]["delta"] == 0.2 and efpb["signal"]["service_duration_s"] == 35 and "per_controller" not in efpb
    assert other["controller"]["delta"] == 0.05 and other["signal"]["service_duration_s"] == 25
    assert result_fingerprint(cfg, ITEM, "efficiency", 1) == result_fingerprint(load_config("configs/design_base.yaml"), ITEM, "efficiency", 1)  # other controllers' runs stay valid
    assert result_fingerprint(cfg, ITEM, "efpb", 1) != result_fingerprint(load_config("configs/design_base.yaml"), ITEM, "efpb", 1)


def test_design_base_adds_the_stress_levels_without_changing_the_old_ones():
    old, new = load_config("configs/intersection.yaml"), load_config("configs/design_base.yaml")
    for table in ("pedestrian_rates_per_s", "vehicle_rates_per_s"):
        assert all(new["demand"][table][k] == v for k, v in old["demand"][table].items())
    assert new["demand"]["vehicle_rates_per_s"]["S"] == 1.5 * old["demand"]["vehicle_rates_per_s"]["X"]
    assert new["demand"]["vehicle_rates_per_s"]["O"] == 2.0 * old["demand"]["vehicle_rates_per_s"]["X"]
