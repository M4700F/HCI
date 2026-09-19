#!/usr/bin/env bash
# 36-run SUMO pilot on 8 parallel workers (run_sumo_batch.py only supports --machines 1 or 2)
cd "$(dirname "$0")/.." && source .venv/bin/activate
export SUMO_HOME=$(python -c "import sumo; print(sumo.SUMO_HOME)") PYTHONPATH=src
cat logs/sumo_jobs.txt | xargs -P 8 -L 1 bash -c 'python run_sumo_actual.py --config configs/experiments/sumo_emergency.yaml --scenario $0 --controller $1 --seed $2 > logs/sumo_$0_$1_$2.log 2>&1 && echo "DONE $0 $1 $2" || echo "FAIL $0 $1 $2"'
echo "ALL DONE"
