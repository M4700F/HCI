from __future__ import annotations

import csv
import json
import platform
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import effective_config, result_fingerprint, sha256_json, write_json
from .controller import make_controller
from .explanations import explanation_from_trace
from .models import DecisionTrace, State
from .timing import clearance_seconds, with_demand_based_plan  # clearance_seconds is re-exported for callers of efpb.sim


CONTROLLERS = ("fixed_time", "efficiency", "equal_bargaining", "efpb")
# Bump when a change alters run results. Runs stored under another version are never silently reused.
# 0.2.0: yellow/all-red clearance; waits and service ratios cover arrivals after warm-up; throughput counts service
# events in the evaluation window; the controller receives the scenario's nominal arrival rates.
# 0.3.0: service capacities are the configured fractional rates (vehicles 0.8/s per approach), no longer rounded up to 1/s.
# 0.4.0: waits also cover people still queued at the end of the run (their wait so far), so starving a mode cannot look good.
SIM_VERSION = "0.4.0"


def _arrival_count(rng: random.Random, rate: float) -> int:
    """Small dependency-free Poisson approximation for manifests: whole arrivals plus a chance of one more for the fraction.
    Rates below 1 per second behave exactly as before; higher rates give several arrivals per second."""
    count = 0
    remaining = max(0.0, rate)
    while remaining > 0 and rng.random() < remaining:
        count += 1
        remaining -= 1.0
    return count


def make_manifest(config: Dict[str, Any], scenario: Dict[str, Any], seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    total = int(config["warmup_s"]) + int(config["evaluation_s"])
    p_rate = config["demand"]["pedestrian_rates_per_s"][scenario["pedestrian_demand"]]
    v_rate = config["demand"]["vehicle_rates_per_s"][scenario["vehicle_demand"]]
    pedestrians: List[Dict[str, Any]] = []
    vehicles: List[Dict[str, Any]] = []
    for t in range(total):
        multiplier = 1.0
        if scenario.get("process") == "bursty_markov":
            multiplier = 2.0 if (t // 60) % 2 else 0.35
        for _ in range(_arrival_count(rng, p_rate * multiplier)):
            pedestrians.append({"id": "p_%06d" % len(pedestrians), "t": t, "crosswalk": rng.choice(["N", "S", "E", "W"]), "speed_mps": config["demand"]["walking_speed_mps"]})
        for _ in range(_arrival_count(rng, v_rate * multiplier)):
            vehicles.append({"id": "v_%06d" % len(vehicles), "t": t, "approach": rng.choice(["N", "S", "E", "W"]), "occupancy": config["demand"]["occupancy_mean"]})
    emergencies = []
    if scenario.get("emergency"):
        emergencies = [{"t": max(20, int(config["warmup_s"]) + 30), "group": "NS", "release_after_s": 15}]
    manifest = {"scenario_id": scenario["id"], "seed": seed, "scenario": scenario, "pedestrians": pedestrians, "vehicles": vehicles, "emergencies": emergencies, "generator_version": "0.1.0"}
    manifest["manifest_hash"] = sha256_json(manifest)
    return manifest


def _serve_count(credit: Dict[str, float], key: str, capacity: float, queued: int) -> int:
    """Whole people or vehicles served this second at a fractional capacity. Unused credit does not build up behind an empty queue."""
    credit[key] += capacity
    count = min(int(credit[key] + 1e-9), queued)
    credit[key] -= count
    if count == queued:
        credit[key] = 0.0
    return count


def _mean_wait(queue: List[Dict[str, Any]], now: int) -> float:
    return sum(now - item["t"] for item in queue) / float(len(queue) or 1)


def _q95(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def run_one(config: Dict[str, Any], scenario: Dict[str, Any], controller_name: str, seed: int, output_root: str, manifest: Optional[Dict[str, Any]] = None, lean: bool = False) -> Dict[str, Any]:
    """Run one simulation. lean=True skips traces, explanations and per-second files (metrics only); decisions and metrics are identical."""
    manifest = manifest or make_manifest(config, scenario, seed)
    run_id = "%s__%s__%s__%s" % (config["experiment_id"], scenario["id"], controller_name, seed)
    run_dir = Path(output_root) / scenario["id"] / controller_name / str(seed) / run_id
    summary_path = run_dir / "run_summary.json"
    config = effective_config(config, controller_name)
    fingerprint = result_fingerprint(config, scenario, controller_name, seed)
    if summary_path.exists():
        existing = json.loads(summary_path.read_text())
        stored = existing.get("metrics", {})
        if stored.get("sim_version") != SIM_VERSION:
            raise RuntimeError("%s was produced by another simulator version; move or archive the old output before re-running." % run_dir)
        if stored.get("config_fingerprint") != fingerprint:
            raise RuntimeError("%s was produced with a different configuration; move or archive the old output before re-running." % run_dir)
        return existing
    if config["signal"].get("fixed_timing", "static") == "demand_based":
        # This scenario's nominal demand sets the splits. Every controller gets the plan, because all of them fall back to
        # the fixed-time plan when the sensors are degraded.
        config = with_demand_based_plan(config, scenario)
    run_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    if not lean:
        write_json(str(run_dir / "manifest.json"), manifest)
        write_json(str(run_dir / "resolved_config.json"), config)
    controller = make_controller(controller_name, config)
    ped_q: List[Dict[str, Any]] = []
    veh_q: Dict[str, List[Dict[str, Any]]] = {key: [] for key in ["N", "S", "E", "W"]}
    ped_waits: List[float] = []
    veh_waits: List[float] = []
    served_p = served_v = requested_p = requested_v = 0
    queue_rows: List[Dict[str, Any]] = []
    transitions = 0
    clearance_steps = 0
    current_phase, phase_elapsed = "P_ALL", 0
    clearance_left = 0  # seconds of yellow / all-red still to run before the new phase is displayed
    traces: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    arrivals_p: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    arrivals_v: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for item in manifest["pedestrians"]:
        arrivals_p[item["t"]].append(item)
    for item in manifest["vehicles"]:
        arrivals_v[item["t"]].append(item)
    emergency_by_t = {item["t"]: item for item in manifest["emergencies"]}
    warmup = int(config["warmup_s"])
    total_time = warmup + int(config["evaluation_s"])
    # Nominal demand of the scenario, given to the controller as its arrival-rate estimate.
    ped_rate = config["demand"]["pedestrian_rates_per_s"][scenario["pedestrian_demand"]]
    veh_rate = config["demand"]["vehicle_rates_per_s"][scenario["vehicle_demand"]]
    # Waits, service ratios and starvation counts follow the arrivals after warm-up; throughput counts service events
    # inside the evaluation window.
    ped_events = veh_events = 0
    cap_p, cap_v = float(config["demand"]["pedestrian_capacity_per_s"]), float(config["demand"]["vehicle_capacity_per_s"])
    credit = {"P": 0.0, "N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}  # fractional service credit per pedestrian queue / approach
    for t in range(total_time):
        ped_q.extend(arrivals_p[t])
        for item in arrivals_v[t]:
            veh_q[item["approach"]].append(item)
        if t >= warmup:
            requested_p += len(arrivals_p[t])
            requested_v += len(arrivals_v[t])
        emergency_group = emergency_by_t.get(t, {}).get("group")
        all_v = [item for queue in veh_q.values() for item in queue]
        state = State(
            sim_time_s=t,
            current_phase=current_phase,
            phase_elapsed_s=phase_elapsed,
            ped_queue=len(ped_q),
            veh_queue={key: len(value) for key, value in veh_q.items()},
            ped_max_wait_s=max([t - item["t"] for item in ped_q] or [0]),
            veh_max_wait_s=max([t - item["t"] for item in all_v] or [0]),
            ped_mean_wait_s=_mean_wait(ped_q, t),
            veh_mean_wait_s=_mean_wait(all_v, t),
            ped_arrival_rate=ped_rate,
            veh_arrival_rate=veh_rate,
            emergency_group=emergency_group,
            sensor_quality=0.5 if scenario.get("sensor_profile") == "degraded" else float(config["sensor"].get("quality", 1.0)),
            sensor_age_s=10.0 if scenario.get("sensor_profile") == "degraded" else float(config["sensor"].get("latency_s", 0)),
            accessibility_extension=scenario.get("sensor_profile") == "accessibility",
        )
        decision_id = "%s__t%06d" % (run_id, t)
        decision, trace = controller.decide(state, decision_id, make_trace=not lean)
        target = decision.chosen.plan.target_phase
        if clearance_left == 0 and target != current_phase and phase_elapsed >= int(config["signal"]["min_green_s"]):
            clearance_left = clearance_seconds(current_phase, target, config["signal"])
            current_phase, phase_elapsed = target, 0
            transitions += 1
        in_clearance = clearance_left > 0
        if in_clearance:
            clearance_left -= 1  # nobody is served during clearance; the minimum green counts from the displayed green
        else:
            phase_elapsed += 1
        served_keys = () if in_clearance else (("P",) if current_phase == "P_ALL" else (("N", "S") if current_phase == "V_NS" else ("E", "W")))
        for key in credit:
            if key not in served_keys:
                credit[key] = 0.0  # no credit builds up while a queue is not being served
        if in_clearance:
            pass
        elif current_phase == "P_ALL":
            for _ in range(_serve_count(credit, "P", cap_p, len(ped_q))):
                item = ped_q.pop(0)
                ped_events += int(t >= warmup)
                if item["t"] >= warmup:
                    ped_waits.append(float(t - item["t"]))
                    served_p += 1
        else:
            for key in served_keys:
                for _ in range(_serve_count(credit, key, cap_v, len(veh_q[key]))):
                    item = veh_q[key].pop(0)
                    veh_events += int(t >= warmup)
                    if item["t"] >= warmup:
                        veh_waits.append(float(t - item["t"]))
                        served_v += 1
        if t >= int(config["warmup_s"]):
            clearance_steps += int(in_clearance)
            if not lean:
                queue_rows.append({"t": t, "phase": current_phase, "in_clearance": in_clearance, "ped_queue": len(ped_q), "veh_queue": sum(len(q) for q in veh_q.values()), "ped_max_wait_s": state.ped_max_wait_s, "veh_max_wait_s": state.veh_max_wait_s, "decision_id": decision_id})
                traces.append(trace.to_dict())
        if emergency_group:
            events.append({"t": t, "type": "emergency", "group": emergency_group, "chosen": target})
    for item in ped_q:  # still queued at the end: count the wait so far instead of ignoring them
        if item["t"] >= warmup:
            ped_waits.append(float(total_time - item["t"]))
    for queue in veh_q.values():
        for item in queue:
            if item["t"] >= warmup:
                veh_waits.append(float(total_time - item["t"]))
    ref_p = float(config["controller"]["ped_wait_limit_s"])
    ref_v = float(config["controller"]["vehicle_wait_limit_s"])
    pmean, vmean = sum(ped_waits) / len(ped_waits) if ped_waits else 0.0, sum(veh_waits) / len(veh_waits) if veh_waits else 0.0
    zp, zv = served_p / float(max(1, requested_p)), served_v / float(max(1, requested_v))
    jain = ((zp + zv) ** 2 / (2 * (zp * zp + zv * zv))) if (zp or zv) else None
    metrics = {"run_id": run_id, "experiment_id": config["experiment_id"], "scenario_id": scenario["id"], "controller": controller_name, "seed": seed, "backend": config.get("backend", "surrogate"), "sim_version": SIM_VERSION, "config_fingerprint": fingerprint,
               "ped_mean_wait_s": pmean, "veh_mean_wait_s": vmean, "ped_p95_wait_s": _q95(ped_waits), "veh_p95_wait_s": _q95(veh_waits), "ped_max_wait_s": max(ped_waits or [0.0]), "veh_max_wait_s": max(veh_waits or [0.0]),
               "ped_throughput_h": ped_events / max(1e-9, config["evaluation_s"] / 3600.0), "veh_throughput_h": veh_events / max(1e-9, config["evaluation_s"] / 3600.0), "ped_service_ratio": zp, "veh_service_ratio": zv, "jain": jain,
               "mean_wait_disparity": abs(pmean / ref_p - vmean / ref_v), "tail_wait_disparity": abs(_q95(ped_waits) / ref_p - _q95(veh_waits) / ref_v), "starvation_violations": sum(1 for value in ped_waits if value > ref_p) + sum(1 for value in veh_waits if value > ref_v), "phase_switches": transitions,
               "yellow_s": int(config["signal"]["yellow_s"]), "all_red_s": int(config["signal"]["all_red_s"]), "clearance_steps": clearance_steps,
               "safety_violations": 0, "requested_p": requested_p, "requested_v": requested_v, "served_p": served_p, "served_v": served_v, "unserved_p": requested_p - served_p, "unserved_v": requested_v - served_v, "wall_time_s": time.perf_counter() - start}
    if not lean:
        with (run_dir / "states.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(queue_rows[0].keys()) if queue_rows else ["t"])
            writer.writeheader(); writer.writerows(queue_rows)
        with (run_dir / "decisions.jsonl").open("w") as handle:
            for trace in traces:
                handle.write(json.dumps(trace, sort_keys=True) + "\n")
        with (run_dir / "explanations.jsonl").open("w") as handle:
            for trace_data in traces:
                handle.write(json.dumps(explanation_from_trace(DecisionTrace(**trace_data), "FC"), sort_keys=True) + "\n")
        with (run_dir / "events.jsonl").open("w") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
    write_json(str(run_dir / "run_metrics.json"), metrics)
    summary = {"status": "valid", "run_dir": str(run_dir), "metrics": metrics, "software": {"python": sys.version, "platform": platform.platform()}}
    write_json(str(summary_path), summary)
    return summary
