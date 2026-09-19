from __future__ import annotations

import itertools
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import sha256_json
from .models import CandidateEvaluation, CandidatePlan, Decision, DecisionTrace, PHASES, State


class PriorityController:
    """Finite, deterministic implementation of the documented decision rule."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.cfg = config
        self.ccfg = config["controller"]
        self.scfg = config["signal"]

    def decide(self, state: State, decision_id: str, make_trace: bool = True) -> Tuple[Decision, Optional[DecisionTrace]]:
        candidates = self._evaluate_all(state)
        emergency = state.emergency_group is not None
        if emergency:
            chosen = self._emergency_choice(candidates, state.emergency_group)
            kind = "emergency"
        elif state.sensor_quality < float(self.ccfg["minimum_quality"]) or state.sensor_age_s > float(self.ccfg["stale_after_s"]):
            chosen = self._fixed_choice(candidates, state)
            kind = "sensor_fallback"
        elif self.name == "fixed_time":
            chosen = self._fixed_choice(candidates, state)
            kind = "fixed_time"
        elif self.name == "efficiency":
            chosen = self._efficiency_choice(candidates)
            kind = "efficiency"
        elif self.name == "equal_bargaining":
            chosen = self._bargaining_choice(candidates, state, bounded=False, debt=False)
            kind = "equal_bargaining"
        elif self.name == "efpb":
            chosen = self._bargaining_choice(candidates, state, bounded=True, debt=True)
            kind = "efpb"
        else:
            raise ValueError("unknown controller: %s" % self.name)
        decision = Decision(decision_id, self.name, chosen, candidates, self._weights(state, self.name == "efpb"), kind, emergency=emergency)
        if not make_trace:
            return decision, None
        rejected = [x for x in candidates if x.plan.candidate_id != chosen.plan.candidate_id and x.safe]
        rejected.sort(key=lambda x: (x.efficiency_loss, x.plan.candidate_id))
        best_rejected = rejected[0].plan.candidate_id if rejected else None
        trace = DecisionTrace(
            decision_id=decision_id,
            controller=self.name,
            sim_time_s=state.sim_time_s,
            state=state.to_dict(),
            decision={"kind": kind, "chosen": chosen.to_dict(), "weights": decision.weights},
            chosen_candidate_id=chosen.plan.candidate_id,
            best_rejected_candidate_id=best_rejected,
            binding_constraints=list(chosen.binding_constraints),
            reason_facts=self._reason_facts(state, chosen),
            counterfactual=self._counterfactual(state, chosen.plan.candidate_id, decision_id),
            config_hash=self.cfg["config_hash"],
        )
        trace.trace_hash = sha256_json(trace.to_dict())
        return decision, trace

    def _plans(self, state: State) -> List[CandidatePlan]:
        duration = int(self.scfg.get("service_duration_s", 25))
        phases = [state.current_phase] + [p for p in PHASES if p != state.current_phase]
        return [CandidatePlan("plan_%s_%s" % (phase, duration), phase, duration, int(phase != state.current_phase)) for phase in phases]

    def _evaluate_all(self, state: State) -> List[CandidateEvaluation]:
        out: List[CandidateEvaluation] = []
        for plan in self._plans(state):
            direction = self._direction(state) if plan.target_phase != "P_ALL" else None
            served_p = self._served_p(state, plan)
            served_v = self._served_v(state, plan)
            demand_p = max(1.0, float(state.ped_queue) + state.ped_arrival_rate * self.ccfg["horizon_s"])
            demand_v = max(1.0, float(state.veh_queue_total) + state.veh_arrival_rate * self.ccfg["horizon_s"])
            utility_p = min(1.0, served_p / demand_p)
            utility_v = min(1.0, served_v / demand_v)
            delay_p = max(0.0, state.ped_queue * self.ccfg["horizon_s"] - served_p * self.ccfg["horizon_s"] / 2.0)
            delay_v = max(0.0, state.veh_queue_total * self.ccfg["horizon_s"] - served_v * self.ccfg["horizon_s"] / 2.0)
            predicted_p = max(0.0, state.ped_max_wait_s + self.ccfg["horizon_s"] - (plan.duration_s if plan.target_phase == "P_ALL" else 0))
            predicted_v = max(0.0, state.veh_max_wait_s + self.ccfg["horizon_s"] - (plan.duration_s if plan.target_phase != "P_ALL" else 0))
            safe = plan.target_phase in PHASES and plan.duration_s >= int(self.scfg["min_green_s"])
            reasons = [] if safe else ["unsafe_signal_plan"]
            if state.accessibility_extension and plan.target_phase != "P_ALL":
                safe = False
                reasons.append("accessibility_clearance_required")
            ev = CandidateEvaluation(plan, safe=safe, rejection_reasons=reasons, utility_p=utility_p, utility_v=utility_v,
                                     predicted_ped_delay=delay_p, predicted_veh_delay=delay_v,
                                     predicted_ped_max_wait=predicted_p, predicted_veh_max_wait=predicted_v,
                                     efficiency_loss=self.ccfg["delay_cost_p"] * delay_p + self.ccfg["delay_cost_v"] * delay_v + self.ccfg["switch_cost"] * plan.switches,
                                     direction=direction)
            out.append(ev)
        return out

    def _served_p(self, state: State, plan: CandidatePlan) -> float:
        if plan.target_phase != "P_ALL":
            return 0.0
        return min(float(state.ped_queue), plan.duration_s * self.cfg["demand"]["pedestrian_capacity_per_s"])

    def _served_v(self, state: State, plan: CandidatePlan) -> float:
        if plan.target_phase == "P_ALL":
            return 0.0
        keys = ("N", "S") if plan.target_phase == "V_NS" else ("E", "W")
        q = sum(state.veh_queue.get(k, 0) for k in keys)
        return min(float(q), plan.duration_s * self.cfg["demand"]["vehicle_capacity_per_s"])

    def _direction(self, state: State) -> str:
        ns = state.veh_queue.get("N", 0) + state.veh_queue.get("S", 0)
        ew = state.veh_queue.get("E", 0) + state.veh_queue.get("W", 0)
        return "NS" if ns >= ew else "EW"

    def _weights(self, state: State, debt: bool) -> Dict[str, float]:
        p = float(self.ccfg["base_weight_p"])
        v = float(self.ccfg["base_weight_v"])
        if debt:
            k, eta = float(self.ccfg["debt_kappa"]), float(self.ccfg["debt_eta"])
            p *= 1 + k * min(1.0, state.ped_max_wait_s / self.ccfg["ped_wait_limit_s"]) ** eta
            v *= 1 + k * min(1.0, state.veh_max_wait_s / self.ccfg["vehicle_wait_limit_s"]) ** eta
        total = p + v
        return {"p": p / total, "v": v / total}

    def _fallback(self, candidates: Iterable[CandidateEvaluation], state: State) -> Tuple[float, float]:
        for c in candidates:
            if c.plan.target_phase == state.current_phase:
                return c.utility_p, c.utility_v
        return 0.0, 0.0

    def _bargaining_choice(self, candidates: List[CandidateEvaluation], state: State, bounded: bool, debt: bool) -> CandidateEvaluation:
        safe = [c for c in candidates if c.safe]
        dp, dv = self._fallback(safe, state)
        for c in safe:
            c.disagreement_p, c.disagreement_v = dp, dv
            c.gain_p, c.gain_v = c.utility_p - dp, c.utility_v - dv
            c.ir = c.gain_p >= -1e-12 and c.gain_v >= -1e-12
            c.starvation_feasible = c.predicted_ped_max_wait <= self.ccfg["ped_wait_limit_s"] and c.predicted_veh_max_wait <= self.ccfg["vehicle_wait_limit_s"]
            if not c.ir:
                c.rejection_reasons.append("individual_rationality")
            if bounded and not c.starvation_feasible:
                c.rejection_reasons.append("predicted_max_wait_limit")
                if c.predicted_ped_max_wait <= self.ccfg["ped_wait_limit_s"] + 1:
                    c.binding_constraints.append("pedestrian_wait_limit")
                if c.predicted_veh_max_wait <= self.ccfg["vehicle_wait_limit_s"] + 1:
                    c.binding_constraints.append("vehicle_wait_limit")
        feasible = [c for c in safe if c.ir and (c.starvation_feasible if bounded else True)]
        if not feasible and bounded:
            feasible = sorted(safe, key=lambda c: (self._breach_count(c), self._largest_breach(c), c.efficiency_loss, c.plan.candidate_id))[:1]
            if feasible:
                feasible[0].binding_constraints.append("least_breach_fallback")
        feasible = feasible or safe or candidates
        lmin = min(c.efficiency_loss for c in feasible)
        if bounded:
            bound = lmin + self.ccfg["delta"] * max(lmin, self.ccfg["efficiency_floor"])
            near = [c for c in feasible if c.efficiency_loss <= bound + 1e-9]
            for c in feasible:
                if c not in near:
                    c.rejection_reasons.append("efficiency_bound")
            feasible = near or feasible
        weights = self._weights(state, debt)
        eps = float(self.ccfg["epsilon"])
        for c in feasible:
            c.nash_score = weights["p"] * math.log(max(eps, c.gain_p + eps)) + weights["v"] * math.log(max(eps, c.gain_v + eps))
        return sorted(feasible, key=lambda c: (-float(c.nash_score), max(c.predicted_ped_max_wait / self.ccfg["ped_wait_limit_s"], c.predicted_veh_max_wait / self.ccfg["vehicle_wait_limit_s"]), c.plan.switches, c.plan.candidate_id))[0]

    def _breach_count(self, c: CandidateEvaluation) -> int:
        return int(c.predicted_ped_max_wait > self.ccfg["ped_wait_limit_s"]) + int(c.predicted_veh_max_wait > self.ccfg["vehicle_wait_limit_s"])

    def _largest_breach(self, c: CandidateEvaluation) -> float:
        return max(c.predicted_ped_max_wait / self.ccfg["ped_wait_limit_s"], c.predicted_veh_max_wait / self.ccfg["vehicle_wait_limit_s"])

    def _efficiency_choice(self, candidates: List[CandidateEvaluation]) -> CandidateEvaluation:
        return sorted([c for c in candidates if c.safe], key=lambda c: (c.efficiency_loss, c.plan.candidate_id))[0]

    def _fixed_choice(self, candidates: List[CandidateEvaluation], state: State) -> CandidateEvaluation:
        splits = self.scfg["fixed_splits_s"]
        x, running, wanted = state.sim_time_s % int(self.scfg["fixed_cycle_s"]), 0, self.scfg["phases"][0]
        for phase in self.scfg["phases"]:
            running += int(splits[phase])
            if x < running:
                wanted = phase
                break
        return sorted([c for c in candidates if c.safe], key=lambda c: (c.plan.target_phase != wanted, c.plan.candidate_id))[0]

    def _emergency_choice(self, candidates: List[CandidateEvaluation], group: Optional[str]) -> CandidateEvaluation:
        wanted = "V_NS" if group == "NS" else "V_EW"
        return sorted([c for c in candidates if c.safe], key=lambda c: (c.plan.target_phase != wanted, c.plan.candidate_id))[0]

    def _reason_facts(self, state: State, chosen: CandidateEvaluation) -> List[Dict[str, Any]]:
        return [
            {"feature_id": "ped_max_wait_s", "label": "longest pedestrian wait", "raw_value": state.ped_max_wait_s, "unit": "s", "normalized": min(1.0, state.ped_max_wait_s / self.ccfg["ped_wait_limit_s"]), "direction": "increases_pedestrian_priority"},
            {"feature_id": "veh_max_wait_s", "label": "longest vehicle wait", "raw_value": state.veh_max_wait_s, "unit": "s", "normalized": min(1.0, state.veh_max_wait_s / self.ccfg["vehicle_wait_limit_s"]), "direction": "increases_vehicle_priority"},
            {"feature_id": "efficiency_loss", "label": "predicted efficiency loss", "raw_value": chosen.efficiency_loss, "unit": "person_seconds_equivalent", "normalized": chosen.efficiency_loss / max(1.0, self.ccfg["efficiency_floor"]), "direction": "bounded_by_delta"},
        ]

    def _counterfactual(self, state: State, chosen_id: str, decision_id: str) -> Dict[str, Any]:
        if self.name not in ("efpb", "equal_bargaining"):
            return {"status": "not_requested"}
        spec = self.ccfg.get("counterfactual", {})
        fields = list(spec.get("feature_steps", {}).items())
        original = state.to_dict()
        for distance in range(1, int(spec.get("max_distance", 4)) + 1):
            for combo in itertools.product(fields, repeat=distance):
                next_state = State(**original)
                deltas: Dict[str, float] = {}
                for feature, step in combo:
                    deltas[feature] = deltas.get(feature, 0) + float(step)
                    if feature == "ped_queue":
                        next_state.ped_queue += int(step)
                    elif feature == "veh_queue":
                        for k in next_state.veh_queue:
                            next_state.veh_queue[k] += int(step) // 4
                    elif feature == "ped_max_wait_s":
                        next_state.ped_max_wait_s = max(0.0, next_state.ped_max_wait_s + float(step))
                    elif feature == "veh_max_wait_s":
                        next_state.veh_max_wait_s = max(0.0, next_state.veh_max_wait_s + float(step))
                replay, _ = self.decide(next_state, decision_id + "_replay", make_trace=False)
                if replay.chosen.plan.candidate_id != chosen_id:
                    return {"status": "validated", "target_candidate_id": replay.chosen.plan.candidate_id, "deltas": deltas, "distance": distance, "replay_decision_id": decision_id + "_replay"}
        return {"status": "no_flip_within_range", "max_distance": int(spec.get("max_distance", 4))}


def make_controller(name: str, config: Dict[str, Any]) -> PriorityController:
    return PriorityController(name, config)
