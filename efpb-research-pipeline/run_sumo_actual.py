from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import hashlib
import tempfile

from efpb.config import effective_config, load_config, result_fingerprint, write_json
from efpb.controller import make_controller
from efpb.models import State
from efpb.timing import with_demand_based_plan

# Bump when a change to this runner alters run results (it is part of every run's fingerprint).
# 0.4.0: signal program 0, scaled vehicle demand, evaluation-window metrics, yellow/all-red clearance, demand-based fixed-time plan.
# 0.4.1: SUMO start-up serialised and checked (parallel runs could share a TraCI port); output-only additional file dropped.
# 0.5.0: pedestrian waits and vehicle stop times also cover pedestrians still waiting and vehicles still in the network at the end.
RUNNER_VERSION = "0.5.0"
SUMO_CONFIG = "sumo/actual/cross.sumocfg"
ROUTE_FILE = "sumo/actual/cross.rou.xml"
# cross.tls.add.xml defines a second program ("manual") that SUMO activates by default. The phase indices below belong
# to the network's own program "0": phase 0 gives green to approaches 1+2, phase 4 to approaches 3+4.
SIGNAL_PROGRAM = "0"
GREEN_PHASE = {"V_NS": 0, "V_EW": 4}
# Approaches 1+2 and 3+4 are the two opposing pairs that share a green phase, so they form the V_NS and V_EW groups.
APPROACH = {"1fi": "N", "1si": "N", "2fi": "S", "2si": "S", "3fi": "E", "3si": "E", "4fi": "W", "4si": "W"}


def sumo_files_hash(directory: str = "sumo/actual", config: str = "cross.sumocfg") -> str:
    """Hash of the SUMO config and the network, route and additional files it lists. Files SUMO writes into the same
    folder during a run (netstate.xml, tlsstate.xml) are not inputs and are left out."""
    root = Path(directory)
    names = {config}
    for element in ET.parse(root / config).getroot().find("input"):
        for value in element.get("value", "").split(","):
            if value.strip():
                names.add(value.strip())
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode() + b"\0" + (root / name).read_bytes() + b"\0")
    return digest.hexdigest()


def pick_scenario(cfg: dict, scenario_id: str | None) -> dict:
    scenarios = cfg.get("scenarios", [{"id": "sumo_actual", "pedestrian_demand": "M", "vehicle_demand": "M", "emergency": False}])
    return next((x for x in scenarios if x.get("id") == scenario_id), scenarios[0]) if scenario_id else scenarios[0]


def run_fingerprint(config_path: str, controller_name: str, seed: int, scenario_id: str | None = None) -> str:
    cfg = load_config(config_path)
    return result_fingerprint(cfg, pick_scenario(cfg, scenario_id), controller_name, seed, {"runner": RUNNER_VERSION, "sumo_files": sumo_files_hash()})


def check_reusable(metrics_path: Path, fingerprint: str) -> None:
    """Refuse to reuse a stored run made with another configuration, runner version or set of SUMO files."""
    if json.loads(metrics_path.read_text()).get("config_fingerprint") != fingerprint:
        raise SystemExit("%s was produced with a different configuration or runner; move or archive the old output before re-running." % metrics_path.parent)


def start_sumo(traci, command: list, port: int, log_path: Path, seed: int, scale: float) -> None:
    """Start SUMO and connect, then confirm that the connected SUMO is this run's own.

    traci picks a free port before SUMO binds it, so two runs starting at once can pick the same port; one SUMO then fails to
    bind and its client can end up talking to the other run's SUMO. Start-up is therefore serialised across processes with a
    file lock, and the connection is checked against this run's seed, scale and log file.
    """
    if port:  # a caller-assigned port that no other run uses (for example one per worker): nothing to serialise
        traci.start(command, port=port)
    else:
        try:
            import fcntl
        except ImportError:  # no file locking on this platform
            fcntl = None
        with open(Path(tempfile.gettempdir()) / "efpb_traci_start.lock", "w") as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            traci.start(command)
    expected = {"seed": str(seed), "log": str(log_path), "scale": "%.6f" % scale}
    found = {name: traci.simulation.getOption(name) for name in expected}
    if found != expected:
        traci.close()
        raise RuntimeError("TraCI connected to a different SUMO instance: expected %s, found %s" % (expected, found))


def import_traci():
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        tools = str(Path(sumo_home) / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
    try:
        import traci
        return traci
    except ImportError as exc:
        raise SystemExit("TraCI import failed. Set SUMO_HOME or install eclipse-sumo.") from exc


def route_flow_rate(route_file: str = ROUTE_FILE) -> float:
    """Total insertion rate (vehicles per second) of the periodic flows in the bundled route file."""
    return sum(1.0 / float(flow.get("period")) for flow in ET.parse(route_file).getroot().iter("flow") if flow.get("period"))


def route_approach_shares(route_file: str = ROUTE_FILE) -> dict:
    """Share of the bundled vehicle demand entering on each approach (route ids start with the approach number)."""
    rate = {key: 0.0 for key in "NSEW"}
    for flow in ET.parse(route_file).getroot().iter("flow"):
        if flow.get("period"):
            rate[APPROACH[flow.get("route")[0] + "si"]] += 1.0 / float(flow.get("period"))
    total = sum(rate.values())
    return {key: value / total for key, value in rate.items()}


def set_signal(traci, tls_id: str, target: str, n_links: int, service_duration_s: int) -> None:
    if target == "P_ALL":
        # Pedestrian service is an all-red vehicle interval; the controller model serves no vehicles during P_ALL.
        traci.trafficlight.setRedYellowGreenState(tls_id, "r" * n_links)
        return
    traci.trafficlight.setProgram(tls_id, SIGNAL_PROGRAM)
    traci.trafficlight.setPhase(tls_id, GREEN_PHASE[target])
    traci.trafficlight.setPhaseDuration(tls_id, service_duration_s)


def clearance_states(green_state: dict, from_phase: str, to_phase: str, yellow_s: int, all_red_s: int, n_links: int) -> list:
    """Per-second signal states between two phases: yellow after a vehicle green, then all-red before a vehicle green.

    P_ALL is already all red, so leaving it needs no clearance and entering it needs only the yellow.
    """
    states = []
    if from_phase != "P_ALL":
        states += [green_state[from_phase].replace("G", "y").replace("g", "y")] * yellow_s
    if to_phase != "P_ALL" and from_phase != "P_ALL":
        states += ["r" * n_links] * all_red_s
    return states


def percentile95(values: list) -> float:
    ordered = sorted(values) or [0]
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def run(config_path: str, controller_name: str, seed: int, port: int = 0, scenario_id: str | None = None, output_root: str = "data/sumo_runs", lean: bool = False) -> dict:
    return run_config(load_config(config_path), controller_name, seed, port, scenario_id, output_root, lean)


def run_config(cfg: dict, controller_name: str, seed: int, port: int = 0, scenario_id: str | None = None, output_root: str = "data/sumo_runs", lean: bool = False) -> dict:
    """Run one SUMO/TraCI run from a loaded config. lean=True skips the per-second traces and states (metrics and metadata only)."""
    traci = import_traci()
    cfg = effective_config(cfg, controller_name)
    scenario = pick_scenario(cfg, scenario_id)
    fingerprint = result_fingerprint(cfg, scenario, controller_name, seed, {"runner": RUNNER_VERSION, "sumo_files": sumo_files_hash()})
    timing_mode = cfg["signal"].get("fixed_timing", "static")
    if timing_mode == "demand_based":
        cfg = with_demand_based_plan(cfg, scenario, route_approach_shares())  # splits from this scenario's nominal demand and the bundled approach mix; every controller's fixed-time fallback uses it
    fixed_timing = timing_mode if controller_name == "fixed_time" else None
    run_id = "sumo_actual__%s__%s__%s" % (scenario["id"], controller_name, seed)
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    warmup = int(cfg["warmup_s"])
    total = warmup + int(cfg["evaluation_s"])
    min_green = int(cfg["signal"]["min_green_s"])
    service_duration = int(cfg["signal"]["service_duration_s"])
    yellow_s = int(cfg["signal"]["yellow_s"])
    all_red_s = int(cfg["signal"]["all_red_s"])
    stop_speed = float(cfg["controller"]["stop_speed_mps"])
    ped_rate = cfg["demand"]["pedestrian_rates_per_s"][scenario.get("pedestrian_demand", "M")]
    # The bundled flows insert route_flow_rate() vehicles/s; SUMO's --scale rescales them to the scenario's vehicle demand.
    veh_rate = cfg["demand"]["vehicle_rates_per_s"][scenario.get("vehicle_demand", "M")]
    sumo_scale = veh_rate / route_flow_rate()
    ped_queue = []
    controller = make_controller(controller_name, cfg)
    traces = []
    states = []
    vehicle_first_seen = {}
    vehicle_stopped_steps = {}
    completed = []
    stopped_wait_samples = []
    ped_waits = []
    queue_sum = 0
    ped_queue_sum = 0
    ped_phase_steps = 0
    phase_switches = 0
    clearance_steps = 0
    collisions = 0
    emergency_stops = 0
    start = time.perf_counter()
    sumo_binary = os.environ.get("SUMO_BINARY", "sumo")
    log_path = output / "sumo.log"  # unique per run; also lets the run check that it reached its own SUMO
    # Only the signal program is loaded: the bundled output-only additional file would make parallel runs overwrite the same files.
    command = [sumo_binary, "-c", SUMO_CONFIG, "--seed", str(seed), "--scale", "%.6f" % sumo_scale, "--no-step-log", "true",
               "--additional-files", "sumo/actual/cross.tls.add.xml", "--log", str(log_path)]
    start_sumo(traci, command, port, log_path, seed, sumo_scale)
    try:
        sumo_version = traci.getVersion()[1]
        tls_id = traci.trafficlight.getIDList()[0]
        n_links = len(traci.trafficlight.getRedYellowGreenState(tls_id))
        program = next(x for x in traci.trafficlight.getAllProgramLogics(tls_id) if x.programID == SIGNAL_PROGRAM)
        green_state = {name: program.phases[index].state for name, index in GREEN_PHASE.items()}
        current_phase = "V_NS"
        phase_elapsed = 0  # seconds the current phase has been fully displayed (clearance not counted)
        clearance = []  # per-second yellow / all-red states still to be shown before the new phase starts
        pending_signal = None
        set_signal(traci, tls_id, current_phase, n_links, service_duration)
        for t in range(total):
            evaluating = t >= warmup
            # Virtual pedestrian demand is explicit and reproducible for the emergency one-day prototype.
            if rng.random() < ped_rate:
                ped_queue.append(t)
            vehicles = traci.vehicle.getIDList()
            by_approach = {"N": [], "S": [], "E": [], "W": []}
            for vehicle_id in vehicles:
                vehicle_first_seen.setdefault(vehicle_id, t)
                if traci.vehicle.getSpeed(vehicle_id) < stop_speed:
                    wait = traci.vehicle.getWaitingTime(vehicle_id)
                    vehicle_stopped_steps[vehicle_id] = vehicle_stopped_steps.get(vehicle_id, 0) + 1
                    key = APPROACH.get(traci.vehicle.getRoadID(vehicle_id))
                    if key:
                        by_approach[key].append(wait)
                    if evaluating:
                        stopped_wait_samples.append(wait)
            all_vehicle_waits = [wait for values in by_approach.values() for wait in values]
            if evaluating:
                queue_sum += len(all_vehicle_waits)
                ped_queue_sum += len(ped_queue)
            state = State(t, current_phase, phase_elapsed, len(ped_queue), {key: len(value) for key, value in by_approach.items()}, max([t - x for x in ped_queue] or [0]), max(all_vehicle_waits or [0]), 0.0, 0.0, ped_rate, veh_rate)
            decision, trace = controller.decide(state, "%s__t%06d" % (run_id, t), make_trace=not lean)
            target = decision.chosen.plan.target_phase
            if not clearance and pending_signal is None and target != current_phase and phase_elapsed >= min_green:
                clearance = clearance_states(green_state, current_phase, target, yellow_s, all_red_s, n_links)
                pending_signal = target
                current_phase = target
                phase_elapsed = 0
                if evaluating:
                    phase_switches += 1
            if clearance:
                traci.trafficlight.setRedYellowGreenState(tls_id, clearance.pop(0))
                if evaluating:
                    clearance_steps += 1
            elif pending_signal is not None:
                set_signal(traci, tls_id, pending_signal, n_links, service_duration)
                pending_signal = None
            elif current_phase != "P_ALL":
                # Program phases expire; keep the current green running while the controller holds it.
                traci.trafficlight.setPhaseDuration(tls_id, service_duration)
            displayed = not clearance and pending_signal is None
            if displayed:
                phase_elapsed += 1
            if current_phase == "P_ALL" and displayed:
                if evaluating:
                    ped_phase_steps += 1
                if ped_queue:
                    arrived_at = ped_queue.pop(0)
                    if evaluating:
                        ped_waits.append(t - arrived_at)
            traci.simulationStep()
            if evaluating:
                collisions += traci.simulation.getCollidingVehiclesNumber()
                emergency_stops += traci.simulation.getEmergencyStoppingVehiclesNumber()
            for vehicle_id in traci.simulation.getArrivedIDList():
                first_seen = vehicle_first_seen.pop(vehicle_id, t)
                stopped_steps = vehicle_stopped_steps.pop(vehicle_id, 0)
                if evaluating:
                    completed.append((t - first_seen, stopped_steps))
            if evaluating:
                if not lean:
                    traces.append(trace.to_dict())
                    states.append({"t": t, "vehicles": len(vehicles), "ped_queue": len(ped_queue), "phase": current_phase, "in_clearance": not displayed, "decision_id": trace.decision_id})
        evaluation_steps = total - warmup
        ped_served = len(ped_waits)
        ped_unserved = 0
        for arrived_at in ped_queue:  # still waiting at the end: count the wait so far
            if arrived_at >= warmup:
                ped_waits.append(total - arrived_at)
                ped_unserved += 1
        stop_times_all = [stopped for _, stopped in completed] + list(vehicle_stopped_steps.values())  # finished plus still in the network
        metrics = {
            "run_id": run_id,
            "backend": "sumo_traci_virtual_pedestrian",
            "sumo_version": sumo_version,
            "runner_version": RUNNER_VERSION,
            "config_fingerprint": fingerprint,
            "controller": controller_name,
            "seed": seed,
            "scenario_id": scenario.get("id"),
            "vehicle_demand": scenario.get("vehicle_demand", "M"),
            "vehicle_rate_per_s": veh_rate,
            "sumo_scale": sumo_scale,
            "steps": evaluation_steps,
            "trace_count": len(traces),
            "wall_time_s": time.perf_counter() - start,
            "vehicle_completed": len(completed),
            "vehicle_throughput_per_hour": len(completed) * 3600.0 / max(1, evaluation_steps),
            "vehicle_trip_time_mean_s": mean([trip for trip, _ in completed]),
            "vehicle_stop_time_mean_s": mean([stopped for _, stopped in completed]),
            "vehicle_stop_time_all_mean_s": mean(stop_times_all),
            "vehicle_unfinished": len(vehicle_stopped_steps),
            "vehicle_stopped_wait_mean_s": mean(stopped_wait_samples),
            "vehicle_stopped_wait_p95_s": percentile95(stopped_wait_samples),
            "vehicle_stopped_wait_max_s": max(stopped_wait_samples or [0]),
            "mean_vehicle_queue": queue_sum / max(1, evaluation_steps),
            "pedestrian_served_virtual": ped_served,
            "pedestrian_unserved": ped_unserved,
            "pedestrian_phase_steps": ped_phase_steps,
            "pedestrian_wait_mean_s": mean(ped_waits),
            "pedestrian_wait_p95_s": percentile95(ped_waits),
            "pedestrian_wait_max_s": max(ped_waits or [0]),
            "mean_pedestrian_queue": ped_queue_sum / max(1, evaluation_steps),
            "phase_switches": phase_switches,
            "fixed_timing": fixed_timing or "",
            "fixed_cycle_s": cfg["signal"]["fixed_cycle_s"] if fixed_timing else "",
            "fixed_splits_s": json.dumps(cfg["signal"]["fixed_splits_s"], sort_keys=True) if fixed_timing else "",
            "yellow_s": yellow_s,
            "all_red_s": all_red_s,
            "clearance_steps": clearance_steps,
            "collisions": collisions,
            "emergency_stops": emergency_stops,
            "metric_window": "evaluation period only (after warmup_s)",
            "scope_warning": "Vehicle movement and signal execution are SUMO/TraCI. Pedestrians are virtual queues because the bundled legacy network has no validated pedestrian walking areas; P_ALL is an all-red vehicle interval. Phase changes show signal.yellow_s of yellow and signal.all_red_s of all-red clearance.",
        }
        write_json(str(output / "metrics.json"), metrics)
        if not lean:
            (output / "states.jsonl").write_text("".join(json.dumps(x) + "\n" for x in states))
            (output / "decisions.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in traces))
        write_json(str(output / "metadata.json"), {"config": cfg, "scenario": scenario, "command": command, "metrics": metrics})
        return metrics
    finally:
        traci.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiments/smoke.yaml")
    parser.add_argument("--controller", choices=["fixed_time", "efficiency", "equal_bargaining", "efpb"], default="efpb")
    parser.add_argument("--seed", type=int, default=9001)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--scenario", default=None, help="Scenario ID from the YAML file; defaults to the first scenario")
    parser.add_argument("--output-root", default="data/sumo_runs")
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.controller, args.seed, args.port, args.scenario, args.output_root), indent=2))
