"""Write docs/preregistration_calibration.md from the frozen files and the calibration outputs (nothing is typed in by hand
except the design decisions and disclosures below). The document is a DRAFT until it is registered with a timestamp outside
this repository (for example on OSF); registering it is a step only the researcher can take."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

import yaml

from efpb.config import load_config


def sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_block(backend: str) -> str:
    path = Path("configs/frozen_%s.yaml" % backend)
    if not path.exists():
        return "_not frozen yet_\n"
    data = yaml.safe_load(path.read_text())
    keep = {k: v for k, v in data.items() if k in ("signal", "per_controller")}
    return "```yaml\n%s```\n\nFile: `%s`, sha256 `%s`. Selection results sha256 `%s`.\n" % (yaml.safe_dump(keep, sort_keys=False), path, sha(str(path)), data["frozen"]["selection_sha256"])


def picks_table(root: str) -> str:
    report = Path(root, "freeze_report.md")
    if not report.exists():
        return "_not run yet_\n"
    text = report.read_text()
    start, end = text.index("## Picks and decisions"), text.index("## Frozen settings")
    return text[start:end].replace("## Picks and decisions\n", "").strip() + "\n"


def main() -> None:
    sat = Path("data/saturation_study")
    lines = ["# Calibration preregistration (DRAFT)", "",
             "Generated %s by `make_preregistration.py`. **Status: draft.** It becomes a preregistration only when it is registered with a timestamp outside this repository, before the confirmatory runs. Any change after that is a deviation and must be recorded in section 8." % datetime.date.today().isoformat(), "",
             "## 1. Scope", "",
             "This document fixes the calibration decisions of the EFPB research plan: demand levels, the tuning-budget policy, the selection and confirmation rules, and the resulting frozen parameters for each backend. It does not change the research questions, hypotheses, outcome measures or statistical models of `explainable-pedestrian-vehicle-priority-research-plan.tex`, and it says nothing about the HCI study.", "",
             "## 2. Demand levels", "",
             "Two levels were added to the existing L, M, H, X (`configs/design_base.yaml`), chosen from a saturation study (`data/saturation_study/`, calibration seeds only) that ran all controllers at their then-current defaults on a ladder of multiples of X in both backends:", "",
             "| level | pedestrians / s | vehicles / s | meaning |", "|---|---|---|---|", "| S | 0.225 | 0.66 | 1.5 x X: near saturation (SUMO at about 90% of its ~0.62 veh/s capacity) |", "| O | 0.300 | 0.88 | 2.0 x X: over saturation (SUMO about 140%; surrogate fixed-time plan collapses) |", "",
             "The old top level X (0.15 / 0.44) is about half of capacity, so the earlier cells could not separate the controllers.", "",
             "## 3. Tuning-budget policy", "",
             "Each controller is evaluated on at most **30 configurations** drawn from its own declared search space; the default configuration is always included. A space of 30 or fewer configurations is searched exhaustively; a larger one by seeded random search (seed 0). No controller gets more tuning than another. Search spaces (`configs/experiments/calibration_sweep.yaml`, `sumo_calibration.yaml`):", "",
             "| controller | tuned parameters | configurations |", "|---|---|---|",
             "| fixed_time | plan family (static / demand-based) and cycle length | 14 |", "| efficiency | horizon (30, 60, 90 s), service duration (15, 25, 35 s), switch cost (0, 5, 10) | 27 |",
             "| equal_bargaining | horizon, service duration (equal weights are by definition, not tuned) | 9 |", "| efpb | horizon, service duration, delta (0, .05, .10, .20), kappa (0, 2, 4), eta (1, 2) | 30 of 180 |", "",
             "Safety timings (minimum green 10 s, yellow 3 s, all-red 1 s) are set by the standards assumed in the plan and are not tuned.", "",
             "## 4. Selection rule (per controller and backend)", "",
             "Objectives, computed over everyone who arrived after warm-up (people still waiting at the end count with the wait so far): **person delay** (occupancy-weighted mean wait, occupancy 1.3 for vehicles) and **max normalised wait** (largest wait divided by its 100 s limit). Scenarios are weighted equally; selection seeds 301-305; calibration scenarios `K_*` (surrogate: MM, LH, HL, HH, XX, SS, OO, bursty HH; SUMO: the same without the bursty cell). Each controller's configurations are scaled to 0-1 on each objective within that controller; the configuration closest to the ideal point (0, 0) is picked. An exact tie keeps the default, then the lower max wait, then the lower id. In SUMO, configurations with any collision are excluded. Picks are written to `selection.json` before any confirmation run.", "",
             "## 5. Confirmation and adoption rule", "",
             "The picked and default configurations are run on fresh seeds (surrogate 321-350, SUMO 361-370). A pick replaces the default unless it is worse than the default in **both** objectives (paired means over identical scenarios and seeds). EFPB's delta sensitivity set {0, .02, .05, .10, .20} is run around the adopted configuration on the same seeds and reported in full.", "",
             "## 6. Frozen parameters", "", "### Surrogate backend", "", picks_table("data/calibration_sweep"), frozen_block("surrogate"), "### SUMO backend", "", picks_table("data/sumo_calibration"), frozen_block("sumo"), "",
             "## 7. Experiments defined for the confirmatory phase", "",
             "| experiment | config | cells | controllers | seeds | runs |", "|---|---|---|---|---|---|"]
    for name in ("confirmatory_core", "robustness", "ablations", "stress"):
        cfg = load_config("configs/experiments/%s.yaml" % name)
        n = len(cfg["scenarios"]) * len(cfg["controllers"]) * len(cfg["seeds"])
        lines.append("| %s | `configs/experiments/%s.yaml` | %d | %d | %d (%s-%s) | %d |" % (name, name, len(cfg["scenarios"]), len(cfg["controllers"]), len(cfg["seeds"]), cfg["seeds"][0], cfg["seeds"][-1], n))
    lines += ["", "The **ablations experiment is not ready**: its five cells are identical in behavior because the ablated controllers (no starvation guard, no efficiency filter, static weights, weighted sum) are not implemented.", "",
              "## 8. Disclosures and deviations", "",
              "- The surrogate was corrected before calibration: service capacity now uses the configured fractional rates (vehicles 0.8/s per approach, previously rounded up to 1/s); the demand generator can produce more than one arrival per second; waits include people still queued at the end of a run (surrogate 0.4.0, SUMO runner 0.5.0).",
              "- A first surrogate selection was made on data produced with a bug (fixed-time splits were mis-scaled, so one vehicle phase was never served) and with waits that ignored unserved people. I saw its confirmation results before discarding it. All selections and confirmations in this document were redone with the corrected code from scratch.",
              "- After that first attempt an exact tie in the selection rule changed a parameter for no measurable reason; the rule was refined so that ties keep the default. I saw that tie before changing the rule.",
              "- Both backends have their own frozen file. The surrogate is engineering validation only; SUMO uses virtual pedestrians.",
              "- Later deviations must be listed here with date and reason.", ""]
    Path("docs/preregistration_calibration.md").write_text("\n".join(lines) + "\n")
    print("wrote docs/preregistration_calibration.md")


if __name__ == "__main__":
    main()
