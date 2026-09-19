# EFPB research pipeline: friend-run instructions

Version: 0.1.0 scaffold

This package contains the reproducible code scaffold for the Explainable Fair Priority Bargaining project. It includes configuration, controllers, manifests, DecisionTrace logging, counterfactual search, tests, aggregation, figures, stimulus export, and SUMO setup files.

Important research-integrity status: the general pipeline still contains a dependency-free surrogate backend, but this release also includes a real SUMO/TraCI emergency runner. The emergency runner uses SUMO for vehicle movement and signal execution, while pedestrians remain a virtual queue because the bundled legacy network has no validated pedestrian walking areas. Read `SUMO_EMERGENCY_SCOPE.md`; do not describe that limited run as a complete multimodal validation.

## 1. Install

```bash
cd efpb-research-pipeline
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,analysis]'
```

Verify:

```bash
python -m pytest -q
```

Expected result: 5 tests pass.

## 2. SUMO installation and network check

Install SUMO using the operating system’s supported package or the official SUMO distribution. Then set `SUMO_HOME` and put its `bin` directory on `PATH`.

Linux example:

```bash
export SUMO_HOME=/opt/sumo
export PATH="$SUMO_HOME/bin:$PATH"
```

macOS/Homebrew-style example:

```bash
export SUMO_HOME=/path/to/sumo
export PATH="$SUMO_HOME/bin:$PATH"
```

Build and validate the supplied four-arm network:

```bash
bash sumo/build_network.sh
PYTHONPATH=src python validate_sumo.py
```

If this fails, do not run confirmatory experiments. Check `SUMO_HOME`, `PATH`, file permissions, and the SUMO version. Open the network in `sumo-gui` and manually inspect every phase and crossing transition.

## 2A. Emergency real-SUMO run for the one-day deadline

Run this on a computer where `sumo` and TraCI are working. It uses real SUMO/TraCI vehicle simulation and writes results under `data/sumo_runs/`:

```bash
PYTHONPATH=src python run_sumo_actual.py --config configs/experiments/sumo_emergency.yaml --scenario S1_balanced --controller efpb --seed 9001
PYTHONPATH=src python run_sumo_batch.py --config configs/experiments/sumo_emergency.yaml --machine 1 --machines 2
```

On the second computer, use `--machine 2`. This emergency matrix is 3 scenarios × 4 controllers × 3 paired seeds = 36 SUMO runs. It is a time-boxed pilot and is not the full 1,540-run confirmatory matrix.

After both computers finish, copy both `data/sumo_runs/` directories into one package directory and run:

```bash
python aggregate_sumo.py --input data/sumo_runs --output data/processed/sumo_metrics.csv
python analyze_sumo.py --input data/processed/sumo_metrics.csv --output data/processed/sumo_analysis.json
```

## 3. Smoke pipeline

```bash
python run_experiment.py --config configs/experiments/smoke.yaml
python aggregate.py --input data/runs --output data/processed/run_metrics.csv
python analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json
python generate_figures.py --input data/processed/run_metrics.csv --output data/figures
python build_stimuli.py --input data/runs --output data/stimuli
```

This creates 8 surrogate runs: 2 scenarios × 4 controllers × 1 paired seed.

## 4. Calibration and benchmark

```bash
python calibrate.py --config configs/experiments/calibration.yaml
python benchmark.py --config configs/experiments/benchmark.yaml
python estimate_runtime.py
```

Inspect calibration outputs before freezing any parameter. Do not tune confirmatory seeds.

## 5. Research matrix

The provisional matrix is defined in `configs/experiment_matrix.yaml`:

- Confirmatory core: 9 demand cells × 4 controllers × 30 paired seeds = 1,080 runs.
- Robustness: 9 targeted scenarios × 4 controllers × 10 seeds = 360 runs.
- Ablations: 5 cells × 2 controllers × 10 seeds = 100 runs.
- Total traffic runs: 1,540.

Run commands:

```bash
python run_experiment.py --config configs/experiments/confirmatory_core.yaml
python run_experiment.py --config configs/experiments/robustness.yaml
python run_experiment.py --config configs/experiments/ablations.yaml
```

## 6. Two-computer split

Both computers must use identical code, configuration, SUMO version, and seed lists.

Computer 1:

```bash
python run_all.py --machine 1 --machines 2 \
  --config configs/experiments/confirmatory_core.yaml \
  --config configs/experiments/robustness.yaml
```

Computer 2:

```bash
python run_all.py --machine 2 --machines 2 \
  --config configs/experiments/confirmatory_core.yaml \
  --config configs/experiments/robustness.yaml
```

Then split ablations using the same `--machine` values. Copy only completed `data/runs/` subdirectories to one machine. Run aggregation after merging:

```bash
python aggregate.py
python analyze.py
python generate_figures.py
python build_stimuli.py
```

The runner uses deterministic job partitioning and unique run IDs. Do not delete failed runs or rerun them selectively without recording the reason.

## 7. Output locations

Each run is stored under:

```text
data/runs/{scenario}/{controller}/{seed}/{run_id}/
```

Important files are `manifest.json`, `resolved_config.json`, `states.csv`, `decisions.jsonl`, `explanations.jsonl`, `events.jsonl`, `run_metrics.json`, and `run_summary.json`.

Aggregated metrics go to `data/processed/run_metrics.csv`; descriptive analysis goes to `data/processed/analysis.json`; figures go to `data/figures/`; replay stimuli go to `data/stimuli/`.

## 8. Runtime estimate

The development Mac measured 3.144 seconds for one 660-second surrogate run. Extrapolated to 4,200 simulated seconds per research run, the provisional 1,540-run matrix is approximately 8.56 CPU hours, or 4.28 ideal hours on two equal computers. Allow approximately 6.4–8.6 wall-clock hours for overhead.

This is not a SUMO benchmark. Measure one representative headless SUMO run on each computer and rerun `estimate_runtime.py` using that benchmark before scheduling the final matrix.

## 9. What may be reported

Report surrogate output only as engineering validation. Report SUMO traffic findings only after the SUMO/TraCI run is validated. Do not claim statistical significance, calibrated parameter values, HCI effects, or paper findings until the corresponding experiments and approved participant study are complete.
