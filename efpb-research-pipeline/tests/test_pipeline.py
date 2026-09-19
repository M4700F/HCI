import json
from pathlib import Path

from efpb.cli import run_config


def test_end_to_end_smoke(tmp_path):
    result = run_config("configs/experiments/smoke.yaml", output_root=str(tmp_path))
    assert result["jobs"] == 8
    assert len(list(Path(tmp_path).glob("**/run_metrics.json"))) == 8
    trace_files = list(Path(tmp_path).glob("**/decisions.jsonl"))
    assert trace_files
    assert json.loads(next(Path(tmp_path).glob("**/run_metrics.json")).read_text())["safety_violations"] == 0
