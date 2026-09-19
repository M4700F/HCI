import csv
from itertools import groupby

from efpb.cli import run_config
from efpb.sim import clearance_seconds

SIGNAL = {"yellow_s": 3, "all_red_s": 1}


def test_clearance_seconds():
    assert clearance_seconds("V_NS", "V_EW", SIGNAL) == 4
    assert clearance_seconds("V_EW", "V_NS", SIGNAL) == 4
    assert clearance_seconds("V_NS", "P_ALL", SIGNAL) == 3
    assert clearance_seconds("P_ALL", "V_EW", SIGNAL) == 0


def test_surrogate_shows_clearance_between_phases(tmp_path):
    run_config("configs/experiments/smoke.yaml", output_root=str(tmp_path), only_controllers=["fixed_time"])
    rows = list(csv.DictReader(next(tmp_path.glob("**/states.csv")).open()))
    runs = [len(list(group)) for flag, group in groupby(r["in_clearance"] == "True" for r in rows) if flag]
    assert runs and max(runs) <= 4
    assert 4 in runs and 3 in runs  # V_NS -> V_EW, then V_EW -> P_ALL, in the fixed cycle
