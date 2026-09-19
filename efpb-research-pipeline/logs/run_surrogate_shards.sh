#!/usr/bin/env bash
# 8 parallel shards over the 1,540-run surrogate matrix (confirmatory_core, robustness, ablations)
cd "$(dirname "$0")/.." && source .venv/bin/activate
export PYTHONPATH=src
for i in 0 1 2 3 4 5 6 7; do
  (
    for cfg in confirmatory_core robustness ablations; do
      python run_experiment.py --config configs/experiments/$cfg.yaml --machine $i --machines 8 > logs/surrogate_${cfg}_shard$i.log 2>&1 \
        && echo "DONE $cfg shard $i $(date +%T)" || echo "FAIL $cfg shard $i $(date +%T)"
    done
  ) &
done
wait
echo "ALL SHARDS FINISHED $(date +%T)"
