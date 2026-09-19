# Explainable Fair Priority Bargaining (EFPB)

This repository is an executable research scaffold for the methodology in `explainable-pedestrian-vehicle-priority-research-plan.tex`. It currently provides a deterministic standard-library surrogate backend for smoke tests, calibration scaffolding, trace generation, counterfactual replay, aggregation, descriptive analysis, figures, and stimulus export. Surrogate output is not SUMO evidence and must not be reported as a traffic finding.

Read [docs/implementation-status.md](docs/implementation-status.md) before treating any output as research evidence. The paper template is intentionally results-ready but does not contain fabricated findings.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,analysis]'
```

Install SUMO separately using [SUMO_SETUP.md](SUMO_SETUP.md). The current environment used for development had Python 3.9 and no SUMO; the code supports Python 3.9+.

After generating `sumo/net/intersection.net.xml`, validate the SUMO installation/network separately:

```bash
export SUMO_HOME=/path/to/sumo
export PATH="$SUMO_HOME/bin:$PATH"
bash sumo/build_network.sh
PYTHONPATH=src python validate_sumo.py
```

This validation command checks that SUMO can load the network. It is not a substitute for the TraCI controller integration validation required before confirmatory claims.

## One-day real-SUMO run

For an actual SUMO/TraCI run, use the emergency matrix. It uses SUMO vehicle movement and signal execution; its pedestrian demand is a reproducible virtual queue because the bundled legacy network has no validated pedestrian walking areas. See [SUMO_EMERGENCY_SCOPE.md](SUMO_EMERGENCY_SCOPE.md).

```bash
PYTHONPATH=src python run_sumo_actual.py --config configs/experiments/sumo_emergency.yaml --scenario S1_balanced --controller efpb --seed 9001
PYTHONPATH=src python run_sumo_batch.py --config configs/experiments/sumo_emergency.yaml --machine 1 --machines 2
```

The two machines use `--machine 1` and `--machine 2` respectively. The matrix contains 36 independent SUMO runs, with paired seeds across controllers.

After copying both machines' `data/sumo_runs/` directories together:

```bash
python aggregate_sumo.py --input data/sumo_runs --output data/processed/sumo_metrics.csv
python analyze_sumo.py --input data/processed/sumo_metrics.csv --output data/processed/sumo_analysis.json
```

## Verify

```bash
python -m pytest -q
python run_experiment.py --config configs/experiments/smoke.yaml
python aggregate.py --input data/runs --output data/processed/run_metrics.csv
python analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json
python generate_figures.py --input data/processed/run_metrics.csv --output data/figures
python build_stimuli.py --input data/runs --output data/stimuli
```

The smoke configuration runs 2 scenarios × 4 controllers × 1 paired seed = 8 runs. Each run stores its resolved config, manifest, states, JSONL DecisionTrace records, explanations, events, metrics, and validation summary below `data/runs/`.

## Calibration sweep

```bash
python sweep_calibration.py --dry-run     # list configurations and run counts
python sweep_calibration.py               # run the sweep (about a minute on 8 workers) and write data/calibration_sweep/
```

`configs/experiments/calibration_sweep.yaml` defines calibration-only scenarios (`K_*`) and seeds (301-305) and a parameter grid per controller. The sweep refuses seeds or scenarios used by the confirmatory, robustness, ablation or SUMO experiments. It writes `report.md`, `pareto.png`, `summary.csv` and `pareto.json` with paired differences to each controller's defaults and their standard errors. It only suggests values; it never edits `configs/intersection.yaml`, so freezing stays a reviewed decision.

Fixed-time plans can be `static` (default: `signal.fixed_cycle_s` with the configured splits) or `demand_based` (`signal.fixed_timing: demand_based`): each scenario's nominal demand sets the splits, with minimum-green floors, and only the cycle length is tuned. The rule is in `src/efpb/timing.py`. The surrogate and the SUMO runner both apply it (the SUMO runner also uses the bundled route file's approach mix). To try it in SUMO, extend a SUMO config with `signal: {fixed_timing: demand_based, fixed_cycle_s: 37}`; `configs/experiments/sumo_emergency.yaml` and the surrogate experiment configs (`confirmatory_core`, `confirmatory`, `robustness`, `ablations`) now enable it with a 37 s cycle; the calibration, smoke and benchmark configs keep the untuned defaults. The plan is applied to every controller, because all of them fall back to the fixed-time plan when sensors are degraded. `run_sumo_actual.py` has an optional `--output-root`.

## Calibration, freeze and preregistration

1. `python sweep_calibration.py` (surrogate) or `python sweep_sumo_calibration.py` (SUMO): every controller on its own search space under the same budget (30 configurations), calibration scenarios `K_*` and seeds 301-305.
2. `python freeze_calibration.py --backend surrogate|sumo`: applies the pre-declared rule (`src/efpb/selection.py`), writes `selection.json` before any confirmation run, confirms the picks and the defaults on fresh seeds, and writes `configs/frozen_<backend>.yaml` plus `freeze_report.md`. It will not re-pick if the selection results change.
3. `python make_preregistration.py`: rewrites `docs/preregistration_calibration.md` from the frozen files. The draft only becomes a preregistration when you register it with a timestamp outside this repository.

`configs/design_base.yaml` adds the demand levels S (near saturation) and O (over saturation). Experiment configs extend `configs/frozen_surrogate.yaml`; per-controller parameters live under `per_controller:`.

## Run report

`python docs/make_report.py` rebuilds `../EFPB_Experiment_Run_Report.pdf` from the stored result files (needs `reportlab` and `pyyaml`; not in the project environment). Every table is read from the results, so rerun it after any new results.

## SUMO fixed-time calibration

```bash
python sweep_sumo_calibration.py --dry-run     # list configurations and run counts
python sweep_sumo_calibration.py               # selection on seeds 301-305, then confirmation of the finalists on held-out seeds
```

`configs/experiments/sumo_calibration.yaml` sweeps the fixed-time plan (static and demand-based, several cycle lengths) in SUMO/TraCI on calibration scenarios (`K_*`) and seeds only; the pilot's seeds and scenarios are refused. Results go to `data/sumo_calibration/` (`report.md`, `pareto.png`, summaries). It suggests values and freezes nothing. SUMO start-up is serialised for safety, so expect about a second per run regardless of workers.

## Reusing stored runs

Finished runs are reused only when they match. Every surrogate run stores `sim_version` and a `config_fingerprint` (a hash of the settings, scenario, controller and seed; names and run lists are ignored), and the simulator raises an error if either differs, telling you to move the old output aside. `run_sumo_batch.py` does the same with a fingerprint that also covers `RUNNER_VERSION` and the SUMO input files. Bump `SIM_VERSION` (`src/efpb/sim.py`) or `RUNNER_VERSION` (`run_sumo_actual.py`) whenever a code change alters results.

SUMO start-up is serialised with a file lock, and each run checks that its TraCI connection reached its own SUMO instance, because parallel runs could otherwise pick the same port.

## Calibration and benchmark

```bash
python calibrate.py --config configs/experiments/calibration.yaml
python benchmark.py --config configs/experiments/benchmark.yaml
```

The benchmark writes the measured surrogate time to `data/processed/benchmark.json`. Do not extrapolate it to SUMO; run the same benchmark with the validated SUMO backend before final scheduling.

## Research runs

```bash
python run_experiment.py --config configs/experiments/confirmatory_core.yaml
python run_experiment.py --config configs/experiments/robustness.yaml
python run_experiment.py --config configs/experiments/ablations.yaml
python aggregate.py --input data/runs --output data/processed/run_metrics.csv
python analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json
```

For two machines, use the same immutable manifests and disjoint deterministic job partitions:

Computer 1:

```bash
python run_all.py --machine 1 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml
```

Computer 2:

```bash
python run_all.py --machine 2 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml
```

Run ablations separately, or assign them to Computer 2 after the core/robustness jobs finish. Merge by copying run directories without changing run IDs, then aggregate once. Never tune on confirmatory seeds.

## Paper status

The methodology document contains the protocol and expected-result decision criteria. It does not contain empirical results. A paper can only be finalized after SUMO runs, validation, calibration lock, and HCI data collection. No numbers in the current repository should be described as findings.
