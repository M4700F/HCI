from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="data/runs"); parser.add_argument("--output", default="data/processed/run_metrics.csv"); args = parser.parse_args()
    rows = [json.loads(path.read_text()) for path in Path(args.input).glob("**/run_metrics.json")]
    if not rows:
        raise SystemExit("No run_metrics.json files found")
    rows.sort(key=lambda row: row["run_id"])
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print("wrote", output, "rows", len(rows))


if __name__ == "__main__":
    main()
