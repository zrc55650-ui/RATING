#!/usr/bin/env python3
"""Export generated SVG figures to single-page PDF and PNG files with Edge."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from analysis_common import ROOT


FIGURES = [
    "figure1_intervention_design.svg",
    "figure2_rating_step_type_heatmap.svg",
    "figure3_placebo_decomposition.svg",
    "figure4_control_stability.svg",
    "step_stability_heatmap.svg",
    "placebo_eligibility_loveplot.svg",
    "risk_coverage_danger.svg",
    "risk_coverage_benefit.svg",
    "judge_audit_confusion_matrix.svg",
]

WORKSTREAM_F_FIGURES = {
    "figure1_intervention_design.svg",
    "figure2_rating_step_type_heatmap.svg",
    "figure3_placebo_decomposition.svg",
    "figure4_control_stability.svg",
}

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def main() -> None:
    edge = next((candidate for candidate in EDGE_CANDIDATES if candidate.exists()), None)
    if edge is None:
        raise FileNotFoundError("Microsoft Edge was not found")
    temp_name = ROOT / "figure_export_temp"
    temp_name.mkdir(exist_ok=True)
    if True:
        temp = Path(temp_name)
        profile = temp / "edge-profile"
        for figure_name in FIGURES:
            svg_path = (
                ROOT / "workstream_A_judge_audit" / figure_name
                if figure_name == "judge_audit_confusion_matrix.svg"
                else ROOT / figure_name
            )
            svg = svg_path.read_text(encoding="utf-8")
            width_match = re.search(r'width="(\d+)', svg)
            height_match = re.search(r'height="(\d+)', svg)
            width = int(width_match.group(1)) if width_match else 900
            height = int(height_match.group(1)) if height_match else 500
            page_width = max(7.0, width / 100)
            page_height = max(4.0, height / 100)
            html = (
                "<!doctype html><meta charset='utf-8'><style>"
                f"@page{{size:{page_width:.2f}in {page_height:.2f}in;margin:0}}"
                "html,body{margin:0;padding:0;background:white;width:100%;height:100%;"
                "display:flex;align-items:center;justify-content:center}"
                "svg{width:100%;height:100%;display:block}"
                "</style>"
                + svg
            )
            wrapper = temp / f"{svg_path.stem}.html"
            wrapper.write_text(html, encoding="utf-8")
            output = svg_path.with_suffix(".pdf")
            completed = subprocess.run(
                [
                    str(edge),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--user-data-dir={profile}",
                    f"--print-to-pdf={output}",
                    wrapper.as_uri(),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            if completed.returncode or not output.exists() or output.stat().st_size == 0:
                raise RuntimeError(
                    f"Failed to export {figure_name}: "
                    f"{completed.stderr or completed.stdout}"
                )
            print(f"Exported {output.name}")
            png_output = svg_path.with_suffix(".png")
            completed = subprocess.run(
                [
                    str(edge),
                    "--headless=new",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    f"--window-size={width},{height}",
                    f"--user-data-dir={profile}",
                    f"--screenshot={png_output}",
                    wrapper.as_uri(),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            if (
                completed.returncode
                or not png_output.exists()
                or png_output.stat().st_size == 0
            ):
                raise RuntimeError(
                    f"Failed to export PNG for {figure_name}: "
                    f"{completed.stderr or completed.stdout}"
                )
            if figure_name in WORKSTREAM_F_FIGURES:
                destination = ROOT / "workstream_F_final_statistics"
                destination.mkdir(exist_ok=True)
                shutil.copyfile(output, destination / output.name)
                shutil.copyfile(png_output, destination / png_output.name)
            print(f"Exported {png_output.name}")


if __name__ == "__main__":
    main()
