# Freeze report (surrogate)

Rule: closest to ideal after min-max scaling within each controller (delay, max wait); safety exclusions applied.
Selection seeds: 301, 302, 303, 304, 305. Confirmation seeds: 30 new seeds (321-350).

## Picks and decisions

| controller | default | pick | delay pick-default (s) | max wait pick-default | adopted |
|---|---|---|---|---|---|
| fixed_time | fixed_time__006 | fixed_time__006 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efficiency | efficiency__013 | efficiency__013 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| equal_bargaining | equal_bargaining__004 | equal_bargaining__004 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efpb | efpb__000 | efpb__029 | +0.215 ± 0.098 | -0.0386 ± 0.0164 | yes |

## Frozen settings

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

## EFPB delta sensitivity (other efpb parameters at the picked values; confirmation seeds)

| delta | person delay (s) | max normalised wait | starvation violations | max wait vs picked |
|---|---|---|---|---|
| 0 | 17.376 | 0.6865 | 17.71 | -0.0050 ± 0.0045 |
| 0.02 | 17.376 | 0.6865 | 17.71 | -0.0050 ± 0.0045 |
| 0.05 | 17.370 | 0.6915 | 17.21 | +0.0000 ± 0.0000 |
| 0.1 | 17.329 | 0.6874 | 17.05 | -0.0041 ± 0.0022 |
| 0.2 | 17.344 | 0.6863 | 17.10 | -0.0053 ± 0.0028 |

## Confirmation results

| config | controller | person delay (s) | max normalised wait | worst scenario |
|---|---|---|---|---|
| efficiency__013 | efficiency | 16.405 | 0.6803 | 1.428 |
| efpb__000 | efpb | 17.155 | 0.7301 | 2.213 |
| efpb__029 | efpb | 17.370 | 0.6915 | 1.918 |
| efpb__sens_d0 | efpb | 17.376 | 0.6865 | 1.875 |
| efpb__sens_d0.02 | efpb | 17.376 | 0.6865 | 1.875 |
| efpb__sens_d0.1 | efpb | 17.329 | 0.6874 | 1.913 |
| efpb__sens_d0.2 | efpb | 17.344 | 0.6863 | 1.925 |
| equal_bargaining__004 | equal_bargaining | 19.455 | 0.9913 | 3.592 |
| fixed_time__006 | fixed_time | 18.168 | 0.5081 | 1.521 |
