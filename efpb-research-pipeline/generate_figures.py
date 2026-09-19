from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def svg_bar(path: Path, title: str, values):
    width, height = 900, 520; max_value = max(values.values() or [1.0]) or 1.0; colors = ["#24527a", "#5aa469", "#e1b12c", "#c44536"]
    bars = []
    for index, (label, value) in enumerate(sorted(values.items())):
        x = 100 + index * 180; bar_height = 300 * value / max_value; y = 390 - bar_height
        bars.append('<rect x="%s" y="%s" width="100" height="%s" fill="%s"/><text x="%s" y="420" font-size="14" text-anchor="middle">%s</text><text x="%s" y="%s" font-size="12" text-anchor="middle">%.2f</text>' % (x, y, bar_height, colors[index % len(colors)], x + 50, label, x + 50, y - 8, value))
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s"><text x="450" y="35" text-anchor="middle" font-size="22">%s</text><line x1="80" y1="390" x2="820" y2="390" stroke="black"/>%s</svg>\n' % (width, height, title, "".join(bars)))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="data/processed/run_metrics.csv"); parser.add_argument("--output", default="data/figures"); args = parser.parse_args()
    rows = list(csv.DictReader(open(args.input))); output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    for metric in ["ped_mean_wait_s", "veh_mean_wait_s", "mean_wait_disparity", "starvation_violations", "wall_time_s"]:
        grouped = defaultdict(list)
        for row in rows: grouped[row["controller"]].append(float(row[metric]))
        svg_bar(output / (metric + ".svg"), metric, {key: sum(values) / len(values) for key, values in grouped.items()})
    print("wrote figures to", output)


if __name__ == "__main__":
    main()
