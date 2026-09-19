from efpb.config import load_config
from efpb.controller import make_controller
from efpb.explanations import explanation_from_trace
from efpb.models import State
from efpb.validators import validate_explanation, validate_trace


def test_trace_and_explanation_validation():
    config = load_config("configs/experiments/smoke.yaml")
    state = State(50, "V_NS", 20, 10, {"N": 2, "S": 2, "E": 8, "W": 8}, 80, 30, 40, 15, .05, .1)
    _, trace = make_controller("efpb", config).decide(state, "d1")
    assert validate_trace(trace)["valid"]
    assert validate_explanation(explanation_from_trace(trace, "FC"), trace)["valid"]
