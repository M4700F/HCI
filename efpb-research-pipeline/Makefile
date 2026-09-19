PYTHON ?= python

install:
	$(PYTHON) -m pip install -e '.[dev,analysis]'

test:
	$(PYTHON) -m pytest -q

smoke:
	$(PYTHON) run_experiment.py --config configs/experiments/smoke.yaml

calibrate:
	$(PYTHON) calibrate.py --config configs/experiments/calibration.yaml

calibrate-sweep:
	$(PYTHON) sweep_calibration.py --config configs/experiments/calibration_sweep.yaml

benchmark:
	$(PYTHON) benchmark.py --config configs/experiments/benchmark.yaml

aggregate:
	$(PYTHON) aggregate.py --input data/runs --output data/processed/run_metrics.csv

analyze:
	$(PYTHON) analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json

figures:
	$(PYTHON) generate_figures.py --input data/processed/run_metrics.csv --output data/figures

stimuli:
	$(PYTHON) build_stimuli.py --input data/runs --output data/stimuli
