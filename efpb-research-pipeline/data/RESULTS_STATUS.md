# Status of the stored results

Current versions: surrogate `SIM_VERSION` 0.4.0, SUMO `RUNNER_VERSION` 0.5.0.

| Location | What | Status |
|---|---|---|
| `data/calibration_sweep/` (`freeze_report.md`, `selection.json`, `summary.csv`, `confirmation/`) | Surrogate calibration: 80 configurations x 8 scenarios x seeds 301-305, picks confirmed on seeds 321-350 | **Current.** Frozen in `configs/frozen_surrogate.yaml`. |
| `data/sumo_calibration/` (`freeze_report.md`, `selection.json`, `summary_selection.csv`, `selection/`, `confirmation/`) | SUMO calibration: 80 configurations x 7 scenarios x seeds 301-305, picks confirmed on seeds 361-370 | **Current.** Frozen in `configs/frozen_sumo.yaml` (all defaults kept). |
| `data/saturation_study/` | Demand ladder in both backends that fixed the new levels S and O | Current. |
| `data/sumo_runs/`, `data/processed/sumo_metrics.csv`, `sumo_analysis.json` | SUMO pilot (36 runs, 3 seeds), tuned fixed-time plan | Current, regenerated with runner 0.5.0. Uses `configs/experiments/sumo_emergency.yaml`, not the frozen files. |
| `data/sumo_runs_static_fixed_time/`, `data/sumo_runs_v2_no_clearance/`, `data/sumo_fixed_time_check/` (+ `data/processed/*_static_fixed_time.*`, `*_v2_no_clearance.*`) | Comparison sets for the pilot, re-created with runner 0.5.0 | Current comparison sets. |
| `data/matrix/` (1,920 surrogate runs, lean mode), `data/sumo_matrix/runs/` (520 SUMO runs, 4200 s), `data/results/` (analysis CSVs) | Matrix experiments with the frozen parameters: surrogate confirmatory_core + robustness + stress (30/10/30 seeds), SUMO 9 nominal + 4 stress cells x 4 controllers x 10 seeds | **Current.** Run 2026-09-19 without confirmation that the preregistration draft was registered first, so treat as exploratory unless it was. Descriptive analysis only (`analyze_matrix.py`); S11 excluded. |
| `data/runs/`, `data/processed/run_metrics.csv`, `analysis.json` | The old 1,540-run surrogate matrix | **Stale.** It predates surrogate 0.3.0 and 0.4.0 (capacity, arrival cap, waits of unserved people), the frozen parameters and the stress levels. Refused for reuse. Move aside and re-run once. |
| `data/runs_v1_no_clearance/`, `data/sumo_runs_v1_defective/`, `data/archive_surrogate_0_2_0/`, `data/archive_sumo_calibration_v1/` | Earlier versions | Archived for the record only. |

Nothing confirmatory has been run. The matrix experiments (`confirmatory_core`, `robustness`, `stress`; `ablations` is not ready, see `docs/preregistration_calibration.md`) extend `configs/frozen_surrogate.yaml`. To run them: move `data/runs/` and the two files `data/processed/run_metrics.csv` and `analysis.json` aside first, then `logs/run_surrogate_shards.sh`.

The calibration outputs carry `config_fingerprint`s; the simulators refuse to reuse a stored run made with another configuration or version.
