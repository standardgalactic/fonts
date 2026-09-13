"""Measurement, validation, and provenance support for font experiments."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from fontTools.ttLib import TTFont


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def measure_font(font):
    """Return representation-level measurements without perceptual claims."""
    glyphs = contours = points = 0
    contour_length = 0.0
    bounds = []
    glyf = font.get("glyf")
    if glyf is not None:
        for name in font.getGlyphOrder():
            glyph = glyf[name]
            if glyph.isComposite() or not hasattr(glyph, "coordinates"):
                continue
            coords = glyph.coordinates
            if not coords:
                continue
            glyphs += 1
            points += len(coords)
            contours += max(0, glyph.numberOfContours)
            xs, ys = [p[0] for p in coords], [p[1] for p in coords]
            bounds.append((min(xs), min(ys), max(xs), max(ys)))
            start = 0
            for end in glyph.endPtsOfContours:
                ring = coords[start:end + 1]
                if len(ring) > 1:
                    pairs = zip(ring, list(ring[1:]) + [ring[0]])
                    contour_length += sum(math.hypot(b[0] - a[0], b[1] - a[1])
                                          for a, b in pairs)
                start = end + 1

    bbox = None
    if bounds:
        bbox = {
            "x_min": min(b[0] for b in bounds), "y_min": min(b[1] for b in bounds),
            "x_max": max(b[2] for b in bounds), "y_max": max(b[3] for b in bounds),
        }
    advances = []
    if "hmtx" in font:
        advances = [advance for advance, _ in font["hmtx"].metrics.values()]
    return {
        "simple_glyphs": glyphs,
        "contours": contours,
        "points": points,
        "total_contour_length": round(contour_length, 3),
        "bounding_box": bbox,
        "advance_width": {
            "minimum": min(advances) if advances else None,
            "maximum": max(advances) if advances else None,
            "mean": round(sum(advances) / len(advances), 3) if advances else None,
        },
    }


def validate_font(font):
    """Check structural invariants that can be tested before serialization."""
    errors = []
    for table in ("head", "maxp", "cmap"):
        if table not in font:
            errors.append(f"missing required table: {table}")
    glyf = font.get("glyf")
    if glyf is None:
        errors.append("missing glyf table")
        return errors
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.isComposite() or not hasattr(glyph, "coordinates"):
            continue
        if glyph.endPtsOfContours and glyph.endPtsOfContours[-1] >= len(glyph.coordinates):
            errors.append(f"{name}: contour endpoint exceeds coordinate count")
        for x, y in glyph.coordinates:
            if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
                errors.append(f"{name}: coordinate outside int16 range")
                break
    return errors


def validate_saved_font(path):
    """Reopen a serialized font and return its errors and measured state."""
    try:
        reopened = TTFont(str(path))
        reopened.getGlyphOrder()
        errors = validate_font(reopened)
        metrics = measure_font(reopened)
        reopened.close()
        return errors, metrics
    except Exception as exc:
        return [f"reopen failed: {type(exc).__name__}: {exc}"], None


def write_provenance(output_path, *, source_path, transform, parameters,
                     sequence_kind, step=None, steps=None, parent=None,
                     source_metrics=None, output_metrics=None):
    output_path = Path(output_path)
    record = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "source_sha256": sha256_file(source_path),
        "output": output_path.name,
        "output_sha256": sha256_file(output_path),
        "transform": transform,
        "parameters": parameters,
        "sequence_kind": sequence_kind,
        "step": step,
        "steps": steps,
        "parent": str(parent) if parent else None,
        "measurements": {"source": source_metrics, "output": output_metrics},
        "claim_scope": "geometric",
    }
    sidecar = output_path.with_suffix(".json")
    sidecar.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sidecar
