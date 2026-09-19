"""Signal timing helpers: clearance lost time and demand-based fixed-time plans."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional


def clearance_seconds(from_phase: str, to_phase: str, signal: Dict[str, Any]) -> int:
    """Lost time when the signal changes phase: yellow after a vehicle green, then all-red before the next vehicle green.

    P_ALL is already all red, so leaving it needs no clearance and entering it needs only the yellow.
    """
    if from_phase == "P_ALL":
        return 0
    return int(signal["yellow_s"]) + (int(signal["all_red_s"]) if to_phase != "P_ALL" else 0)


def clearance_into(signal: Dict[str, Any]) -> Dict[str, int]:
    """Clearance seconds at the start of each phase's slot in the fixed cycle."""
    order = list(signal["phases"])
    return {phase: clearance_seconds(order[index - 1], phase, signal) for index, phase in enumerate(order)}


EVEN_SHARES = {"N": 0.25, "S": 0.25, "E": 0.25, "W": 0.25}


def flow_ratios(config: Dict[str, Any], scenario: Dict[str, Any], approach_shares: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Nominal demand over service capacity per phase (pedestrians share one queue; a vehicle phase serves its two approaches
    in parallel, so its busier approach sets the ratio). Vehicles are spread evenly over the approaches unless shares are given."""
    multiplier = 1.175 if scenario.get("process") == "bursty_markov" else 1.0  # mean of the 2.0 / 0.35 alternating bursts
    ped = config["demand"]["pedestrian_rates_per_s"][scenario["pedestrian_demand"]] * multiplier
    veh = config["demand"]["vehicle_rates_per_s"][scenario["vehicle_demand"]] * multiplier
    cap_p = float(config["demand"]["pedestrian_capacity_per_s"])
    cap_v = float(config["demand"]["vehicle_capacity_per_s"])
    shares = approach_shares or EVEN_SHARES
    return {"P_ALL": ped / cap_p, "V_NS": veh * max(shares["N"], shares["S"]) / cap_v, "V_EW": veh * max(shares["E"], shares["W"]) / cap_v}


def cycle_floor(config: Dict[str, Any]) -> int:
    """Shortest cycle in which every phase still gets its minimum green plus its clearance."""
    signal = config["signal"]
    return len(signal["phases"]) * int(signal["min_green_s"]) + sum(clearance_into(signal).values())


def webster_cycle(config: Dict[str, Any], scenario: Dict[str, Any], approach_shares: Optional[Dict[str, float]] = None) -> float:
    """Webster's optimum cycle (1.5 L + 5) / (1 - Y); infinite when the nominal demand saturates the phases."""
    lost = sum(clearance_into(config["signal"]).values())
    total = sum(flow_ratios(config, scenario, approach_shares).values())
    return float("inf") if total >= 1 else (1.5 * lost + 5) / (1 - total)


def demand_based_splits(config: Dict[str, Any], scenario: Dict[str, Any], cycle_s: int, approach_shares: Optional[Dict[str, float]] = None) -> Dict[str, int]:
    """Slot per phase (its green plus the clearance before it). Every phase gets its minimum green; the remaining cycle time is
    shared in proportion to the phases' flow ratios, as in Webster's rule."""
    signal = config["signal"]
    floor = cycle_floor(config)
    if cycle_s < floor:
        raise ValueError("cycle %d s is below the %d s needed for the minimum greens and clearances" % (cycle_s, floor))
    into, ratios = clearance_into(signal), flow_ratios(config, scenario, approach_shares)
    pool = cycle_s - floor
    total = sum(ratios.values()) or 1.0
    slots = {phase: int(signal["min_green_s"]) + into[phase] + int(pool * ratios[phase] / total) for phase in signal["phases"]}
    slots[max(ratios, key=ratios.get)] += cycle_s - sum(slots.values())  # rounding remainder goes to the busiest phase
    return slots


def with_demand_based_plan(config: Dict[str, Any], scenario: Dict[str, Any], approach_shares: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    plan = copy.deepcopy(config)
    plan["signal"]["fixed_splits_s"] = demand_based_splits(config, scenario, int(config["signal"]["fixed_cycle_s"]), approach_shares)
    return plan
