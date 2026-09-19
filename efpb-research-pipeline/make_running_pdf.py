from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors


OUT = Path("release/EFPB_running_instructions.pdf")


def p(text, style):
    return Paragraph(text.replace("&", "&amp;"), style)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, leading=24, spaceAfter=10))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
    styles.add(ParagraphStyle(name="CodeBlock", parent=styles["Code"], fontName="Courier", fontSize=7.5, leading=9, leftIndent=8, rightIndent=8, backColor=colors.HexColor("#f2f2f2"), borderPadding=5, spaceBefore=4, spaceAfter=6))
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title="EFPB research pipeline running instructions")
    story = []
    story.append(Paragraph("EFPB Research Pipeline", styles["TitleCenter"]))
    story.append(Paragraph("Friend-run installation and experiment instructions — release 0.1.0 scaffold", styles["Heading2"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Important status: this package includes a deterministic surrogate backend and a real SUMO/TraCI emergency runner. The emergency runner uses SUMO for vehicle movement and signal execution, while pedestrians remain a reproducible virtual queue because the bundled legacy network has no validated pedestrian walking areas. Read SUMO_EMERGENCY_SCOPE.md and do not present this limited pilot as complete multimodal evidence.", styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("1. Install", styles["Heading1"]))
    story.append(Paragraph("From the extracted package directory:", styles["BodyText"]))
    story.append(Paragraph("cd efpb-research-pipeline<br/>python3 -m venv .venv<br/>source .venv/bin/activate<br/>python -m pip install --upgrade pip<br/>python -m pip install -e '.[dev,analysis]'", styles["CodeBlock"]))
    story.append(Paragraph("Verify the code:", styles["BodyText"]))
    story.append(Paragraph("python -m pytest -q", styles["CodeBlock"]))
    story.append(Paragraph("Expected result: 5 tests pass.", styles["BodyText"]))
    story.append(Paragraph("2. SUMO setup and network check", styles["Heading1"]))
    story.append(Paragraph("Install SUMO using the supported package for your operating system. Then set SUMO_HOME and PATH:", styles["BodyText"]))
    story.append(Paragraph("export SUMO_HOME=/path/to/sumo<br/>export PATH=\"$SUMO_HOME/bin:$PATH\"<br/>bash sumo/build_network.sh<br/>PYTHONPATH=src python validate_sumo.py", styles["CodeBlock"]))
    story.append(Paragraph("If validation fails, stop. Check the SUMO version, environment variables, permissions, and the generated network. Manually inspect the network in sumo-gui before any confirmatory use.", styles["BodyText"]))
    story.append(Paragraph("Emergency real-SUMO run (one-day deadline)", styles["Heading2"]))
    story.append(Paragraph("PYTHONPATH=src python run_sumo_actual.py --config configs/experiments/sumo_emergency.yaml --scenario S1_balanced --controller efpb --seed 9001<br/>PYTHONPATH=src python run_sumo_batch.py --config configs/experiments/sumo_emergency.yaml --machine 1 --machines 2", styles["CodeBlock"]))
    story.append(Paragraph("Run the same batch command on the second computer with --machine 2. The emergency matrix has 36 real SUMO runs (3 scenarios × 4 controllers × 3 paired seeds). Results are written to data/sumo_runs/. After copying both computers' run folders together, aggregate them with:", styles["BodyText"]))
    story.append(Paragraph("python aggregate_sumo.py --input data/sumo_runs --output data/processed/sumo_metrics.csv<br/>python analyze_sumo.py --input data/processed/sumo_metrics.csv --output data/processed/sumo_analysis.json", styles["CodeBlock"]))
    story.append(Paragraph("This is the narrow, time-boxed pilot defined in SUMO_EMERGENCY_SCOPE.md.", styles["BodyText"]))
    story.append(Paragraph("3. Smoke pipeline", styles["Heading1"]))
    story.append(Paragraph("python run_experiment.py --config configs/experiments/smoke.yaml<br/>python aggregate.py --input data/runs --output data/processed/run_metrics.csv<br/>python analyze.py --input data/processed/run_metrics.csv --output data/processed/analysis.json<br/>python generate_figures.py --input data/processed/run_metrics.csv --output data/figures<br/>python build_stimuli.py --input data/runs --output data/stimuli", styles["CodeBlock"]))
    story.append(Paragraph("This runs 2 scenarios × 4 controllers × 1 paired seed = 8 surrogate runs.", styles["BodyText"]))
    story.append(Paragraph("4. Calibration and benchmark", styles["Heading1"]))
    story.append(Paragraph("python calibrate.py --config configs/experiments/calibration.yaml<br/>python benchmark.py --config configs/experiments/benchmark.yaml<br/>python estimate_runtime.py", styles["CodeBlock"]))
    story.append(Paragraph("Inspect calibration output before freezing parameters. Do not tune confirmatory seeds.", styles["BodyText"]))
    story.append(Paragraph("5. Experiment matrix", styles["Heading1"]))
    data = [["Group", "Runs", "Definition"], ["Confirmatory core", "1,080", "9 demand cells × 4 controllers × 30 paired seeds"], ["Robustness", "360", "9 targeted scenarios × 4 controllers × 10 seeds"], ["Ablations", "100", "5 cells × 2 controllers × 10 seeds"], ["Total", "1,540", "Traffic runs"]]
    table = Table(data, colWidths=[38 * mm, 22 * mm, 105 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24445c")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("LEADING", (0, 0), (-1, -1), 10), ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f7f9fb"))]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Run the traffic groups with:", styles["BodyText"]))
    story.append(Paragraph("python run_experiment.py --config configs/experiments/confirmatory_core.yaml<br/>python run_experiment.py --config configs/experiments/robustness.yaml<br/>python run_experiment.py --config configs/experiments/ablations.yaml", styles["CodeBlock"]))
    story.append(Paragraph("6. Two-computer split", styles["Heading1"]))
    story.append(Paragraph("Computer 1", styles["Heading2"]))
    story.append(Paragraph("python run_all.py --machine 1 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml", styles["CodeBlock"]))
    story.append(Paragraph("Computer 2", styles["Heading2"]))
    story.append(Paragraph("python run_all.py --machine 2 --machines 2 --config configs/experiments/confirmatory_core.yaml --config configs/experiments/robustness.yaml", styles["CodeBlock"]))
    story.append(Paragraph("Use the same package, configuration, SUMO release, and seed lists on both computers. Copy completed data/runs subdirectories to one computer, then aggregate once. Do not delete failed runs or rerun selectively without recording the reason.", styles["BodyText"]))
    story.append(Paragraph("7. Outputs", styles["Heading1"]))
    story.append(Paragraph("Each run is stored under data/runs/{scenario}/{controller}/{seed}/{run_id}/ and includes manifest.json, resolved_config.json, states.csv, decisions.jsonl, explanations.jsonl, events.jsonl, run_metrics.json, and run_summary.json. Aggregates go to data/processed/, figures to data/figures/, and stimuli to data/stimuli/.", styles["BodyText"]))
    story.append(Paragraph("8. Runtime estimate", styles["Heading1"]))
    story.append(Paragraph("Measured surrogate benchmark: 3.144 seconds for 660 simulated seconds on the development Mac. The provisional 1,540-run matrix extrapolates to about 8.56 CPU hours, or 4.28 ideal hours on two equal computers. Allow approximately 6.4–8.6 wall-clock hours for overhead. Replace this with a measured headless SUMO benchmark before scheduling final confirmatory runs.", styles["BodyText"]))
    story.append(Paragraph("9. Research integrity", styles["Heading1"]))
    story.append(Paragraph("The paper must not contain fabricated results. Surrogate output is engineering validation only. Report SUMO traffic findings only after SUMO/TraCI validation, calibration lock, complete runs, and result validation. HCI claims require the approved participant study; stimulus generation alone is not HCI evidence.", styles["BodyText"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Source: EFPB research plan and repository release documentation.", styles["Small"]))
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    main()
