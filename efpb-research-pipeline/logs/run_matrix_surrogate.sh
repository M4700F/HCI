#!/usr/bin/env bash
# Surrogate matrix in lean mode: confirmatory_core, robustness and stress on 8 shards (ablations are not runnable yet).
cd "$(dirname "$0")/.." && source .venv/bin/activate
export PYTHONPATH=src
for i in 0 1 2 3 4 5 6 7; do
  (
    for cfg in confirmatory_core robustness stress; do
      python run_experiment.py --config configs/experiments/$cfg.yaml --output-root data/matrix --machine $i --machines 8 --lean > logs/matrix_${cfg}_shard$i.log 2>&1 \
        && echo "DONE $cfg shard $i $(date +%T)" || echo "FAIL $cfg shard $i $(date +%T)"
    done
  ) &
done
wait
echo "ALL SHARDS FINISHED $(date +%T)"
