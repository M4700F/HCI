from efpb.selection import adopt, frozen_settings, nest, pick_closest_to_ideal


def rows(*points):
    return [{"config_id": "c%d" % i, "person_delay_s": d, "max_norm_wait": w} for i, (d, w) in enumerate(points)]


def test_pick_is_closest_to_the_ideal_point_and_scale_free():
    data = rows((10, 1.0), (12, 0.5), (20, 0.4), (11, 0.9))
    assert pick_closest_to_ideal(data)["config_id"] == "c1"  # a good compromise beats the extremes
    scaled = [dict(r, person_delay_s=r["person_delay_s"] * 1000) for r in data]
    assert pick_closest_to_ideal(scaled)["config_id"] == "c1"  # the units of an objective do not change the pick


def test_pick_ties_and_exclusions():
    tied = rows((10, 0.5), (10, 0.5))
    assert pick_closest_to_ideal(tied)["config_id"] == "c0"
    data = rows((10, 1.0), (12, 0.5), (20, 0.4))
    data[1]["collisions_total"] = 2
    picked = pick_closest_to_ideal(data, exclude=lambda r: r.get("collisions_total", 0) > 0)
    assert picked["config_id"] != "c1"
    assert pick_closest_to_ideal(data, exclude=lambda r: True)  # everything excluded falls back to the full set


def test_an_exact_tie_keeps_the_default():
    data = rows((10, 0.5), (10, 0.5), (10, 0.5))
    data[2]["is_default"] = True
    assert pick_closest_to_ideal(data)["config_id"] == "c2"
    data[2]["is_default"] = "True"  # values read back from a CSV are strings
    assert pick_closest_to_ideal(data)["config_id"] == "c2"


def test_adopt_unless_worse_in_both():
    assert adopt(-1.0, 0.2) and adopt(0.5, -0.1) and adopt(0.0, 0.0)
    assert not adopt(0.5, 0.1)


def test_frozen_settings_keep_only_changes_and_a_global_fixed_plan():
    defaults = {"fixed_time": {"signal.fixed_timing": "demand_based", "signal.fixed_cycle_s": 37}, "efpb": {"controller.delta": 0.05, "controller.horizon_s": 60}}
    adopted = {"fixed_time": {"signal.fixed_timing": "demand_based", "signal.fixed_cycle_s": 45}, "efpb": {"controller.delta": 0.1, "controller.horizon_s": 60}}
    global_settings, per_controller = frozen_settings(adopted, defaults)
    assert global_settings == {"signal": {"fixed_timing": "demand_based", "fixed_cycle_s": 45}}
    assert per_controller == {"efpb": {"controller": {"delta": 0.1}}}
    assert nest("a.b.c", 1) == {"a": {"b": {"c": 1}}}
