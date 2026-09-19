# Reproduction and two-computer run plan

## 1. Smoke test

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,analysis]'
python -m pytest -q
python run_experiment.py --config configs/experiments/smoke.yaml
```

Expected engineering result: 4 tests pass and 8 valid surrogate run directories are created. This does not validate SUMO geometry.

## 2. Calibration and measured benchmark

```bash
python calibrate.py --config configs/experiments/calibration.yaml
python benchmark.py --config configs/experiments/benchmark.yaml
python estimate_runtime.py
```

Freeze only parameters selected from calibration outputs. The current local measurement was 3.144 seconds per 660-second surrogate run, or 0.00476 seconds per simulated second. This is not a SUMO measurement.

## 3. Confirmatory traffic experiments

After installing and validating SUMO, change the backend and run the same benchmark on each computer. Do not report confirmatory results until the SUMO validation report is valid.

```bash
python run_experiment.py --config configs/experiments/confirmatory_core.yaml
python run_experiment.py --config configs/experiments/robustness.yaml
python run_experiment.py --config configs/experiments/ablations.yaml
python aggregate.py --input data/runs --output data/processed/run_metrics.csv
python analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json
python generate_figures.py --input data/processed/run_metrics.csv --output data/figures
```

## 4. Machine split

The deterministic partition is by the ordered Cartesian product `(scenario, controller, seed)` and `index % 2`. This guarantees disjoint run IDs when both machines use the same configs.

Computer 1:

```bash
python run_all.py --machine 1 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml
```

Computer 2:

```bash
python run_all.py --machine 2 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml
```

For ablations, use the same split after core/robustness jobs:

```bash
python run_all.py --machine 1 --machines 2 --config configs/experiments/ablations.yaml
python run_all.py --machine 2 --machines 2 --config configs/experiments/ablations.yaml
```

Copy only completed run directories and manifests between machines. Since run IDs are immutable, aggregation is safe after merging. If a run fails, preserve its failure record and diagnose it; do not silently replace it with a favorable rerun.

## 5. Runtime calculation

The provisional matrix is 1,540 traffic runs:

- confirmatory core: 9 demand cells × 4 controllers × 30 seeds = 1,080;
- robustness: 9 targeted scenarios × 4 controllers × 10 seeds = 360;
- ablations: 5 cells × 2 controllers × 10 seeds = 100.

The initial protocol uses 600 s warm-up + 3,600 s evaluation = 4,200 simulated seconds per run. The benchmark uses 60 + 600 = 660 simulated seconds. `estimate_runtime.py` scales the measured benchmark and prints total CPU hours, ideal two-machine wall time, and 1.5×/2× overhead bounds.

Using the current surrogate measurement only, the extrapolation is about 20.0 seconds per 4,200-second run, 8.6 CPU hours for 1,540 runs, and 4.3 ideal wall-clock hours on two equal machines. A realistic 1.5×–2× engineering bound is approximately 6.5–8.6 wall-clock hours. Replace this estimate with the measured SUMO benchmark before publication; SUMO speed, GUI/headless mode, CPU, filesystem, and trace/counterfactual settings can change it materially.

The HCI study is not a traffic-run multiplier. It uses frozen traces and has separate participant/recruitment time, which cannot be estimated from SUMO runtime.
