"""Backend-independent CSV and SVG artifacts rendered from canonical fields."""

from __future__ import annotations

import csv
import html
import io
import math
from pathlib import Path

from tcad_agent.results.models import CanonicalResult, FieldSeries

_WIDTH = 960
_PANEL_HEIGHT = 250
_LEFT = 92
_RIGHT = 28
_TOP = 54
_BOTTOM = 48


class FieldArtifactWriter:
    def write(self, result: CanonicalResult, output: Path) -> tuple[Path, Path]:
        output.mkdir(parents=True, exist_ok=True)
        csv_path = output / "fields.csv"
        svg_path = output / "field-plots.svg"
        csv_path.write_text(self._csv(result))
        svg_path.write_text(self._svg(result))
        return csv_path, svg_path

    @staticmethod
    def _csv(result: CanonicalResult) -> str:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("field", "position_m", "value", "unit"))
        for name, field in sorted(result.fields.items()):
            for position, value in zip(field.positions_m, field.values, strict=False):
                writer.writerow((name, f"{position:.17g}", f"{value:.17g}", field.unit))
        return stream.getvalue()

    def _svg(self, result: CanonicalResult) -> str:
        fields = sorted(result.fields.items())
        height = max(180, len(fields) * _PANEL_HEIGHT)
        rows = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" '
                f'height="{height}" viewBox="0 0 {_WIDTH} {height}" role="img" '
                'aria-label="Normalized TCAD field plots">'
            ),
            "<style>",
            "text{font-family:Inter,system-ui,sans-serif;fill:#dce4f5}",
            ".title{font-size:17px;font-weight:700}.label{font-size:12px;fill:#98a6bf}",
            ".axis{stroke:#59677e;stroke-width:1}.grid{stroke:#283348;stroke-width:1}",
            ".trace{fill:none;stroke:#6f91ff;stroke-width:2.25}",
            ".panel{fill:#111827;stroke:#263249;stroke-width:1}",
            "</style>",
            '<rect width="100%" height="100%" fill="#0b1020"/>',
        ]
        if not fields:
            rows.append(
                '<text x="48" y="92" class="title">No normalized spatial fields available</text>'
            )
        for index, (name, field) in enumerate(fields):
            rows.extend(self._panel(index * _PANEL_HEIGHT, name, field))
        rows.append("</svg>\n")
        return "\n".join(rows)

    def _panel(self, offset: int, name: str, field: FieldSeries) -> list[str]:
        plot_width = _WIDTH - _LEFT - _RIGHT
        plot_height = _PANEL_HEIGHT - _TOP - _BOTTOM
        x0 = _LEFT
        y0 = offset + _TOP
        safe_name = html.escape(name)
        safe_unit = html.escape(field.unit)
        rows = [
            (
                f'<rect class="panel" x="20" y="{offset + 14}" width="{_WIDTH - 40}" '
                f'height="{_PANEL_HEIGHT - 24}" rx="10"/>'
            ),
            f'<text class="title" x="40" y="{offset + 40}">{safe_name}</text>',
        ]
        pairs = [
            (position, value)
            for position, value in zip(field.positions_m, field.values, strict=False)
            if math.isfinite(position) and math.isfinite(value)
        ]
        if len(pairs) < 2:
            rows.append(
                f'<text class="label" x="{x0}" y="{y0 + 30}">Insufficient finite data</text>'
            )
            return rows

        positions = [item[0] for item in pairs]
        values = [item[1] for item in pairs]
        log_scale = (
            "m^-3" in field.unit
            and min(values) > 0
            and max(values) / min(values) >= 1.0e3
        )
        display_values = [math.log10(value) for value in values] if log_scale else values
        xmin, xmax = min(positions), max(positions)
        ymin, ymax = min(display_values), max(display_values)
        if math.isclose(xmin, xmax):
            xmax = xmin + 1.0
        if math.isclose(ymin, ymax):
            padding = max(abs(ymin) * 0.05, 1.0)
            ymin -= padding
            ymax += padding

        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = y0 + plot_height * (1.0 - fraction)
            rows.append(
                f'<line class="grid" x1="{x0}" y1="{y:.3f}" '
                f'x2="{x0 + plot_width}" y2="{y:.3f}"/>'
            )
        rows.extend(
            (
                f'<line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" '
                f'y2="{y0 + plot_height}"/>',
                f'<line class="axis" x1="{x0}" y1="{y0 + plot_height}" '
                f'x2="{x0 + plot_width}" y2="{y0 + plot_height}"/>',
            )
        )
        points = []
        for position, value in zip(positions, display_values, strict=True):
            x = x0 + (position - xmin) / (xmax - xmin) * plot_width
            y = y0 + (1.0 - (value - ymin) / (ymax - ymin)) * plot_height
            points.append(f"{x:.3f},{y:.3f}")
        rows.append(f'<polyline class="trace" points="{" ".join(points)}"/>')
        scale_label = f"log10({safe_unit})" if log_scale else safe_unit
        rows.extend(
            (
                f'<text class="label" x="{x0}" y="{y0 + plot_height + 24}">'
                f'{xmin:.3e} m</text>',
                f'<text class="label" text-anchor="end" x="{x0 + plot_width}" '
                f'y="{y0 + plot_height + 24}">{xmax:.3e} m</text>',
                f'<text class="label" x="{x0 + 8}" y="{y0 + 16}">'
                f'{ymax:.3e} {scale_label}</text>',
                f'<text class="label" x="{x0 + 8}" y="{y0 + plot_height - 8}">'
                f'{ymin:.3e} {scale_label}</text>',
            )
        )
        return rows
