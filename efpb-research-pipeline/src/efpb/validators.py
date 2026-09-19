from __future__ import annotations

from typing import Any, Dict

from .config import sha256_json
from .models import DecisionTrace


def validate_trace(trace: DecisionTrace) -> Dict[str, Any]:
    chosen = trace.decision.get("chosen", {})
    checks = {
        "chosen_candidate_matches": chosen.get("plan", {}).get("candidate_id") == trace.chosen_candidate_id,
        "config_hash_present": bool(trace.config_hash),
        "trace_hash_present": bool(trace.trace_hash),
        "reason_facts_bounded": len(trace.reason_facts) <= 3,
        "counterfactual_declared": bool(trace.counterfactual.get("status")),
    }
    payload = trace.to_dict(); supplied = payload.get("trace_hash", ""); payload["trace_hash"] = ""
    checks["trace_hash_recomputes"] = sha256_json(payload) == supplied
    return {"valid": all(checks.values()), "checks": checks}


def validate_explanation(explanation: Dict[str, Any], trace: DecisionTrace) -> Dict[str, Any]:
    checks = {
        "decision_id_matches": explanation.get("decision_id") == trace.decision_id,
        "trace_hash_matches": explanation.get("trace_hash") == trace.trace_hash,
        "validation_status_is_valid": explanation.get("validation_status") == "valid",
        "all_reason_slots_bound": explanation.get("reason_facts") == trace.reason_facts,
    }
    return {"valid": all(checks.values()), "checks": checks}
