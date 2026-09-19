# Implementation status

## Implemented and verified

- Time-boxed real-SUMO/TraCI runner for vehicle movement and signal execution (`run_sumo_actual.py`) plus deterministic two-machine batching (`run_sumo_batch.py`).

- YAML configuration inheritance and SHA-256 configuration hashes.
- Immutable seeded demand manifests with paired controller inputs.
- Typed state, candidate, decision, DecisionTrace, explanation, and validation objects.
- Fixed-time, efficiency-only, equal-weight bargaining, and EFPB decision logic.
- Waiting debt, weighted Nash score, individual rationality, near-efficiency filtering, max-wait fallback, emergency choice, direction selection, and deterministic tie-breaking.
- Counterfactual replay search with an explicit “no flip within range” result.
- Trace-bound factual/contrastive explanation generation and hash/slot validation.
- Resumable unique run directories and structured JSON/CSV/JSONL outputs.
- Smoke, calibration, benchmark, aggregation, descriptive analysis, figures, and stimulus commands.
- 5 automated tests, including an end-to-end 8-run smoke test.
- Measured surrogate benchmark: 3.144 seconds for one 660-second run on the development Mac.

- Surrogate `SIM_VERSION` 0.2.0: yellow/all-red clearance, waits/service ratios/throughput over the evaluation window, and scenario arrival rates passed to the controller. Runs stored under another version are refused, not reused. The stored 1,540-run results predate this version (see `data/RESULTS_STATUS.md`).
- Tuned demand-based fixed-time plan (`signal.fixed_timing: demand_based`, 37 s cycle) enabled in the SUMO pilot and the four surrogate experiment configs; applied to every controller so that the sensor fallback is consistent. The stored 1,540-run results predate it.
- Config fingerprints on stored runs (surrogate and SUMO batch), a locked and verified TraCI start-up, and regenerated calibration, sweep and pilot outputs that reproduced the earlier results exactly.
- SUMO fixed-time calibration (`sweep_sumo_calibration.py`): 14 plans, selection seeds plus held-out confirmation; the 37 s demand-based plan is confirmed.
- Calibration phase: saturation study and demand levels S and O (`configs/design_base.yaml`), equal-budget tuning of all four controllers in both backends, confirmation on fresh seeds and frozen parameter files (`configs/frozen_surrogate.yaml`, `configs/frozen_sumo.yaml`), with a preregistration draft (`docs/preregistration_calibration.md`). Surrogate 0.4.0 and SUMO runner 0.5.0 count everyone in the waits, including people still queued at the end.

## Not yet evidence-complete

- Scenario S11 (accessibility) is broken in the simulator: `accessibility_extension` stays on for the whole run, which marks every vehicle plan unsafe. Pedestrian walking/crossing time is not modelled at all. The analysis excludes S11.
- The ablation variants (no starvation guard, no efficiency filter, static weights, weighted sum) are not implemented: the five ablation cells are identical.
- `equal_bargaining` starves pedestrians completely under near- and over-saturation because its individual-rationality rule never leaves a vehicle phase while vehicles are queued; confirm this matches the intended baseline before the confirmatory runs.

- The general run backend remains an in-process surrogate, but the emergency runner now provides a separate real-SUMO/TraCI path. Its pedestrian demand is virtual and `P_ALL` is a vehicle-phase proxy because the bundled legacy network has no validated pedestrian walking areas; this is not complete multimodal evidence.
- The SUMO configuration/network files are provided, but the local pip-installed SUMO binary did not return from `sumo --version` during validation. A working SUMO installation on each experiment machine is required.
- Full TraCI state collection, legal SUMO signal-transition execution, pedestrian route validation, and online/offline SUMO metric cross-checking are not yet validated.
- Statistical scripts currently produce descriptive JSON only. The preregistered GLMM/LMM/ordinal analyses still require the full analysis implementation and real run/HCI data.
- The browser dashboard and participant response application are not implemented; the current stimulus export is a trace-pack generator, not an ethics-ready study host.
- Calibration values in `configs/intersection.yaml` are provisional and must be frozen only after calibration and standards review.

Therefore, the repository is a reproducible engineering scaffold and surrogate pipeline, not yet a completed SUMO/HCI research result package. The paper template marks empirical sections as TBD for this reason.
