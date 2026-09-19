# EFPB research methodology and implementation gap analysis

Status: Phase 1–3 analysis only. No experiment code has been implemented yet.

Sources reviewed:

- `explainable-pedestrian-vehicle-priority-research-plan.tex` (4,721 lines)
- `/Users/alifhasnain/Downloads/HCI.pdf` (66 pages; compiled copy of the same research plan)
- `https://github.com/Hasucat/HCI-Project.git` (empty repository; no commits or tracked files)

The PDF contains the same research plan as the TeX source. It does not add a separate executable specification. The user request is the governing implementation instruction; the research plan is the methodology to preserve.

## 1. Research understanding

### Objective

Evaluate Explainable Fair Priority Bargaining (EFPB) as a transparent, starvation-safe, efficiency-bounded allocator of safe service between pedestrian and vehicle modes at one isolated four-arm signalized intersection, and test whether trace-faithful factual and counterfactual explanations improve human comprehension, perceived procedural/informational fairness, and calibrated reliance.

The claim is deliberately narrower than “Nash bargaining is new” or “people are Nash-rational.” The proposed novelty is the combination of constrained multimodal allocation, a machine-verifiable DecisionTrace, replay-validated counterfactual explanations, and a controlled HCI evaluation.

### Research questions

1. Can EFPB reduce severe pedestrian/vehicle waiting disparity and starvation relative to fixed-time and efficiency-only adaptive control while remaining within its declared efficiency tolerance?
2. How sensitive are efficiency and fairness to efficiency tolerance, waiting debt, demand mix, accessibility/walking speed, sensor error, and emergency demand?
3. Does a faithful factual explanation improve identification of why priority was assigned?
4. Does a solver/replay-validated counterfactual improve understanding of what would flip the decision, and at what time cost?
5. Do explanations improve discrimination between sound and procedurally anomalous but physically safe decisions, rather than simply increasing trust?

### Hypotheses

- H1: Factual (F) and factual-plus-counterfactual (FC) interfaces improve factual-rationale accuracy over decision-only (D).
- H2: FC improves contrastive/decision-flip accuracy over F and D.
- H3: explanation condition interacts with sound versus anomalous decision quality, improving calibration/appropriate endorsement rather than uniformly increasing trust.
- H4: F and FC improve procedural and informational fairness judgments for sound decisions without erasing the penalty for anomalous decisions.
- H5: FC may increase inspection time; its benefit is an accuracy–time trade-off, not a presumed speed improvement.

### Contribution and limits

The planned contribution has algorithmic, technical/XAI, HCI, ITS, experimental, and engineering parts. The document explicitly treats the algorithmic novelty as incremental relative to Wang et al.’s pedestrian/vehicle bargaining work. It requires a faithful closest bargaining baseline, calibration, sensitivity analysis, and null-result reporting. SUMO evidence is not field safety evidence, and the dashboard is an audit/replay interface, not a driver-facing or roadside crossing display.

## 2. Complete methodology extracted

### Control and simulation workflow

1. Use one isolated four-arm, through-only intersection with four inbound/outbound vehicle lanes, four marked crosswalks, waiting areas, and no turns in the primary study.
2. Use three service phases: `P_ALL`, `V_NS`, and `V_EW`, with legal WALK/change/clearance and yellow/all-red transitions owned by SUMO and a safety kernel.
3. Sample controller state at 1 Hz. Use rolling arrival windows (pilot candidates: 30/60/120 s), a sensor abstraction, and explicit missing/stale/degraded states.
4. Represent pedestrian and vehicle service as two stateless virtual advocates. Vehicle-direction service is selected by total-delay max-pressure between NS and EW.
5. Enumerate a finite horizon action set containing current continuation, phase extensions, and short service-phase sequences. Reject unsafe, conflicting, impossible-transition, clearance-truncating, emergency-incompatible, and avoidable max-wait-breach plans.
6. Predict service, mode utility, delay, and tail wait with a deterministic queue-discharge predictor calibrated against SUMO and validated on held-out rollouts.
7. Apply the lexicographic pipeline: legal safety and emergency handling → maximum-wait/starvation protection → near-efficient filtering → weighted Nash bargaining.
8. Execute the chosen target through the signal safety state machine. Use fixed-time fallback for invalid/stale sensors. Preserve displaced debt after emergency preemption and enter recovery.
9. Log state, candidates, predicates, scores, chosen action, execution receipt, events, and latency. Generate an immutable trace and deterministic explanation from trace slots only.
10. Replay counterfactual perturbations through the same controller and release only a real decision flip; otherwise abstain.
11. Generate common-random-number scenario manifests once and run all controllers on the same manifest/seed.
12. Aggregate validated runs, analyze at run level, generate figures/tables, and export immutable replay stimuli for the HCI study.

### Mathematical model

- Modes: `p` and `v`; vehicle approaches and crosswalks: N/S/E/W; phases: `P_ALL`, `V_NS`, `V_EW`; time step `Delta t = 1 s`.
- Pedestrian demand: queue count, mean/max waiting time, rolling-window arrival rate, density, and `D_p = sum_c(n_c^p + H lambda_c^p)`.
- Vehicle demand: stop-threshold queue count, stopped waiting time, mean/max waiting, rolling arrival rate, and `D_v = sum_r(q_r^v + H lambda_r^v)`.
- Normalization: `clip(x / s_x, 0, 1)` using frozen operational limits or calibration quantiles; test 90th/95th/99th percentile scales.
- Service utility: `u_m(a,t) = min(1, S_m(a,t) / max(1,D_m(t)))`.
- Disagreement: safe fallback utility `d_m(t) = u_m(a_t^0,t)`; individual rationality requires every mode’s candidate utility to be at least its fallback utility.
- Waiting debt: `r_m = clip(W_m/T_m^max,0,1)`, raw weight `pi_m[1 + kappa*r_m^eta]`, normalized across modes.
- Starvation protection: predicted maximum wait must be within each mode’s limit. If no candidate satisfies it, lexicographically minimize number of breaches, largest normalized breach, then efficiency loss; never relax safety.
- Efficiency loss: `L_eff = sum_m c_m * predicted_delay_m + c_sw * switches`.
- Near-efficient set: candidates within `L_min + delta * max(L_min, L_floor)` over the starvation-feasible set.
- Weighted Nash decision: maximize `sum_m omega_m * log(u_m - d_m + epsilon)` over near-efficient individually rational candidates; ties use lower normalized tail wait, fewer switches, then stable candidate ID.
- Direction pressure: `P_g = sum_r in g (upstream delay - downstream delay)` for `g in {NS,EW}`; choose the larger legal pressure when a vehicle slot is allocated.
- Counterfactual: minimize normalized L1 perturbation over declared discrete controllable state changes, replaying the actual controller until the target alternative wins while immutable and safety facts remain unchanged.

### Fairness

Fairness is layered: safety fairness; minimum service/max-wait fairness; proportional allocative fairness from weighted Nash bargaining; outcome distributions; procedural consistency; and separately measured perceived fairness. Required run-level measures include service ratios, nullable two-mode Jain index, normalized mean wait disparity, normalized 95th-percentile disparity, maximum waits, exceedance counts, and the total-delay/maximum-normalized-wait Pareto frontier. Jain alone is explicitly insufficient.

### Explainability and DecisionTrace

Every decision must retain the exact input state/configuration hash, sensor freshness, candidates and rejected predicates, utility/disagreement/gain/weight/loss/Nash values, chosen plan, tie-break path, binding constraints, override/fallback status, top reason facts, best rejected alternative, counterfactual search bounds and replay proof, execution receipt, software/controller version, and hashes.

The `ExplanationRecord` contains `decision_id`, timestamp, audience, decision summary, up to three validated reason facts, binding constraints, alternative, counterfactual, override, freshness, uncertainty note, template ID, trace hash, and validation status. Templates are deterministic and slot-bound; no LLM or generic post-hoc prose is permitted. Binding means the predicate is actually evaluated and within configured slack tolerance. Counterfactuals are displayed only after replay validation and minimality audit.

### Scenario design

Demand levels are relative to empirically estimated capacity: L ≈ 25%, M ≈ 50%, H ≈ 75%, X ≈ 90–100%. The factorial core is pedestrian demand `{L,M,H}` × vehicle demand `{L,M,H}` × controller, with asymmetric NS/EW splits and Poisson and bursty Markov-modulated demand processes. Targeted scenarios are:

| ID | Purpose | Key condition |
|---|---|---|
| S1 | Nominal fairness/efficiency | Balanced M/M |
| S2 | Pedestrian responsiveness | Ped H / veh M |
| S3 | Vehicle responsiveness | Ped M / veh H |
| S4 | Tail protection | Low current count, initialized wait near limit |
| S5 | Direction allocation | High NS vehicle wait |
| S6 | Trade-off stress test | Ped H / veh H |
| S7 | Emergency handling | NS emergency during ordinary phase |
| S8 | Temporal debt | Pedestrian imbalance followed by vehicle surge |
| S9 | Graceful overload | Both X / finite downstream capacity |
| S10 | Low-demand sanity | Both L |
| S11 | Accessibility | Mobility-impaired slower walking/extension request |
| S12 | Sensor robustness | Missed pedestrians, stale vehicles, recovery |

Each manifest must freeze rates/routes/process, walking-speed distribution, vehicle type/occupancy, emergency schedule, sensor model, durations, seed streams, controller, network, and experiment version.

### Baselines

- B0 fixed-time: operational reference; timing calibrated with the same budget and shared safety timings.
- B1 efficiency-only adaptive: minimum predicted total person delay or total-delay max-pressure over the same horizon/action set.
- B2 equal-weight/Wang-style bargaining: closest reproduction possible on the simplified three-phase geometry, with deviations disclosed.
- B3 EFPB without UI explanation: technical controller condition.
- B4 EFPB + factual explanation: same decisions as B3; UI effect only.
- B5 EFPB + factual + counterfactual: same decisions as B3/B4; contrastive-information effect.

B0–B3 are technical simulation comparators. B3–B5 reuse the same traces for HCI; separate traffic runs would be invalid because explanation cannot affect SUMO.

### Metrics and statistics

Technical metrics: mode/person/vehicle delay, wait distributions and 95th/max tails, queues, throughput, service ratio, starvation exceedances and seconds, phase switches, emergency response, safety invariants, controller latency, fairness, and realized efficiency-bound compliance. Explanation metrics: record fidelity, counterfactual validity, constraint precision, coverage by decision class, reason stability, and generation/search latency. HCI metrics: factual/contrastive/constraint comprehension, response time, confidence/Brier score, appropriate endorsement, quality discrimination/AUROC, trust, procedural/distributive/informational fairness, SUS, and optional explanation satisfaction.

Simulation analysis treats a complete run as the unit, with controller fixed effects and scenario/paired-seed blocking. Planned models include `metric ~ controller * scenario_family + (1|seed)`, appropriate log/Gamma/count models, paired/bootstrap CIs, diagnostics, rank-based sensitivity, and Holm adjustment. HCI uses logistic GLMMs for correctness/endorsement, LMMs for log response time and suitable composites, cumulative-link mixed models for ordinal ratings, planned contrasts D/F/FC, and explanation × quality interactions. Pilot-derived exclusions, missingness, reliability/omega, convergence, and all deviations are reported.

### Ablations and sensitivity

A1 efficiency-only; A2 no starvation constraint; A3 no efficiency filter; A4 equal/static weights; A5 tuned weighted sum; A6 sensor fallback off; A7 decision-only UI; A8 factual-only UI. Sensitivity varies `delta`, `kappa`, `eta`, horizon, normalization quantile, arrival window, walking speed, occupancy, sensor error, and seed.

### HCI protocol

Within-participant 3 explanation conditions (D/F/FC) × 2 decision-quality conditions (sound/anomalous), 18 scored trials per participant in three six-trial blocks, matched scenario sets, Williams/Latin-square order, 90 usable participants as an initial target, and 102–108 recruitment target before pilot power finalization. Anomalies must be physically safe and faithfully disclose the faulty rule. The study requires ethics approval, accessibility support, stable local replays, monotonic browser timing, and no participant interaction while driving/crossing.

## 3. Research requirement → existing implementation → gap → planned change

| Research requirement | Existing implementation | Gap | Required change |
|---|---|---|---|
| EFPB controller and equations | None; only prose/LaTeX | Complete | Typed pure-Python domain, predictor, candidate evaluator, EFPB controller, config tests |
| Four-arm SUMO network | None | Complete | Versioned network/TLS/detectors/routes and network invariant tests |
| Safety/clearance/emergency kernel | None | Complete | Explicit signal FSM, conflict matrix, clearance, preemption/recovery |
| Pedestrian/vehicle sensor abstraction | None | Complete | TraCI adapter, state collector, quality/staleness/noise layer |
| Baselines B0–B5 | None | Complete | Fixed-time, efficiency, equal bargaining, EFPB, and UI replay conditions |
| Scenario manifests/common seeds | None | Complete | Independent RNG streams, immutable hashed manifests, factorial/stress configs |
| DecisionTrace/explanations | None | Complete | Versioned schemas, JSONL trace, deterministic templates, validators |
| Counterfactual replay | None | Complete | Deterministic discrete search with replay proof/minimality audit |
| Traffic/fairness/explanation metrics | None | Complete | Run-level metrics and cross-checks against SUMO trip/person outputs |
| Experiment scheduler | None | Complete | Resumable unique run IDs, no overwrite, machine partitioning, validation |
| Calibration | None | Complete | Calibration-only sweeps and held-out predictor comparison |
| Statistics/figures/tables | None | Complete | Raw-data-consuming Python/R analysis and publication figures/tables |
| HCI stimulus generation | None | Complete | Matched D/F/FC replay packs, hashes, scoring keys, balance tests |
| Dashboard/API | None | Complete/secondary | Optional after core pipeline; same renderer for replay/live audit |
| Reproducibility | None | Complete | Locks, environment metadata, commit/config hashes, README, mini release |

## 4. Methodological ambiguities that must not be silently invented

The plan intentionally delegates these to standards, calibration, pilot, or preregistration. They will be configuration values with provenance and sensitivity coverage, not hidden constants:

1. Governing jurisdiction/standard, intersection dimensions, speed limit, lane geometry, WALK/clearance/yellow/all-red durations.
2. SUMO release and exact network topology/link indices.
3. Capacity estimate and numeric L/M/H/X rates, route distributions, burst process parameters, vehicle occupancy/type mix, and walking-speed distributions.
4. Queue-discharge/prediction equations and calibrated saturation/walking parameters.
5. `T_p^max`, `T_v^max`, base weights `pi`, debt parameters `kappa`/`eta`, `epsilon`, `L_floor`, delay/switch cost units `c_m`/`c_sw`, horizon `H`, duration grid, fallback policy, and stale/quality thresholds.
6. B1 choice between minimum predicted total person delay and total-delay max-pressure; B2 mapping from Wang’s four-phase formulation to this three-service-phase network.
7. Emergency release condition, maximum emergency service duration, recovery schedule, and signed-event representation.
8. Counterfactual feature whitelist, grids/ranges, perturbation distance cap, and immutable state fields.
9. Exact seed counts for robustness, sensitivity, ablation, and HCI stimulus-generation pools. The document specifies at least 30 paired seeds for the main study, adding batches of 10 to a CI half-width rule up to 100; it does not enumerate every secondary cell.
10. HCI power finalization, adapted justice-scale wording, recruitment/accessibility logistics, and approved response storage.
11. Dataset access/licensing: IMPTC is recommended for calibration, SinD is a sensitivity source, and U.S. DOT data are optional robustness data. Full-data access is not guaranteed.

These are research decisions. The implementation will include calibration/sensitivity commands and will label provisional defaults as non-confirmatory until frozen.

## 5. Current phase conclusion

The repository is a blank starting point, so there is no working functionality to preserve or reuse. The correct implementation order is: repository bootstrap and network/safety smoke test → typed state and manifests → B0/B1/B2 → EFPB and trace → counterfactual validation → batch runner/metrics → calibration/benchmark → full matrix → analysis/figures → replay stimuli/dashboard.

No experiment has been run and no result, runtime measurement, significance claim, or calibration value should yet be presented as empirical evidence.
