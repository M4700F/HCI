# Calibration sweep report

**Suggestions only. Nothing was frozen.** Values come from calibration scenarios and seeds only, on the surrogate backend.

- Scenarios: K_MM, K_LH, K_HL, K_HH, K_XX, K_SS, K_OO, K_HH_burst
- Seeds: 301, 302, 303, 304, 305
- Configurations: 80, runs: 3200
- Person delay = occupancy-weighted mean wait of the people served; max normalised wait = largest wait / its limit. Scenarios are weighted equally.
- `d_maxwait_vs_default` / `d_maxwait_se`: paired difference to the same controller's default configuration on identical demand, and its standard error. A difference under about 2 standard errors is not distinguishable from seed noise. `summary.csv` has the same columns for person delay.
- A best value on the edge of a swept grid means the grid should be widened before the value is trusted.

## Configurations per controller (parameter-selection budget)

- efficiency: 27
- efpb: 30
- equal_bargaining: 9
- fixed_time: 14

## efficiency: non-dominated configurations

| config_id | person_delay_s | max_norm_wait | d_maxwait_vs_default | d_maxwait_se | worst_scenario_max_norm_wait | starvation_violations | phase_switches | clearance_share | p:controller.horizon_s | p:controller.switch_cost | p:signal.service_duration_s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| efficiency__004 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 30 | 5 | 25 |
| efficiency__007 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 30 | 10 | 25 |
| efficiency__013 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 60 | 5 | 25 |
| efficiency__016 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 60 | 10 | 25 |
| efficiency__022 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 90 | 5 | 25 |
| efficiency__025 | 17.142 | 0.731 | 0.000 | 0.000 | 1.796 | 9.025 | 79.900 | 0.195 | 90 | 10 | 25 |
| efficiency__005 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 30 | 5 | 35 |
| efficiency__008 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 30 | 10 | 35 |
| efficiency__014 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 60 | 5 | 35 |
| efficiency__017 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 60 | 10 | 35 |
| efficiency__023 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 90 | 5 | 35 |
| efficiency__026 | 17.281 | 0.701 | -0.029 | 0.015 | 1.562 | 9.050 | 80.050 | 0.196 | 90 | 10 | 35 |

Current defaults (efficiency__013): person delay 17.142, max normalised wait 0.731, starvation violations 9.025.

## efpb: non-dominated configurations

| config_id | person_delay_s | max_norm_wait | d_maxwait_vs_default | d_maxwait_se | worst_scenario_max_norm_wait | starvation_violations | phase_switches | clearance_share | p:controller.debt_eta | p:controller.debt_kappa | p:controller.delta | p:controller.horizon_s | p:signal.service_duration_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| efpb__029 | 17.585 | 0.699 | -0.171 | 0.080 | 1.906 | 19.500 | 77.200 | 0.199 | 2 | 4 | 0.050 | 60 | 15 |

Current defaults (efpb__000): person delay 18.205, max normalised wait 0.870, starvation violations 22.475.

## equal_bargaining: non-dominated configurations

| config_id | person_delay_s | max_norm_wait | d_maxwait_vs_default | d_maxwait_se | worst_scenario_max_norm_wait | starvation_violations | phase_switches | clearance_share | p:controller.horizon_s | p:signal.service_duration_s |
|---|---|---|---|---|---|---|---|---|---|---|
| equal_bargaining__004 | 21.244 | 0.991 | 0.000 | 0.000 | 3.538 | 40.850 | 74.125 | 0.189 | 60 | 25 |
| equal_bargaining__007 | 21.244 | 0.991 | 0.000 | 0.000 | 3.538 | 40.850 | 74.125 | 0.189 | 90 | 25 |

Current defaults (equal_bargaining__004): person delay 21.244, max normalised wait 0.991, starvation violations 40.850.

## fixed_time: non-dominated configurations

| config_id | person_delay_s | max_norm_wait | d_maxwait_vs_default | d_maxwait_se | worst_scenario_max_norm_wait | starvation_violations | phase_switches | clearance_share | p:signal.fixed_cycle_s | p:signal.fixed_timing |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time__006 | 18.649 | 0.505 | 0.000 | 0.000 | 1.534 | 20.425 | 82.000 | 0.187 | 37 | demand_based |

Current defaults (fixed_time__006): person delay 18.649, max normalised wait 0.505, starvation violations 20.425.

## EFPB delta sensitivity (other parameters at their defaults)

| delta | person delay (s) | max normalised wait | starvation violations |
|---|---|---|---|
| 0.05 | 18.205 | 0.870 | 22.475 |
| 0.2 | 18.088 | 0.848 | 22.475 |

Chord-knee suggestion for delta: None. This is a starting point for judgement, not a selection.

## Limits

- Surrogate backend; the plan also calibrates the delay predictor against SUMO.
- Person delay covers people served before the end of the run; people still waiting are not counted.
- Parameters that are safety timings (minimum green, yellow, all-red) are not swept.
- equal_bargaining has no tunable parameter in this sweep; fixed_time is tuned only through its cycle length.
