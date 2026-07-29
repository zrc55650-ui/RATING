#!/usr/bin/env python3
"""Convert the simple SVG charts emitted by this repository into PDF.

This is intentionally small and dependency-free: it supports the SVG primitives
used by the figure scripts (rect, line, circle, and text), which keeps figure
export reproducible on machines without a browser or SVG converter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def color(value: str, opacity: float = 1.0) -> tuple[float, float, float]:
    value = value.strip()
    if value == "none":
        return 0.0, 0.0, 0.0
    if value.startswith("#"):
        raw = value[1:]
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        rgb = tuple(int(raw[index:index + 2], 16) / 255.0 for index in (0, 2, 4))
    else:
        rgb = (0.0, 0.0, 0.0)
    return tuple(channel * opacity + (1.0 - opacity) for channel in rgb)


def css_rules(svg: str) -> dict[str, dict[str, str]]:
    style_match = re.search(r"<style>(.*?)</style>", svg, re.DOTALL)
    rules: dict[str, dict[str, str]] = {}
    if not style_match:
        return rules
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style_match.group(1)):
        properties = {}
        for item in body.split(";"):
            if ":" in item:
                key, value = item.split(":", 1)
                properties[key.strip()] = value.strip()
        for name in selector.split(","):
            rules[name.strip()] = properties
    return rules


def attrs(element: ET.Element, rules: dict[str, dict[str, str]]) -> dict[str, str]:
    result = dict(rules.get(element.tag.rsplit("}", 1)[-1], {}))
    for class_name in element.attrib.get("class", "").split():
        result.update(rules.get(f".{class_name}", {}))
    result.update({key.rsplit("}", 1)[-1]: value for key, value in element.attrib.items()})
    return result


def number(value: str, default: float = 0.0) -> float:
    match = re.match(r"[-+]?\d*\.?\d+", value or "")
    return float(match.group(0)) if match else default


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def rgb_command(prefix: str, value: str, opacity: float = 1.0) -> str:
    red, green, blue = color(value, opacity)
    return f"{red:.4f} {green:.4f} {blue:.4f} {prefix}"


def make_content(svg_path: Path) -> tuple[bytes, int, int]:
    svg = svg_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    width = int(number(root.attrib.get("width", "900")))
    height = int(number(root.attrib.get("height", "500")))
    rules = css_rules(svg)
    commands = [f"q 1 0 0 -1 0 {height} cm"]

    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "style":
            continue
        values = attrs(element, rules)
        opacity = number(values.get("opacity", "1"), 1.0)
        if tag == "rect":
            x, y = number(values.get("x")), number(values.get("y"))
            w, h = number(values.get("width")), number(values.get("height"))
            fill = values.get("fill", "none")
            stroke = values.get("stroke", "none")
            if fill != "none":
                commands.append(rgb_command("rg", fill, opacity))
                commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
            if stroke != "none":
                commands.append(rgb_command("RG", stroke, opacity))
                commands.append(f"{number(values.get('stroke-width', '1')):.2f} w")
                commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
        elif tag == "line":
            stroke = values.get("stroke", "#000000")
            commands.append(rgb_command("RG", stroke, opacity))
            commands.append(f"{number(values.get('stroke-width', '1')):.2f} w")
            commands.append(
                f"{number(values.get('x1')):.2f} {number(values.get('y1')):.2f} m "
                f"{number(values.get('x2')):.2f} {number(values.get('y2')):.2f} l S"
            )
        elif tag == "circle":
            cx, cy, radius = (number(values.get(key)) for key in ("cx", "cy", "r"))
            fill = values.get("fill", "none")
            stroke = values.get("stroke", "none")
            k = 0.5522848 * radius
            path = (
                f"{cx + radius:.2f} {cy:.2f} m "
                f"{cx + radius:.2f} {cy + k:.2f} {cx + k:.2f} {cy + radius:.2f} {cx:.2f} {cy + radius:.2f} c "
                f"{cx - k:.2f} {cy + radius:.2f} {cx - radius:.2f} {cy + k:.2f} {cx - radius:.2f} {cy:.2f} c "
                f"{cx - radius:.2f} {cy - k:.2f} {cx - k:.2f} {cy - radius:.2f} {cx:.2f} {cy - radius:.2f} c "
                f"{cx + k:.2f} {cy - radius:.2f} {cx + radius:.2f} {cy - k:.2f} {cx + radius:.2f} {cy:.2f} c"
            )
            if fill != "none":
                commands.append(rgb_command("rg", fill, opacity))
                commands.append(path + " f")
            if stroke != "none":
                commands.append(rgb_command("RG", stroke, opacity))
                commands.append(f"{number(values.get('stroke-width', '1')):.2f} w")
                commands.append(path + " S")
        elif tag == "text":
            text = "".join(element.itertext())
            if not text:
                continue
            x, y = number(values.get("x")), number(values.get("y"))
            size = number(values.get("font-size", "14"), 14.0)
            font = "/F2" if values.get("font-weight") == "700" else "/F1"
            anchor = values.get("text-anchor", "start")
            estimated_width = size * 0.52 * len(text)
            if anchor == "middle":
                x -= estimated_width / 2
            elif anchor == "end":
                x -= estimated_width
            fill = values.get("fill", "#172033")
            commands.append(rgb_command("rg", fill, opacity))
            transform = values.get("transform", "")
            if "rotate(-90" in transform:
                commands.append(f"BT {font} {size:.2f} Tf 0 -1 1 0 {x:.2f} {y:.2f} Tm ({pdf_escape(text)}) Tj ET")
            else:
                commands.append(f"BT {font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({pdf_escape(text)}) Tj ET")

    commands.append("Q")
    return "\n".join(commands).encode("ascii"), width, height


def write_pdf(output: Path, content: bytes, width: int, height: int) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: svg_to_pdf.py INPUT.svg OUTPUT.pdf")
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    content, width, height = make_content(source)
    write_pdf(destination, content, width, height)
    print(f"Wrote {destination}")
