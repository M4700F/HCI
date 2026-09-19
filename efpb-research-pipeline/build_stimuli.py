from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="data/runs"); parser.add_argument("--output", default="data/stimuli"); args = parser.parse_args()
    traces = []
    for path in Path(args.input).glob("**/decisions.jsonl"):
        for line in path.read_text().splitlines()[:3]:
            trace = json.loads(line); traces.append({"decision_id": trace["decision_id"], "trace": trace, "conditions": ["D", "F", "FC"]})
    if not traces:
        raise SystemExit("No validated decision traces found")
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True); (output / "manifest.json").write_text(json.dumps({"version": "0.1.0", "stimuli": traces}, indent=2, sort_keys=True) + "\n"); print("wrote", len(traces), "stimulus traces")


if __name__ == "__main__":
    main()
