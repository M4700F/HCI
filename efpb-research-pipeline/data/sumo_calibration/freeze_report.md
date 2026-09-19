# Freeze report (sumo)

Rule: closest to ideal after min-max scaling within each controller (delay, max wait); safety exclusions applied.
Selection seeds: 301, 302, 303, 304, 305. Confirmation seeds: 10 new seeds (361-370).

## Picks and decisions

| controller | default | pick | delay pick-default (s) | max wait pick-default | adopted |
|---|---|---|---|---|---|
| fixed_time | fixed_time__006 | fixed_time__006 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efficiency | efficiency__013 | efficiency__001 | +0.186 ± 0.090 | +0.0009 ± 0.0102 | no (kept default) |
| equal_bargaining | equal_bargaining__004 | equal_bargaining__004 | +0.000 ± 0.000 | +0.0000 ± 0.0000 | yes |
| efpb | efpb__000 | efpb__006 | +2.030 ± 3.726 | +0.0476 ± 0.1424 | no (kept default) |

## Frozen settings

```yaml
signal:
  fixed_cycle_s: 37
  fixed_timing: demand_based
```

## EFPB delta sensitivity (other efpb parameters at the picked values; confirmation seeds)

| delta | person delay (s) | max normalised wait | starvation violations (surrogate) / collisions (SUMO) | max wait vs picked |
|---|---|---|---|---|
| 0 | 19.287 | 0.4846 | 0.00 | +0.0000 ± 0.0000 |
| 0.02 | 19.287 | 0.4846 | 0.00 | +0.0000 ± 0.0000 |
| 0.05 | 19.287 | 0.4846 | 0.00 | +0.0000 ± 0.0000 |
| 0.1 | 19.288 | 0.4830 | 0.00 | -0.0016 ± 0.0015 |
| 0.2 | 19.327 | 0.4826 | 0.00 | -0.0020 ± 0.0023 |

## Confirmation results

| config | controller | person delay (s) | max normalised wait | worst scenario |
|---|---|---|---|---|
| efficiency__001 | efficiency | 16.741 | 0.5074 | 0.864 |
| efficiency__013 | efficiency | 16.555 | 0.5066 | 0.878 |
| efpb__000 | efpb | 17.257 | 0.4370 | 0.582 |
| efpb__006 | efpb | 19.287 | 0.4846 | 1.459 |
| efpb__sens_d0 | efpb | 19.287 | 0.4846 | 1.459 |
| efpb__sens_d0.02 | efpb | 19.287 | 0.4846 | 1.459 |
| efpb__sens_d0.1 | efpb | 19.288 | 0.4830 | 1.459 |
| efpb__sens_d0.2 | efpb | 19.327 | 0.4826 | 1.459 |
| equal_bargaining__004 | equal_bargaining | 30.644 | 2.2329 | 8.990 |
| fixed_time__006 | fixed_time | 24.121 | 0.6210 | 2.522 |
