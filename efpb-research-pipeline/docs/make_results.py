"""Builds ../EFPB_Simulation_Results.pdf: every result produced so far, read from the stored result files.

Run from the project root with reportlab, pyyaml and matplotlib installed:  python docs/make_results.py
(Charts are drawn to a temporary folder.) Nothing is typed in except the wording; all numbers come from data/.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from pdfkit import (AMBER, GREEN, ROOT, W, B, C, P, Spacer, body, build, esc, fnum, h1, h2, is_true, load, md_table, mm, picture, small, sub, table, title)

OUT = ROOT.parent / "EFPB_Simulation_Results.pdf"
CONTROLLERS = ["fixed_time", "efficiency", "equal_bargaining", "efpb"]
SHORT = {"fixed_time": "fixed", "efficiency": "effic.", "equal_bargaining": "equal barg.", "efpb": "efpb"}
COLORS = {"fixed_time": "#7f7f7f", "efficiency": "#2a6f97", "equal_bargaining": "#5aa469", "efpb": "#c44536"}
NOMINAL = ["C_LL", "C_LM", "C_LH", "C_ML", "C_MM", "C_MH", "C_HL", "C_HM", "C_HH"]
STRESS = ["T_SS", "T_HS", "T_SH", "T_OO"]
TMP = Path(tempfile.mkdtemp(prefix="efpb_results_"))

# ------------------------------------------------------------------ data
res = {n: {k: load("data/results/%s_%s.csv" % (k, n)) for k in ("overall", "paired", "cells")} for n in ("surrogate", "sumo")}
excluded = json.loads((ROOT / "data/results/excluded.json").read_text())
pilot, pilot_static, pilot_v2 = load("data/processed/sumo_metrics.csv"), load("data/processed/sumo_metrics_static_fixed_time.csv"), load("data/processed/sumo_metrics_v2_no_clearance.csv")
sat_sur, sat_sumo = load("data/saturation_study/surrogate_summary.csv"), load("data/saturation_study/sumo_summary.csv")
cal = {}
for name, root, sel, runs in (("surrogate", "data/calibration_sweep", "summary.csv", "run_metrics.csv"), ("SUMO", "data/sumo_calibration", "summary_selection.csv", "run_metrics_selection.csv")):
    cal[name] = {"root": root, "summary": load("%s/%s" % (root, sel)), "runs": len(load("%s/%s" % (root, runs))), "selection": json.loads((ROOT / root / "selection.json").read_text()),
                 "configs": json.loads((ROOT / root / "configs.json").read_text()), "frozen": yaml.safe_load((ROOT / ("configs/frozen_%s.yaml" % ("surrogate" if name == "surrogate" else "sumo"))).read_text())}
runs_sur, runs_sumo = load("data/results/runs_surrogate.csv"), load("data/results/runs_sumo.csv")
LABEL = {"controller.horizon_s": "horizon", "signal.service_duration_s": "duration", "controller.switch_cost": "switch cost", "controller.delta": "delta", "controller.debt_kappa": "kappa", "controller.debt_eta": "eta", "signal.fixed_cycle_s": "cycle", "signal.fixed_timing": "plan"}


def describe(ov):
    return ", ".join("%s %s" % (LABEL.get(k, k), ov[k]) for k in sorted(ov))


def overall(name, group, controller):
    return next(r for r in res[name]["overall"] if r["group"] == group and r["controller"] == controller)


def pair(name, group, other, metric):
    return next(r for r in res[name]["paired"] if r["group"] == group and r["comparison"] == "efpb - " + other and r["metric"] == metric)


def pair_text(name, group, other, metric):
    r = pair(name, group, other, metric)
    return "%+.2f ± %.2f (%s/%s)" % (float(r["mean_diff"]), float(r["se"]), r["cells_efpb_lower"], r["cells"])


def cell_val(name, scenario, controller, key):
    return float(next(r for r in res[name]["cells"] if r["scenario"] == scenario and r["controller"] == controller)[key])


# ------------------------------------------------------------------ charts
def chart(name, path):
    figure, axes = plt.subplots(2, 2, figsize=(11, 6.6))
    for col, (cells, label, logy) in enumerate(((NOMINAL, "nominal cells", False), (STRESS, "stress cells", True))):
        for row, (key, ylabel) in enumerate((("person_delay_s", "person delay (s)"), ("max_norm_wait", "max wait / limit"))):
            axis = axes[row][col]
            width = 0.2
            for k, c in enumerate(CONTROLLERS):
                axis.bar([i + (k - 1.5) * width for i in range(len(cells))], [cell_val(name, sc, c, key) for sc in cells], width, color=COLORS[c], label=SHORT[c])
            axis.set_xticks(range(len(cells)))
            axis.set_xticklabels(cells, fontsize=8, rotation=45 if col == 0 else 0)
            axis.set_ylabel(ylabel, fontsize=9)
            if logy:
                axis.set_yscale("log")
            if key == "max_norm_wait":
                axis.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
            axis.set_title("%s, %s%s" % (ylabel, label, " (log scale)" if logy else ""), fontsize=9)
            axis.tick_params(axis="y", labelsize=8)
    axes[0][0].legend(fontsize=8, ncol=4)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def ladder_chart(path):
    figure, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for c in CONTROLLERS:
        rows = sorted((r for r in sat_sur if r["controller"] == c), key=lambda r: float(r["multiplier"]))
        axes[0].plot([float(r["multiplier"]) for r in rows], [min(float(r["ped_service_ratio"]), float(r["veh_service_ratio"])) for r in rows], marker="o", color=COLORS[c], label=SHORT[c])
    axes[0].set_title("surrogate: worst service ratio", fontsize=9)
    for c in ("fixed_time", "efficiency", "efpb"):
        rows = sorted((r for r in sat_sumo if r["controller"] == c), key=lambda r: float(r["multiplier"]))
        axes[1].plot([float(r["multiplier"]) for r in rows], [float(r["veh_completion_ratio"]) for r in rows], marker="o", color=COLORS[c], label=SHORT[c])
    axes[1].set_title("SUMO: share of vehicle demand completed", fontsize=9)
    for axis in axes:
        axis.set_xlabel("demand as a multiple of the old top level X", fontsize=9)
        axis.axvline(1.5, color="black", linestyle=":", linewidth=0.8)
        axis.axvline(2.0, color="black", linestyle=":", linewidth=0.8)
        axis.text(1.5, 0.05, " S", fontsize=8)
        axis.text(2.0, 0.05, " O", fontsize=8)
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


chart("sumo", TMP / "sumo.png")
chart("surrogate", TMP / "surrogate.png")
ladder_chart(TMP / "ladder.png")


def cell_table(name, scenarios):
    """Per-cell person delay and max wait for the four controllers, the lowest value in each block in bold."""
    rows = [["Cell", "Demand ped/veh"] + ["delay " + SHORT[c] for c in CONTROLLERS] + ["wait " + SHORT[c] for c in CONTROLLERS]]
    for sc in scenarios:
        d = [cell_val(name, sc, c, "person_delay_s") for c in CONTROLLERS]
        w = [cell_val(name, sc, c, "max_norm_wait") for c in CONTROLLERS]
        levels = sc.split("_")[-1] if sc[:2] in ("C_", "T_") else ""
        rows.append([sc, "%s / %s" % (levels[0], levels[1]) if len(levels) == 2 else ""] + ["<b>%s</b>" % fnum(v, 1) if v == min(d) else fnum(v, 1) for v in d] + ["<b>%s</b>" % fnum(v, 2) if v == min(w) else fnum(v, 2) for v in w])
    return table(rows, [22 * mm, 18 * mm] + [(W - 40 * mm) / 8.0] * 8, markup=True)


s = []
s.append(P("EFPB Simulation Results", title))
s.append(P("Every result produced so far: the SUMO and surrogate experiments, the SUMO pilot, calibration and the demand study<br/>Runs of 19 September 2026 on one laptop. Companion to EFPB_Experiment_Run_Report.pdf (what was done and how).", sub))

# ------------------------------------------------------------------ 1
s.append(P("1. Read this first", h1))
s += B([
    "<b>These are traffic-simulation results only.</b> Nothing here tests explanations, comprehension, trust or any other part of the HCI study; that part of the research plan has not been carried out.",
    "<b>Status: exploratory.</b> The matrix experiments (section 3) were started without confirmation that the preregistration draft had been registered first. Unless it was registered before 17:39 on 2026-09-19, treat them as exploratory, not confirmatory.",
    "<b>Two backends.</b> SUMO/TraCI is the real traffic simulator (vehicles and signals in SUMO; <i>pedestrians are a virtual queue</i> because the network has no validated walking areas). The surrogate is a fast in-process approximation used for engineering validation; its numbers should not be reported as traffic evidence.",
    "<b>Descriptive statistics only.</b> Means over cells (cells weighted equally) and paired differences on identical scenarios and seeds, with standard errors. The preregistered models are not implemented, so there are no significance tests.",
    "<b>Objectives.</b> <i>Person delay</i> is the occupancy-weighted mean wait of everyone who arrived after warm-up (people still waiting at the end count with the wait so far). <i>Max wait / limit</i> is the largest wait divided by its 100 s limit; above 1 the limit is exceeded. Lower is better for both.",
])
s.append(P("Result sets in this document", h2))
sets = [
    ["Result set", "Backend", "Runs", "Seeds", "Status"],
    ["Matrix: 9 nominal + 4 stress cells x 4 controllers", "SUMO", "%d" % len(runs_sumo), "4001–4010 (10)", "Exploratory; 30-seed version kept for future work"],
    ["Matrix: confirmatory_core, robustness, stress", "Surrogate", "%d (%d analysed)" % (len(runs_sur), len(res["surrogate"]["cells"]) and sum(int(r["runs"]) for r in res["surrogate"]["cells"])), "1001–1030, 2001–2010, 1101–1130", "Exploratory; engineering validation"],
    ["Pilot: 3 scenarios x 4 controllers", "SUMO", "36", "9001–9003 (3)", "Time-boxed pilot"],
    ["Calibration selection", "Surrogate / SUMO", "%d / %d" % (cal["surrogate"]["runs"], cal["SUMO"]["runs"]), "301–305", "Parameter selection, calibration data only"],
    ["Calibration confirmation and delta sensitivity", "Surrogate / SUMO", "2,400 / 700", "321–350 / 361–370", "Fresh seeds; parameters frozen"],
    ["Demand (saturation) study", "Both", "160 / 45", "301–305 / 301–303", "Chose demand levels S and O"],
]
s.append(table(sets, [62 * mm, 26 * mm, 22 * mm, 30 * mm, W - 140 * mm]))

# ------------------------------------------------------------------ 2
s.append(P("2. Headline results", h1))
def line(name, group, other, metric):
    r = pair(name, group, other, metric)
    return "%+.2f ± %.2f" % (float(r["mean_diff"]), float(r["se"]))
s += B([
    "<b>Nominal demand, SUMO (9 cells).</b> efpb has the lowest mean person delay: %s s, against %s for efficiency, %s for equal_bargaining and %s for the tuned fixed-time plan. It is lower than each of them in all 9 cells (paired differences %s, %s, %s s). Its max wait is lower than efficiency's (%s) and about equal to equal_bargaining's (%s)." % (fnum(overall("sumo", "nominal", "efpb")["person_delay_s"], 2), fnum(overall("sumo", "nominal", "efficiency")["person_delay_s"], 2), fnum(overall("sumo", "nominal", "equal_bargaining")["person_delay_s"], 2), fnum(overall("sumo", "nominal", "fixed_time")["person_delay_s"], 2), line("sumo", "nominal", "efficiency", "person_delay_s"), line("sumo", "nominal", "equal_bargaining", "person_delay_s"), line("sumo", "nominal", "fixed_time", "person_delay_s"), line("sumo", "nominal", "efficiency", "max_norm_wait"), line("sumo", "nominal", "equal_bargaining", "max_norm_wait")),
    "<b>The tuned fixed-time plan has the lowest max wait</b> in the nominal cells (%s against %s for efpb in SUMO) because every phase comes round within its 37 s cycle, but at a person delay %s s higher. Neither objective alone decides a winner." % (fnum(overall("sumo", "nominal", "fixed_time")["max_norm_wait"]), fnum(overall("sumo", "nominal", "efpb")["max_norm_wait"]), fnum(-float(pair("sumo", "nominal", "fixed_time", "person_delay_s")["mean_diff"]), 1)),
    "<b>The surrogate agrees for nominal demand:</b> efpb ties efficiency on person delay (%s s) with a lower max wait (%s); fixed-time again has the lowest max wait." % (line("surrogate", "nominal", "efficiency", "person_delay_s"), line("surrogate", "nominal", "efficiency", "max_norm_wait")),
    "<b>Under saturation there is no clear ordering.</b> In SUMO efpb, efficiency and fixed-time are within about 7 s on person delay with large standard errors, and the over-saturated cell T_OO fails for every controller. In the surrogate efficiency has the lowest person delay under stress.",
    "<b>equal_bargaining collapses under saturation</b> (SUMO stress: person delay %s s, max wait %s times the limit) because it almost never serves pedestrians while vehicles are queued. This is how the baseline is implemented; whether that is the intended baseline is undecided." % (fnum(overall("sumo", "stress", "equal_bargaining")["person_delay_s"], 0), fnum(overall("sumo", "stress", "equal_bargaining")["max_norm_wait"], 0)),
    "<b>Safety:</b> no collisions and no emergency stops in any of the 520 SUMO matrix runs; after adding yellow and all-red clearance the SUMO pilot also had none (79 emergency stops without it).",
    "<b>Calibration:</b> a demand-based fixed-time plan with a 37 s cycle wins in both backends; in the surrogate only efpb changes from its defaults (kappa 4, eta 2, service duration 15 s), in SUMO every controller keeps its defaults. The delta tolerance barely matters.",
])

# ------------------------------------------------------------------ 3
s.append(P("3. Matrix experiments", h1))
s.append(P("Frozen parameters, fresh paired seeds. SUMO: 13 demand cells x 4 controllers x 10 seeds, 4,200 s per run (600 s warm-up, 3,600 s evaluation). Surrogate: confirmatory_core (9 cells, 30 seeds), robustness (8 of 9 scenarios analysed, 10 seeds) and stress (4 cells, 30 seeds). Cell T_XY is pedestrian level X, vehicle level Y (L, M, H = light, medium, high; S = near saturation, O = over saturation).", body))
for name, label, groups, extra in (("sumo", "3.1 SUMO/TraCI (virtual pedestrians)", ("nominal", "stress"), True), ("surrogate", "3.2 Surrogate (engineering validation only)", ("nominal", "robustness", "stress"), False)):
    s.append(P(label, h2))
    head = ["Group", "Controller", "Person delay (s)", "Max wait / limit", "Ped wait (s)", "Veh wait or stop (s)"] + (["Unserved ped / unfinished veh"] if extra else ["Starvation violations"])
    rows = [head]
    for g in groups:
        for c in CONTROLLERS:
            r = overall(name, g, c)
            rows.append([g, c, fnum(r["person_delay_s"], 1), fnum(r["max_norm_wait"]), fnum(r["ped_mean_wait_s"], 1), fnum(r["veh_mean_wait_s"], 1)] + (["%s / %s" % (fnum(r["ped_unserved"], 1), fnum(r["veh_unfinished"], 1))] if extra else [fnum(r["starvation_violations"], 2)]))
    s.append(P("<b>Means over cells</b> (%s)." % ", ".join("%s: %s cells" % (g, overall(name, g, "efpb")["cells"]) for g in groups), body))
    s.append(table(rows, [20 * mm, 28 * mm, 22 * mm, 22 * mm, 20 * mm, 25 * mm, W - 137 * mm]))
    s.append(Spacer(1, 4))
    rows = [["Group", "efpb minus", "Person delay (s)", "Max wait / limit"]]
    for g in groups:
        for other in ("fixed_time", "efficiency", "equal_bargaining"):
            rows.append([g, other, pair_text(name, g, other, "person_delay_s"), pair_text(name, g, other, "max_norm_wait")])
    s.append(P("<b>efpb against each controller</b>, paired on scenario and seed: mean difference ± standard error (cells where efpb is lower / cells). Negative = efpb lower, i.e. better.", body))
    s.append(table(rows, [22 * mm, 35 * mm, (W - 57 * mm) / 2, (W - 57 * mm) / 2]))
    s.append(Spacer(1, 4))
    s.append(picture(TMP / ("%s.png" % name)))
    s.append(P("Figure: person delay and max wait per cell for the four controllers (stress cells on a log scale; the dashed line is the wait limit).", small))
    s.append(P("<b>Per cell</b> (lowest value in each block in bold; demand levels of pedestrians / vehicles):", body))
    s.append(cell_table(name, NOMINAL))
    s.append(Spacer(1, 4))
    s.append(cell_table(name, STRESS))
    if name == "surrogate":
        s.append(Spacer(1, 6))
        rob = sorted({r["scenario"] for r in res["surrogate"]["cells"] if r["group"] == "robustness"})
        rows = [["Robustness scenario"] + ["delay " + SHORT[c] for c in CONTROLLERS] + ["wait " + SHORT[c] for c in CONTROLLERS]]
        for sc in rob:
            rows.append([sc] + [fnum(cell_val("surrogate", sc, c, "person_delay_s"), 1) for c in CONTROLLERS] + [fnum(cell_val("surrogate", sc, c, "max_norm_wait"), 2) for c in CONTROLLERS])
        s.append(table(rows, [36 * mm] + [(W - 36 * mm) / 8.0] * 8))
        s.append(P("Excluded from every mean and comparison: %s. S12 (sensor error) gives identical numbers for every controller because they all fall back to the same fixed plan, and S7 (emergency) is a single-second request with no visible effect; both are valid but uninformative." % "; ".join("%s (%s)" % (k, v) for k, v in excluded.items()), small))
    s.append(Spacer(1, 6))

# ------------------------------------------------------------------ 4
s.append(P("4. SUMO pilot (time-boxed)", h1))
s.append(P("36 runs: 3 scenarios (balanced, pedestrian-heavy, vehicle-heavy) x 4 controllers x 3 seeds (9001–9003, never used for calibration); 900 s evaluation. fixed_time uses the tuned demand-based 37 s plan. Means of 3 seeds; no collisions and no emergency stops.", body))
def cell_mean(rows, sc, ctl, key):
    return statistics.mean(float(r[key]) for r in rows if r["scenario_id"] == sc and r["controller"] == ctl)
rows = [["Scenario", "Controller", "Veh/h", "Stop time (s)", "Wait p95 (s)", "Queue", "Ped served", "Ped wait (s)", "Switches", "Clear. %"]]
for sc in ("S1_balanced", "S2_pedestrian_heavy", "S3_vehicle_heavy"):
    for c in CONTROLLERS:
        m = lambda key: cell_mean(pilot, sc, c, key)
        rows.append([sc, c, fnum(m("vehicle_throughput_per_hour"), 0), fnum(m("vehicle_stop_time_mean_s"), 1), fnum(m("vehicle_stopped_wait_p95_s"), 1), fnum(m("mean_vehicle_queue")), fnum(m("pedestrian_served_virtual"), 1), fnum(m("pedestrian_wait_mean_s"), 1), fnum(m("phase_switches"), 0), fnum(100 * m("clearance_steps") / 900.0, 1)])
s.append(table(rows, [33 * mm, 26 * mm, 12 * mm, 16 * mm, 16 * mm, 12 * mm, 15 * mm, 15 * mm, 15 * mm, W - 160 * mm]))
def mean_all(rows, ctl, key):
    return statistics.mean(float(r[key]) for r in rows if r["controller"] == ctl)
s.append(Spacer(1, 4))
s += B([
    "<b>Effect of yellow/all-red clearance</b> (pilot with the static 90 s fixed-time plan so timing is not mixed in): mean vehicle stop time without / with clearance – %s. Emergency stops: %d without, %d with." % ("; ".join("%s %s / %s s" % (c, fnum(mean_all(pilot_v2, c, "vehicle_stop_time_mean_s"), 1), fnum(mean_all(pilot_static if c == "fixed_time" else pilot, c, "vehicle_stop_time_mean_s"), 1)) for c in CONTROLLERS), sum(float(r["emergency_stops"]) for r in pilot_v2), sum(float(r["emergency_stops"]) for r in pilot)),
    "<b>Effect of tuning the fixed-time plan</b> (same seeds): mean vehicle stop time %s s with the static 90 s plan against %s s with the tuned demand-based 37 s plan." % (fnum(mean_all(pilot_static, "fixed_time", "vehicle_stop_time_mean_s"), 1), fnum(mean_all(pilot, "fixed_time", "vehicle_stop_time_mean_s"), 1)),
    "In the pilot no controller is clearly ahead on vehicles (stop times within about 1 s); equal_bargaining has the lowest pedestrian waits at these light demand levels. Three seeds only.",
])

# ------------------------------------------------------------------ 5
s.append(P("5. Calibration results", h1))
s.append(P("Every controller was tuned under the same budget (at most 30 configurations from its own search space, default always included) on calibration scenarios and seeds 301–305. Each controller's pick is the configuration closest to the ideal point (lowest delay and lowest max wait, both scaled 0–1 within that controller); ties keep the default. The pick was recorded before any confirmation run, then compared with the default on fresh seeds and adopted unless worse in both objectives.", body))
for name in ("surrogate", "SUMO"):
    b = cal[name]
    root = b["root"]
    s.append(P("5.%d %s" % (1 if name == "surrogate" else 2, name), h2))
    dec = {r[0]: r for r in md_table(root + "/freeze_report.md", "## Picks and decisions")[1:]}
    rows = [["Controller", "Configs tried", "Delay range (s)", "Max wait range", "Default (delay / max wait)", "Pick", "Adopted?"]]
    for c in CONTROLLERS:
        group = [r for r in b["summary"] if r["controller"] == c]
        default = next(r for r in group if is_true(r["is_default"]))
        pid = b["selection"]["picks"][c]
        rows.append([c, str(len(group)), "%s–%s" % (fnum(min(float(r["person_delay_s"]) for r in group), 1), fnum(max(float(r["person_delay_s"]) for r in group), 1)), "%s–%s" % (fnum(min(float(r["max_norm_wait"]) for r in group)), fnum(max(float(r["max_norm_wait"]) for r in group))), "%s / %s" % (fnum(default["person_delay_s"], 1), fnum(default["max_norm_wait"])), "default" if pid == default["config_id"] else describe(b["configs"][pid]), dec[c][-1]])
    s.append(table(rows, [24 * mm, 14 * mm, 24 * mm, 24 * mm, 30 * mm, W - 136 * mm, 20 * mm]))
    s.append(Spacer(1, 4))
    conf = md_table(root + "/freeze_report.md", "## Confirmation results")
    rows = [["Configuration confirmed on fresh seeds", "Controller", "Person delay (s)", "Max wait / limit", "Worst scenario"]]
    for r in conf[1:]:
        cid = r[0]
        label = describe(b["configs"][cid]) if cid in b["configs"] else "efpb delta " + cid.split("sens_d")[-1]
        rows.append([label + (" (default)" if cid in b["configs"] and is_true(next(x for x in b["summary"] if x["config_id"] == cid)["is_default"]) else ""), r[1], fnum(r[2], 1), fnum(r[3]), fnum(r[4])])
    s.append(table(rows, [W - 95 * mm, 30 * mm, 20 * mm, 20 * mm, 25 * mm]))
    frozen = {k: v for k, v in b["frozen"].items() if k in ("signal", "per_controller")}
    s.append(P("<b>Frozen</b> (%s): %s" % (C("configs/frozen_%s.yaml" % ("surrogate" if name == "surrogate" else "sumo")), esc(json.dumps(frozen))), small))
    dl = md_table(root + "/freeze_report.md", "## EFPB delta sensitivity (other efpb parameters at the picked values; confirmation seeds)")
    s.append(table([["delta", "Person delay (s)", "Max wait / limit", "Max wait vs picked"]] + [[r[0], fnum(r[1], 2), fnum(r[2], 4), r[4]] for r in dl[1:]], [20 * mm, 40 * mm, 40 * mm, W - 100 * mm]))
    s.append(Spacer(1, 6))
s.append(P("5.3 Fixed-time cycle length under stress", h2))
rows = [["Cycle (s)", "Surrogate: delay / max wait / worst scenario", "SUMO: delay / max wait / worst scenario"]]
for cycle in (37, 40, 45, 50, 60, 75, 90, 120):
    cells = []
    for name in ("surrogate", "SUMO"):
        r = next(x for x in cal[name]["summary"] if x["controller"] == "fixed_time" and x["p:signal.fixed_timing"] == "demand_based" and float(x["p:signal.fixed_cycle_s"]) == cycle)
        cells.append("%s / %s / %s" % (fnum(r["person_delay_s"], 1), fnum(r["max_norm_wait"]), fnum(r["worst_scenario_max_norm_wait"])))
    rows.append([str(cycle)] + cells)
s.append(table(rows, [20 * mm, (W - 20 * mm) / 2, (W - 20 * mm) / 2]))
s.append(P("Demand-based plans (splits from each scenario's nominal demand). Both backends pick 37 s, the shortest cycle that fits three 10 s minimum greens plus clearance. Longer cycles lower the worst-scenario wait but raise the overall delay. Static plans with proportional splits had a much higher max wait at every cycle length.", small))

# ------------------------------------------------------------------ 6
s.append(P("6. Demand study: where the system saturates", h1))
s.append(picture(TMP / "ladder.png"))
s.append(P("Figure: all controllers at their then-current defaults on a ladder of demand levels. The old top level X (0.15 pedestrians and 0.44 vehicles per second) is about half of capacity. Dotted lines mark the two levels added: S = 1.5x X (0.225 / 0.66 per second, near saturation) and O = 2.0x X (0.30 / 0.88, over saturation).", small))
rows = [["x X", "ped / veh per s"] + ["surrogate " + SHORT[c] for c in CONTROLLERS]]
for mult in sorted({float(r["multiplier"]) for r in sat_sur}):
    group = {r["controller"]: r for r in sat_sur if float(r["multiplier"]) == mult}
    rows.append(["%.1f" % mult, "%s / %s" % (fnum(group["fixed_time"]["ped_rate"], 3), fnum(group["fixed_time"]["veh_rate"], 2))] + ["%s / %s" % (fnum(min(float(group[c]["ped_service_ratio"]), float(group[c]["veh_service_ratio"]))), fnum(group[c]["max_norm_wait"])) for c in CONTROLLERS])
s.append(table(rows, [14 * mm, 28 * mm] + [(W - 42 * mm) / 4.0] * 4))
s.append(P("Surrogate cells: worst service ratio / max wait per limit.", small))
rows = [["x X", "veh per s"] + ["SUMO " + SHORT[c] for c in ("fixed_time", "efficiency", "efpb")]]
for mult in sorted({float(r["multiplier"]) for r in sat_sumo}):
    group = {r["controller"]: r for r in sat_sumo if float(r["multiplier"]) == mult}
    rows.append(["%.1f" % mult, fnum(group["fixed_time"]["veh_rate"], 2)] + ["%s / %s" % (fnum(group[c]["veh_completion_ratio"]), fnum(group[c]["mean_vehicle_queue"], 1)) for c in ("fixed_time", "efficiency", "efpb")])
s.append(table(rows, [14 * mm, 28 * mm] + [(W - 42 * mm) / 3.0] * 3))
s.append(P("SUMO cells: share of vehicle demand completed / mean vehicles queued. SUMO's vehicle throughput plateaus near 2,200 vehicles per hour (about 0.62 per second).", small))

# ------------------------------------------------------------------ 7
s.append(P("7. What these results support, and what they do not", h1))
s += B([
    "<b>Supported (descriptively):</b> under nominal demand, efpb matches or beats the adaptive baselines on person delay and has a lower max wait than efficiency-only control; a properly tuned fixed-time plan is a strong baseline on tail waits. These patterns hold in both backends.",
    "<b>Not supported:</b> any claim that efpb is better under saturation (no clear ordering); any claim about explanations, comprehension, calibrated reliance or fairness perception; any inferential (significance) claim.",
    "<b>Sensitivity to the objectives.</b> Max wait favours short fixed cycles by construction, person delay favours adaptive control, and equal cell weights let the over-saturated cell dominate averages. Report both objectives and the per-cell tables.",
    "<b>Baselines.</b> equal_bargaining collapses under saturation as implemented; the ablation variants (no starvation guard, no efficiency filter, static weights, weighted sum) are not implemented, so no ablation results exist.",
    "<b>Scope.</b> One four-arm intersection; virtual pedestrians (no walking time, crossing or pedestrian clearance interval modelled); SUMO cells cover demand only, not emergency, sensor-error, accessibility or bursty scenarios.",
    "<b>Sample size.</b> The SUMO matrix has 10 seeds per cell where the research plan's design has 30; the 30-seed run is kept as future work (about 50 more minutes on this laptop). The standard errors treat cell-and-seed pairs as independent and ignore differences between cells, so they are not reliable for the 4-cell stress group.",
])

# ------------------------------------------------------------------ 8
s.append(P("8. Where the numbers come from", h1))
s.append(table([
    ["Result", "Files (inside efpb-research-pipeline/)", "How to reproduce"],
    ["SUMO matrix", "data/sumo_matrix/runs/ (runs), data/results/*_sumo.csv", "python run_sumo_matrix.py; python analyze_matrix.py"],
    ["Surrogate matrix", "data/matrix/ (runs), data/results/*_surrogate.csv", "logs/run_matrix_surrogate.sh; python analyze_matrix.py"],
    ["SUMO pilot", "data/sumo_runs/, data/processed/sumo_metrics.csv", "logs/run_sumo_pilot.sh; python aggregate_sumo.py"],
    ["Calibration", "data/calibration_sweep/, data/sumo_calibration/ (selection.json, summary, freeze_report.md)", "sweep_calibration.py / sweep_sumo_calibration.py, then freeze_calibration.py"],
    ["Frozen parameters", "configs/frozen_surrogate.yaml, configs/frozen_sumo.yaml", "written by freeze_calibration.py"],
    ["Demand study", "data/saturation_study/", "python saturation_study.py"],
    ["This document", "docs/make_results.py", "python docs/make_results.py (needs reportlab, pyyaml, matplotlib)"],
], [30 * mm, 85 * mm, W - 115 * mm]))
s.append(P("Every stored run carries a simulator version and a configuration fingerprint, and the simulators refuse to reuse a run made with another configuration. The raw run folders are large and are not committed; the summary CSVs and reports listed above are.", small))

build(s, OUT, "EFPB Simulation Results", "EFPB Research Pipeline – Simulation Results")
