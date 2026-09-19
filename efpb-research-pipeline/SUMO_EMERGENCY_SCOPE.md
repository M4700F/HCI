# Emergency SUMO scope for the one-day deadline

`run_sumo_actual.py` is the time-boxed SUMO/TraCI runner. It uses a real SUMO vehicle network and real TraCI vehicle queues, but represents pedestrian demand as a virtual queue because the supplied legacy SUMO crossing network does not contain validated pedestrian walking areas. This is a valid engineering prototype, not the complete multimodal methodology in the research plan.

Use it only if the one-day deadline requires a real SUMO run immediately. In the paper, describe this as a SUMO vehicle-network prototype with virtual pedestrian demand and narrow the claims accordingly. Do not claim pedestrian trajectory validation, field safety, or complete multimodal realism.

The complete four-arm pedestrian SUMO model with validated walking areas, crossing links, legal pedestrian timing, and full TraCI safety execution requires additional network engineering and should not be fabricated in one day.

## Runner corrections (v2)

The first pilot results were discarded (kept as `data/sumo_runs_v1_defective/`) because of these runner defects, now fixed in `run_sumo_actual.py`:

- `cross.tls.add.xml` defines a second signal program (`manual`) that SUMO activates by default, so the phase indices 0/2/4 pointed at near-all-red phases. The runner now selects the network's program `0`. V_NS and V_EW serve the opposing approach pairs 1+2 and 3+4; `P_ALL` is an all-red vehicle interval.
- `vehicle_demand` was ignored. The bundled flows (0.565 veh/s) are now rescaled with `--scale` to `demand.vehicle_rates_per_s` for the scenario, and the controller is told the vehicle arrival rate.
- Vehicle wait now uses SUMO's consecutive stopped time (`getWaitingTime`), and all metrics cover the evaluation window only. Vehicle approaches are mapped by edge (`1fi/1si` ... `4fi/4si`) instead of defaulting to one approach.
- `phase_switches` counts real phase changes; `pedestrian_served_virtual` counts virtual pedestrians actually served.

Yellow and all-red clearance (v3): a phase change now shows `signal.yellow_s` of yellow after a vehicle green and `signal.all_red_s` of all-red before the next vehicle green (leaving `P_ALL` needs none, entering it needs only the yellow). The minimum green counts from the moment the new green is displayed. This removed the hard-braking events (79 emergency stops in the 36 no-clearance runs, 0 with clearance). The earlier results are kept as `data/sumo_runs_v2_no_clearance/`. Note that the surrogate backend does not apply `yellow_s` / `all_red_s`.

Still open: pedestrians remain virtual, and the pedestrian clearance interval (`signal.pedestrian_clearance_s`) is not modelled.

Runner v0.4.1: parallel runs could pick the same TraCI port, so one run's client could talk to another run's SUMO (seen once in 36 runs as a bind error and a differing result). Start-up is now serialised with a file lock, each run checks its seed, scale and log path after connecting, and the output-only additional file is no longer loaded (parallel runs overwrote the same output files). Every run stores a `config_fingerprint`. The pilot was regenerated and reproduced the earlier results exactly.

Demand-based fixed-time plan (v4): `run_sumo_actual.py` applies `signal.fixed_timing: demand_based` to the fixed_time controller (splits from the scenario's nominal demand and the bundled route file's approach mix, cycle from `signal.fixed_cycle_s`). A wiring check is in `data/sumo_fixed_time_check/`. The pilot config now enables it with a 37 s cycle and the 9 fixed-time pilot runs were repeated; the earlier static-plan runs are in `data/sumo_runs_static_fixed_time/`.
