from efpb.config import load_config
from efpb.controller import make_controller
from efpb.models import State


def cfg():
    return load_config("configs/experiments/smoke.yaml")


def make_state(**updates):
    values = dict(sim_time_s=50, current_phase="V_NS", phase_elapsed_s=20, ped_queue=10, veh_queue={"N": 2, "S": 2, "E": 8, "W": 8}, ped_max_wait_s=80, veh_max_wait_s=30, ped_mean_wait_s=40, veh_mean_wait_s=15, ped_arrival_rate=.05, veh_arrival_rate=.1)
    values.update(updates)
    return State(**values)


def test_efpb_is_deterministic():
    controller = make_controller("efpb", cfg()); first, trace1 = controller.decide(make_state(), "d1"); second, trace2 = controller.decide(make_state(), "d2")
    assert first.chosen.plan.candidate_id == second.chosen.plan.candidate_id
    assert trace1.reason_facts == trace2.reason_facts


def test_safety_and_candidates_are_logged():
    decision, trace = make_controller("efpb", cfg()).decide(make_state(), "d1")
    assert len(decision.candidates) == 3
    assert all(candidate.safe for candidate in decision.candidates)
    assert trace.chosen_candidate_id == decision.chosen.plan.candidate_id


def test_emergency_selects_requested_direction():
    decision, _ = make_controller("efpb", cfg()).decide(make_state(emergency_group="EW"), "d1")
    assert decision.chosen.plan.target_phase == "V_EW"
