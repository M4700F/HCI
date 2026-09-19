# Calibration preregistration (DRAFT)

Generated 2026-09-19 by `make_preregistration.py`. **Status: draft.** It becomes a preregistration only when it is registered with a timestamp outside this repository, before the confirmatory runs. Any change after that is a deviation and must be recorded in section 8.

## 1. Scope

This document fixes the calibration decisions of the EFPB research plan: demand levels, the tuning-budget policy, the selection and confirmation rules, and the resulting frozen parameters for each backend. It does not change the research questions, hypotheses, outcome measures or statistical models of `explainable-pedestrian-vehicle-priority-research-plan.tex`, and it says nothing about the HCI study.

## 2. Demand levels

Two levels were added to the existing L, M, H, X (`configs/design_base.yaml`), chosen from a saturation study (`data/saturation_study/`, calibration seeds only) that ran all controllers at their then-current defaults on a ladder of multiples of X in both backends:

| level | pedestrians / s | vehicles / s | meaning |
|---|---|---|---|
| S | 0.225 | 0.66 | 1.5 x X: near saturation (SUMO at about 90% of its ~0.62 veh/s capacity) |
| O | 0.300 | 0.88 | 2.0 x X: over saturation (SUMO about 140%; surrogate fixed-time plan collapses) |

The old top level X (0.15 / 0.44) is about half of capacity, so the earlier cells could not separate the controllers.

## 3. Tuning-budget policy

Each controller is evaluated on at most **30 configurations** drawn from its own declared search space; the default configuration is always included. A space of 30 or fewer configurations is searched exhaustively; a larger one by seeded random search (seed 0). No controller gets more tuning than another. Search spaces (`configs/experiments/calibration_sweep.yaml`, `sumo_calibration.yaml`):

| controller | tuned parameters | configurations |
|---|---|---|
| fixed_time | plan family (static / demand-based) and cycle length | 14 |
| efficiency | horizon (30, 60, 90 s), service duration (15, 25, 35 s), switch cost (0, 5, 10) | 27 |
| equal_bargaining | horizon, service duration (equal weights are by definition, not tuned) | 9 |
| efpb | horizon, service duration, delta (0, .05, .10, .20), kappa (0, 2, 4), eta (1, 2) | 30 of 180 |

Safety timings (minimum green 10 s, yellow 3 s, all-red 1 s) are set by the standards assumed in the plan and are not tuned.

## 4. Selection rule (per controller and backend)

Objectives, computed over everyone who arrived after warm-up (people still waiting at the end count with the wait so far): **person delay** (occupancy-weighted mean wait, occupancy 1.3 for vehicles) and **max normalised wait** (largest wait divided by its 100 s limit). Scenarios are weighted equally; selection seeds 301-305; calibration scenarios `K_*` (surrogate: MM, LH, HL, HH, XX, SS, OO, bursty HH; SUMO: the same without the bursty cell). Each controller's configurations are scaled to 0-1 on each objective within that controller; the configuration closest to the ideal point (0, 0) is picked. An exact tie keeps the default, then the lower max wait, then the lower id. In SUMO, configurations with any collision are excluded. Picks are written to `selection.json` before any confirmation run.

## 5. Confirmation and adoption rule

The picked and default configurations are run on fresh seeds (surrogate 321-350, SUMO 361-370). A pick replaces the default unless it is worse than the default in **both** objectives (paired means over identical scenarios and seeds). EFPB's delta sensitivity set {0, .02, .05, .10, .20} is run around the adopted configuration on the same seeds and reported in full.

## 6. Frozen parameters

### Surrogate backend

| controller | default | pick | delay pick-default (s) | max wait pick-default | adopted |
|---|---|---|---|---|---|
| fixed_time | fixed_time__006 | fixed_time__006 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efficiency | efficiency__013 | efficiency__013 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| equal_bargaining | equal_bargaining__004 | equal_bargaining__004 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efpb | efpb__000 | efpb__029 | +0.215 ± 0.098 | -0.0386 ± 0.0164 | yes |

```yaml
signal:
  fixed_cycle_s: 37
  fixed_timing: demand_based
per_controller:
  efpb:
    controller:
      debt_eta: 2
      debt_kappa: 4
    signal:
      service_duration_s: 15
```

File: `configs/frozen_surrogate.yaml`, sha256 `3e834bca1280e8a9f8ebfda60612fa88ca1b01707d0a858e07515b90371e90e6`. Selection results sha256 `099790d1ddf69457c56ba9f6ef344c8bb298da452b42f373f6066cca7065ed7c`.

### SUMO backend

| controller | default | pick | delay pick-default (s) | max wait pick-default | adopted |
|---|---|---|---|---|---|
| fixed_time | fixed_time__006 | fixed_time__006 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efficiency | efficiency__013 | efficiency__001 | +0.186 ± 0.090 | +0.0009 ± 0.0102 | no (kept default) |
| equal_bargaining | equal_bargaining__004 | equal_bargaining__004 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efpb | efpb__000 | efpb__006 | +2.030 ± 3.726 | +0.0476 ± 0.1424 | no (kept default) |

```yaml
signal:
  fixed_cycle_s: 37
  fixed_timing: demand_based
```

File: `configs/frozen_sumo.yaml`, sha256 `ac7d1d176ff5f663a53dc74e0b42292098d16567fdb15eae25ae9211181cd449`. Selection results sha256 `1e08105f01452057ced1dda4bcf89a11970902c2644eca02fe51c98010d031ef`.


## 7. Experiments defined for the confirmatory phase

| experiment | config | cells | controllers | seeds | runs |
|---|---|---|---|---|---|
| confirmatory_core | `configs/experiments/confirmatory_core.yaml` | 9 | 4 | 30 (1001-1030) | 1080 |
| robustness | `configs/experiments/robustness.yaml` | 9 | 4 | 10 (2001-2010) | 360 |
| ablations | `configs/experiments/ablations.yaml` | 5 | 2 | 10 (3001-3010) | 100 |
| stress | `configs/experiments/stress.yaml` | 4 | 4 | 30 (1101-1130) | 480 |

The **ablations experiment is not ready**: its five cells are identical in behavior because the ablated controllers (no starvation guard, no efficiency filter, static weights, weighted sum) are not implemented.

## 8. Disclosures and deviations

- The surrogate was corrected before calibration: service capacity now uses the configured fractional rates (vehicles 0.8/s per approach, previously rounded up to 1/s); the demand generator can produce more than one arrival per second; waits include people still queued at the end of a run (surrogate 0.4.0, SUMO runner 0.5.0).
- A first surrogate selection was made on data produced with a bug (fixed-time splits were mis-scaled, so one vehicle phase was never served) and with waits that ignored unserved people. I saw its confirmation results before discarding it. All selections and confirmations in this document were redone with the corrected code from scratch.
- After that first attempt an exact tie in the selection rule changed a parameter for no measurable reason; the rule was refined so that ties keep the default. I saw that tie before changing the rule.
- Both backends have their own frozen file. The surrogate is engineering validation only; SUMO uses virtual pedestrians.
- The matrix experiments (`data/matrix/` surrogate, `data/sumo_matrix/` SUMO) were started on 2026-09-19 at 17:39 without confirmation that this draft had been registered. If it was not registered before that time, the results are exploratory, not confirmatory.
- Scenario S11 (accessibility) is excluded from the analysis: the simulator keeps its accessibility flag on for the whole run, which marks every vehicle plan unsafe, so vehicles are never served by any controller. The exclusion follows from the code, not from the outcomes. S7 (emergency: a single-second request) and S12 (all controllers fall back to the same fixed plan) are valid but barely informative as implemented.
- The SUMO experiment uses 10 paired seeds (the plan's design has 30 for the confirmatory core) because of the time available.
- Later deviations must be listed here with date and reason.

