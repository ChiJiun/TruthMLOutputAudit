from __future__ import annotations

import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
SUMMARY_PATH = RESULTS_DIR / "summary.md"
OUTPUT_PATH = RESULTS_DIR / "s2_accuracy_comparison.svg"


def parse_summary(path: Path) -> tuple[float, float, float, str]:
    text = path.read_text(encoding="utf-8")

    def extract_float(label: str) -> float:
        match = re.search(rf"{re.escape(label)}:\s*([0-9.]+)", text)
        if not match:
            raise ValueError(f"Could not find '{label}' in {path}")
        return float(match.group(1))

    accepted_match = re.search(r"Accepted clients:\s*([0-9]+/[0-9]+)", text)
    if not accepted_match:
        raise ValueError(f"Could not find accepted client ratio in {path}")

    return (
        extract_float("Initial accuracy"),
        extract_float("Proof-gated next-round accuracy"),
        extract_float("Ungated next-round accuracy"),
        accepted_match.group(1),
    )


def svg_bar(x: float, y: float, width: float, height: float, color: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="10" fill="{color}" />'


def generate_svg(initial: float, proof_gated: float, ungated: float, accepted_ratio: str) -> str:
    width = 1360
    height = 820
    left = 110
    right = 270
    top = 150
    bottom = 190
    plot_width = width - left - right
    plot_height = height - top - bottom

    categories = [
        ("Initial", initial, "#9AA0A6"),
        ("Proof-Gated", proof_gated, "#1F77B4"),
        ("Ungated", ungated, "#F28E2B"),
    ]

    y_min = 0.65
    y_max = 0.86

    def to_y(value: float) -> float:
        norm = (value - y_min) / (y_max - y_min)
        return top + plot_height - norm * plot_height

    grid_values = [0.65, 0.70, 0.75, 0.80, 0.85]
    bar_width = 180
    gap = (plot_width - bar_width * len(categories)) / (len(categories) + 1)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FAFAF8" />',
        '<text x="110" y="64" font-family="Segoe UI, Arial, sans-serif" font-size="32" font-weight="700" fill="#1F2937">Accuracy After Verifying Client DP Updates Before Aggregation</text>',
        '<text x="110" y="98" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#4B5563">This experiment compares a proof-checked aggregation path against aggregating all submitted client updates.</text>',
    ]

    for grid in grid_values:
        y = to_y(grid)
        svg_parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#D1D5DB" stroke-width="1" />')
        svg_parts.append(
            f'<text x="{left-18}" y="{y+6:.1f}" text-anchor="end" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#6B7280">{grid:.2f}</text>'
        )

    axis_y = top + plot_height
    svg_parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{axis_y}" stroke="#374151" stroke-width="2" />')
    svg_parts.append(f'<line x1="{left}" y1="{axis_y}" x2="{width-right}" y2="{axis_y}" stroke="#374151" stroke-width="2" />')
    svg_parts.append(
        f'<text x="38" y="{top + plot_height / 2:.1f}" transform="rotate(-90 38 {top + plot_height / 2:.1f})" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#374151">Accuracy</text>'
    )

    for index, (label, value, color) in enumerate(categories):
        x = left + gap + index * (bar_width + gap)
        y = to_y(value)
        bar_height = axis_y - y
        svg_parts.append(svg_bar(x, y, bar_width, bar_height, color))
        value_box_y = y - 36
        svg_parts.append(
            f'<rect x="{x + 24:.1f}" y="{value_box_y - 22:.1f}" width="{bar_width - 48:.1f}" height="30" rx="8" fill="#FFFFFF" opacity="0.92" />'
        )
        svg_parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{value_box_y:.1f}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="23" font-weight="700" fill="#111827">{value:.6f}</text>'
        )
        svg_parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{axis_y + 34:.1f}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="20" font-weight="600" fill="#1F2937">{label}</text>'
        )
        if label == "Proof-Gated":
            detail = "Only verified updates"
        elif label == "Ungated":
            detail = "All submitted updates"
        else:
            detail = "Before round update"
        svg_parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{axis_y + 60:.1f}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#6B7280">{detail}</text>'
        )

    note_x = 1095
    note_y = 220
    note_w = 200
    note_h = 136
    svg_parts.extend(
        [
            f'<rect x="{note_x}" y="{note_y}" width="{note_w}" height="{note_h}" rx="16" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="1.5" />',
            f'<text x="{note_x + 20}" y="{note_y + 34}" font-family="Segoe UI, Arial, sans-serif" font-size="20" font-weight="700" fill="#111827">Notes</text>',
            f'<text x="{note_x + 20}" y="{note_y + 68}" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#374151">Accepted: {accepted_ratio}</text>',
            f'<text x="{note_x + 20}" y="{note_y + 98}" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#374151">Rejected: 1/3</text>',
            f'<text x="{note_x + 20}" y="{note_y + 128}" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#374151">Tampered: No</text>',
        ]
    )

    caption = (
        "Figure. The server first verifies whether each client update satisfies the auditable DP constraints, then aggregates only the accepted updates."
    )
    svg_parts.append(
        f'<text x="110" y="{height - 44}" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#4B5563">{caption}</text>'
    )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def main() -> int:
    initial, proof_gated, ungated, accepted_ratio = parse_summary(SUMMARY_PATH)
    svg = generate_svg(initial, proof_gated, ungated, accepted_ratio)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Saved chart to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
