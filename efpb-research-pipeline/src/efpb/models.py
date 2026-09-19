from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


PHASES = ("P_ALL", "V_NS", "V_EW")


@dataclass
class State:
    sim_time_s: int
    current_phase: str
    phase_elapsed_s: int
    ped_queue: int
    veh_queue: Dict[str, int]
    ped_max_wait_s: float
    veh_max_wait_s: float
    ped_mean_wait_s: float
    veh_mean_wait_s: float
    ped_arrival_rate: float
    veh_arrival_rate: float
    downstream_occupancy: Dict[str, float] = field(default_factory=dict)
    emergency_group: Optional[str] = None
    sensor_quality: float = 1.0
    sensor_age_s: float = 0.0
    accessibility_extension: bool = False

    @property
    def veh_queue_total(self) -> int:
        return sum(self.veh_queue.values())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidatePlan:
    candidate_id: str
    target_phase: str
    duration_s: int
    switches: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateEvaluation:
    plan: CandidatePlan
    safe: bool
    ir: bool = False
    starvation_feasible: bool = False
    rejection_reasons: List[str] = field(default_factory=list)
    utility_p: float = 0.0
    utility_v: float = 0.0
    disagreement_p: float = 0.0
    disagreement_v: float = 0.0
    gain_p: float = 0.0
    gain_v: float = 0.0
    predicted_ped_delay: float = 0.0
    predicted_veh_delay: float = 0.0
    predicted_ped_max_wait: float = 0.0
    predicted_veh_max_wait: float = 0.0
    efficiency_loss: float = 0.0
    nash_score: Optional[float] = None
    binding_constraints: List[str] = field(default_factory=list)
    direction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["plan"] = self.plan.to_dict()
        return d


@dataclass
class Decision:
    decision_id: str
    controller: str
    chosen: CandidateEvaluation
    candidates: List[CandidateEvaluation]
    weights: Dict[str, float]
    decision_kind: str = "ordinary"
    fallback: bool = False
    emergency: bool = False
    tie_break_path: List[str] = field(default_factory=list)


@dataclass
class DecisionTrace:
    decision_id: str
    controller: str
    sim_time_s: int
    state: Dict[str, Any]
    decision: Dict[str, Any]
    chosen_candidate_id: str
    best_rejected_candidate_id: Optional[str]
    binding_constraints: List[str]
    reason_facts: List[Dict[str, Any]]
    counterfactual: Dict[str, Any]
    config_hash: str
    trace_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
