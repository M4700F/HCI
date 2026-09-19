from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate real SUMO/TraCI run metrics.")
    parser.add_argument("--input", default="data/sumo_runs")
    parser.add_argument("--output", default="data/processed/sumo_metrics.csv")
    args = parser.parse_args()
    rows = []
    for path in sorted(Path(args.input).glob("*/metrics.json")):
        rows.append(json.loads(path.read_text()))
    if not rows:
        raise SystemExit("No SUMO metrics found under %s" % args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("wrote", output, "rows", len(rows))


if __name__ == "__main__":
    main()
