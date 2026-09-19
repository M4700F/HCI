from __future__ import annotations

from typing import Any, Dict

from .models import DecisionTrace


def explanation_from_trace(trace: DecisionTrace, condition: str = "F") -> Dict[str, Any]:
    chosen = trace.decision["chosen"]
    phase = chosen["plan"]["target_phase"]
    text = "%s service was selected for the next %s s." % ("Pedestrian" if phase == "P_ALL" else "Vehicle", chosen["plan"]["duration_s"])
    facts = trace.reason_facts
    if len(facts) >= 2:
        text += " The longest pedestrian wait is %.1f s and the longest vehicle wait is %.1f s." % (facts[0]["raw_value"], facts[1]["raw_value"])
    if condition in ("F", "FC"):
        text += " The selected plan's predicted loss is %.2f." % chosen["efficiency_loss"]
    result: Dict[str, Any] = {"decision_id": trace.decision_id, "condition": condition, "text": text, "trace_hash": trace.trace_hash, "validation_status": "valid", "reason_facts": facts}
    if condition == "FC":
        result["counterfactual"] = trace.counterfactual
        if trace.counterfactual.get("status") == "validated":
            result["text"] += " A replay-validated change would select %s." % trace.counterfactual["target_candidate_id"]
        else:
            result["text"] += " No validated decision flip was found within the declared search range."
    return result
