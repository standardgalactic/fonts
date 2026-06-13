import os
import sys
import random
import argparse
import math
from pathlib import Path
from fontTools.ttLib import TTFont

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_font(path):
    return TTFont(str(path))

def get_glyf(font):
    return font.get("glyf")

def iter_simple_glyphs(font):
    """Yield (name, glyph) for every non-composite glyph with contours."""
    glyf = get_glyf(font)
    if glyf is None:
        return
    for name in glyf.keys():
        g = glyf[name]
        if g.isComposite():
            continue
        if not hasattr(g, "numberOfContours") or g.numberOfContours <= 0:
            continue
        yield name, g

# TrueType signed int16 coordinate bounds
COORD_MIN, COORD_MAX = -32000, 32000

def clamp_coords(font):
    """Clamp all glyph coordinates to TrueType int16 safe range."""
    glyf = get_glyf(font)
    if glyf is None:
        return
    for name in glyf.keys():
        g = glyf[name]
        if g.isComposite() or not hasattr(g, "numberOfContours") or g.numberOfContours <= 0:
            continue
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (
                max(COORD_MIN, min(COORD_MAX, int(x))),
                max(COORD_MIN, min(COORD_MAX, int(y))),
            )

def normalize_font(font, margin=30000):
    """
    If any coordinate exceeds margin, scale the entire font down uniformly
    so the largest absolute coordinate equals margin. Prevents xMaxExtent
    overflow that persists after coordinate clamping because fontTools
    recomputes bbox metrics from glyph data at compile time.
    """
    glyf = get_glyf(font)
    if glyf is None:
        return
    max_coord = 0
    for name in glyf.keys():
        g = glyf[name]
        if g.isComposite() or not hasattr(g, "coordinates"):
            continue
        for x, y in g.coordinates:
            max_coord = max(max_coord, abs(x), abs(y))
    if max_coord <= margin or max_coord == 0:
        return
    scale = margin / max_coord
    print(f"    [normalize] rescaling by {scale:.4f} (max coord was {max_coord})")
    for name in glyf.keys():
        g = glyf[name]
        if g.isComposite() or not hasattr(g, "coordinates"):
            continue
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (int(x * scale), int(y * scale))

def clamp_metrics(font):
    """
    Clamp font-level metric fields stored as int16 in hhea/head/OS2.
    fontTools recomputes some of these from glyph bboxes on save, so we
    force them into range after coordinate mutation.
    """
    INT16_MIN, INT16_MAX = -32768, 32767

    for table_tag in ("hhea", "vhea"):
        if table_tag not in font:
            continue
        t = font[table_tag]
        for attr in ("advanceWidthMax", "minLeftSideBearing", "minRightSideBearing",
                     "xMaxExtent", "caretSlopeRise", "caretSlopeRun", "caretOffset",
                     "ascent", "descent", "lineGap",
                     "advanceHeightMax", "minTopSideBearing", "minBottomSideBearing",
                     "yMaxExtent"):
            if hasattr(t, attr):
                v = getattr(t, attr)
                if isinstance(v, (int, float)):
                    setattr(t, attr, max(INT16_MIN, min(INT16_MAX, int(v))))

    if "head" in font:
        h = font["head"]
        for attr in ("xMin", "yMin", "xMax", "yMax"):
            if hasattr(h, attr):
                v = getattr(h, attr)
                if isinstance(v, (int, float)):
                    setattr(h, attr, max(INT16_MIN, min(INT16_MAX, int(v))))

    if "OS/2" in font:
        o = font["OS/2"]
        for attr in ("sTypoAscender", "sTypoDescender", "sTypoLineGap",
                     "usWinAscent", "usWinDescent",
                     "sxHeight", "sCapHeight",
                     "ySubscriptXSize", "ySubscriptYSize",
                     "ySubscriptXOffset", "ySubscriptYOffset",
                     "ySuperscriptXSize", "ySuperscriptYSize",
                     "ySuperscriptXOffset", "ySuperscriptYOffset",
                     "yStrikeoutSize", "yStrikeoutPosition"):
            if hasattr(o, attr):
                v = getattr(o, attr)
                if isinstance(v, (int, float)):
                    setattr(o, attr, max(INT16_MIN, min(INT16_MAX, int(v))))

INT16_MIN_SAVE = -32768
INT16_MAX_SAVE = 32767

# Fields actually stored as signed int16 in each table
_INT16_FIELDS = {
    "hhea": ("advanceWidthMax", "minLeftSideBearing", "minRightSideBearing",
             "xMaxExtent", "caretSlopeRise", "caretSlopeRun", "caretOffset",
             "ascent", "descent", "lineGap"),
    "vhea": ("advanceHeightMax", "minTopSideBearing", "minBottomSideBearing",
             "yMaxExtent", "caretSlopeRise", "caretSlopeRun", "caretOffset",
             "ascent", "descent", "lineGap"),
    "head": ("xMin", "yMin", "xMax", "yMax"),
    "OS/2": ("sTypoAscender", "sTypoDescender", "sTypoLineGap",
             "sxHeight", "sCapHeight",
             "ySubscriptXSize", "ySubscriptYSize",
             "ySubscriptXOffset", "ySubscriptYOffset",
             "ySuperscriptXSize", "ySuperscriptYSize",
             "ySuperscriptXOffset", "ySuperscriptYOffset",
             "yStrikeoutSize", "yStrikeoutPosition"),
}

def check_overflows(font):
    found = []
    for table_tag, fields in _INT16_FIELDS.items():
        if table_tag not in font:
            continue
        t = font[table_tag]
        for field in fields:
            if hasattr(t, field):
                v = getattr(t, field)
                if isinstance(v, (int, float)) and (v < INT16_MIN_SAVE or v > INT16_MAX_SAVE):
                    found.append(f"  OVERFLOW {table_tag}.{field} = {v}")
    return found

def diagnostic_report(font):
    print("\n===== FONT DIAGNOSTICS =====")
    for table_tag in ("head", "hhea"):
        if table_tag not in font:
            continue
        t = font[table_tag]
        print(table_tag.upper())
        for field in ("xMin","yMin","xMax","yMax",
                      "advanceWidthMax","minLeftSideBearing","minRightSideBearing",
                      "xMaxExtent","ascent","descent","lineGap"):
            if hasattr(t, field):
                print(f"  {field} = {getattr(t, field)}")
    if "hmtx" in font:
        metrics = font["hmtx"].metrics
        if metrics:
            biggest_adv = max(metrics.items(), key=lambda kv: abs(kv[1][0]))
            biggest_lsb = max(metrics.items(), key=lambda kv: abs(kv[1][1]))
            print(f"  largest advance: {biggest_adv}")
            print(f"  largest lsb:     {biggest_lsb}")
    if "glyf" in font:
        biggest_name, biggest_extent = None, -1
        glyf_table = font["glyf"]
        for name in font.getGlyphOrder():
            try:
                g = glyf_table[name]
            except Exception:
                continue
            if g.isComposite() or not hasattr(g, "coordinates") or not g.coordinates:
                continue
            xs = [p[0] for p in g.coordinates]
            extent = max(xs) - min(xs)
            if extent > biggest_extent:
                biggest_extent, biggest_name = extent, name
        print(f"  largest glyph extent: {biggest_name} = {biggest_extent}")
    print("============================\n")

def save_font(font, path):
    normalize_font(font)
    clamp_coords(font)
    clamp_metrics(font)
    if get_glyf(font) is not None:
        font["glyf"].recalcBBoxes = False
    # hhea.xMaxExtent is recomputed from hmtx+glyf during compile regardless
    # of recalcBBoxes. Force it into range now, after all other clamping.
    if "hhea" in font:
        font["hhea"].xMaxExtent = max(INT16_MIN_SAVE, min(INT16_MAX_SAVE,
                                      font["hhea"].xMaxExtent))
    # Also clamp minRightSideBearing which can go very negative after radial distortion
    if "hhea" in font and hasattr(font["hhea"], "minRightSideBearing"):
        font["hhea"].minRightSideBearing = max(INT16_MIN_SAVE,
            min(INT16_MAX_SAVE, font["hhea"].minRightSideBearing))
    overflows = check_overflows(font)
    if overflows:
        print(f"  [pre-save overflows in {Path(path).name}]")
        for line in overflows:
            print(line)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        font.save(str(path))
        print(f"  -> {path}")
    except Exception as e:
        print(f"\n  FAILED: {Path(path).name}")
        print(f"  {type(e).__name__}: {e}")
        diagnostic_report(font)
        xml_path = str(path).replace(".ttf", "_FAILED.ttx")
        try:
            font.saveXML(xml_path)
            print(f"  debug XML -> {xml_path}")
        except Exception:
            pass
        print("  (skipping, continuing run)\n")
        return  # don't re-raise; let the run continue

# ─────────────────────────────────────────────────────────────────────────────
# Transform families
# ─────────────────────────────────────────────────────────────────────────────

def apply_jitter(font, strength, seed=42):
    """Uniform random point displacement."""
    rng = random.Random(seed)
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (
                x + rng.randint(-strength, strength),
                y + rng.randint(-strength, strength),
            )

def apply_gaussian_jitter(font, sigma, seed=42):
    """Gaussian noise — more central-tendency drift, fewer extreme outliers."""
    rng = random.Random(seed)
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (
                int(x + rng.gauss(0, sigma)),
                int(y + rng.gauss(0, sigma)),
            )

def apply_condense(font, factor):
    """Scale x-coordinates by factor, leave y unchanged."""
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (int(x * factor), y)

def apply_shear(font, amount):
    """Horizontal shear: x += amount * y."""
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (int(x + amount * y), y)

def apply_vertical_shear(font, amount):
    """Vertical shear: y += amount * x."""
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (x, int(y + amount * x))

def apply_baseline_droop(font, strength):
    """
    Points droop downward proportionally to their x position.
    Simulates letterforms melting toward the right margin.
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        if not coords:
            continue
        xs = [p[0] for p in coords]
        x_max = max(xs) or 1
        for i, (x, y) in enumerate(coords):
            droop = int(strength * (x / x_max) * 200)
            coords[i] = (x, y - droop)

def apply_ascender_evaporation(font, strength):
    """
    Points above the baseline drift upward/shrink — ascenders dissolve.
    strength 0.0–1.0
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            if y > 400:  # rough x-height threshold in font units
                scale = 1.0 - strength * ((y - 400) / 600.0)
                coords[i] = (x, int(y * max(0.05, scale)))

def apply_descender_erosion(font, strength):
    """
    Points below baseline shrink toward it — g, p, q, y lose their tails.
    strength 0.0–1.0
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            if y < 0:
                coords[i] = (x, int(y * (1.0 - strength)))

def apply_stroke_collapse(font, strength):
    """
    Compress all glyphs horizontally toward their own center.
    Strokes get thinner, letters become reedy.
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        if not coords:
            continue
        xs = [p[0] for p in coords]
        cx = sum(xs) / len(xs)
        for i, (x, y) in enumerate(coords):
            coords[i] = (int(cx + (x - cx) * (1.0 - strength * 0.7)), y)

def apply_quantize(font, grid):
    """
    Snap all coordinates to a grid.
    Low grid values (8, 16) produce a chunky pixelated look.
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (
                round(x / grid) * grid,
                round(y / grid) * grid,
            )

def apply_wave(font, amplitude, frequency):
    """
    Sinusoidal y-displacement based on x position.
    Letterforms ripple like reflection in water.
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            offset = int(amplitude * math.sin(x * frequency * 2 * math.pi / 1000))
            coords[i] = (x, y + offset)

def apply_radial_distortion(font, strength, seed=42):
    """
    Points further from origin get displaced more — barrel/pincushion distortion.
    """
    rng = random.Random(seed)
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        if not coords:
            continue
        xs, ys = [p[0] for p in coords], [p[1] for p in coords]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        for i, (x, y) in enumerate(coords):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx*dx + dy*dy) or 1
            factor = 1.0 + strength * dist / 500.0
            coords[i] = (
                int(cx + dx * factor + rng.gauss(0, strength * 2)),
                int(cy + dy * factor + rng.gauss(0, strength * 2)),
            )

def apply_point_dropout(font, rate, seed=42):
    """
    Randomly collapse a fraction of glyph points to their neighbours.
    Creates letterforms with missing segments.
    rate 0.0–1.0
    """
    rng = random.Random(seed)
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        n = len(coords)
        for i in range(n):
            if rng.random() < rate:
                neighbour = coords[(i + 1) % n]
                coords[i] = neighbour

def apply_rotation(font, angle_deg):
    """Rotate all glyph coordinates around origin by angle_deg."""
    theta = math.radians(angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (
                int(x * cos_t - y * sin_t),
                int(x * sin_t + y * cos_t),
            )

def apply_vertical_squash(font, factor):
    """Scale y uniformly — compress or expand vertically."""
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            coords[i] = (x, int(y * factor))

def apply_echo(font, offset_x, offset_y, blend=0.3):
    """
    Add a ghost copy of each point offset by (offset_x, offset_y),
    blended toward the original — creates a shadow-echo effect.
    """
    for _, g in iter_simple_glyphs(font):
        coords = g.coordinates
        for i, (x, y) in enumerate(coords):
            ex = x + offset_x
            ey = y + offset_y
            coords[i] = (
                int(x * (1 - blend) + ex * blend),
                int(y * (1 - blend) + ey * blend),
            )

# ─────────────────────────────────────────────────────────────────────────────
# Sequence generator — interpolate a single parameter across N steps
# ─────────────────────────────────────────────────────────────────────────────

def generate_sequence(source_path, out_dir, prefix, transform_fn, param_range, steps):
    """
    Generate `steps` fonts by linearly interpolating param_range=(lo, hi)
    and applying transform_fn(font, param).
    """
    lo, hi = param_range
    for i in range(steps):
        t = i / max(1, steps - 1)
        param = lo + t * (hi - lo)
        font = load_font(source_path)
        transform_fn(font, param)
        stem = source_path.stem
        fname = out_dir / f"{stem}_{prefix}_{i:03d}.ttf"
        save_font(font, fname)

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate experimental font variants.")
    parser.add_argument("source_dir", nargs="?", default=".", help="Directory containing .ttf files")
    parser.add_argument("--steps", type=int, default=8, help="Steps per parametric series")
    parser.add_argument("--out", default="experiments", help="Output directory")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    out_base = Path(args.out)
    steps = args.steps

    fonts = sorted(source_dir.glob("*.ttf"))
    if not fonts:
        print(f"No .ttf files found in {source_dir}")
        sys.exit(1)

    print(f"Found {len(fonts)} source font(s): {[f.name for f in fonts]}")
    print(f"Output: {out_base}/  |  Steps per series: {steps}\n")

    for fontfile in fonts:
        stem = fontfile.stem
        print(f"\n{'='*60}")
        print(f"Source: {fontfile.name}")
        print(f"{'='*60}")

        # ── 1. Static single-shot variants ───────────────────────────────────

        singles = {
            "static": [
                ("jitter_mild",    lambda f: apply_jitter(f, 8)),
                ("jitter_heavy",   lambda f: apply_jitter(f, 30)),
                ("gaussian_mild",  lambda f: apply_gaussian_jitter(f, 6)),
                ("gaussian_heavy", lambda f: apply_gaussian_jitter(f, 25)),
                ("condense_60",    lambda f: apply_condense(f, 0.60)),
                ("condense_80",    lambda f: apply_condense(f, 0.80)),
                ("expand_120",     lambda f: apply_condense(f, 1.20)),
                ("expand_150",     lambda f: apply_condense(f, 1.50)),
                ("shear_fwd_10",   lambda f: apply_shear(f, 0.10)),
                ("shear_fwd_25",   lambda f: apply_shear(f, 0.25)),
                ("shear_back_10",  lambda f: apply_shear(f, -0.10)),
                ("vshear_10",      lambda f: apply_vertical_shear(f, 0.10)),
                ("vshear_neg10",   lambda f: apply_vertical_shear(f, -0.10)),
                ("droop_mild",     lambda f: apply_baseline_droop(f, 0.3)),
                ("droop_heavy",    lambda f: apply_baseline_droop(f, 0.8)),
                ("asc_evap_30",    lambda f: apply_ascender_evaporation(f, 0.30)),
                ("asc_evap_70",    lambda f: apply_ascender_evaporation(f, 0.70)),
                ("desc_erode_50",  lambda f: apply_descender_erosion(f, 0.50)),
                ("stroke_collapse_30", lambda f: apply_stroke_collapse(f, 0.30)),
                ("stroke_collapse_70", lambda f: apply_stroke_collapse(f, 0.70)),
                ("quantize_8",     lambda f: apply_quantize(f, 8)),
                ("quantize_16",    lambda f: apply_quantize(f, 16)),
                ("quantize_32",    lambda f: apply_quantize(f, 32)),
                ("wave_mild",      lambda f: apply_wave(f, 40, 1.5)),
                ("wave_heavy",     lambda f: apply_wave(f, 100, 2.5)),
                ("radial_mild",    lambda f: apply_radial_distortion(f, 0.3)),
                ("radial_heavy",   lambda f: apply_radial_distortion(f, 0.9)),
                ("dropout_5pct",   lambda f: apply_point_dropout(f, 0.05)),
                ("dropout_20pct",  lambda f: apply_point_dropout(f, 0.20)),
                ("dropout_40pct",  lambda f: apply_point_dropout(f, 0.40)),
                ("rotate_5",       lambda f: apply_rotation(f, 5)),
                ("rotate_neg5",    lambda f: apply_rotation(f, -5)),
                ("vsquash_70",     lambda f: apply_vertical_squash(f, 0.70)),
                ("vstretch_130",   lambda f: apply_vertical_squash(f, 1.30)),
                ("echo_right",     lambda f: apply_echo(f, 30, 0, 0.25)),
                ("echo_shadow",    lambda f: apply_echo(f, 15, -15, 0.30)),
            ]
        }

        static_dir = out_base / "static"
        for _, variants in singles.items():
            for name, fn in variants:
                font = load_font(fontfile)
                fn(font)
                save_font(font, static_dir / f"{stem}_{name}.ttf")

        # ── 2. Parametric sequences (for document interpolation) ───────────

        seq_dir = out_base / "sequences"

        print("\n  [sequences]")

        generate_sequence(
            fontfile, seq_dir / f"{stem}_jitter_seq",
            "jitter", lambda f, p: apply_jitter(f, int(p)),
            (0, 60), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_droop_seq",
            "droop", lambda f, p: apply_baseline_droop(f, p),
            (0.0, 1.0), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_collapse_seq",
            "collapse", lambda f, p: apply_stroke_collapse(f, p),
            (0.0, 0.85), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_dropout_seq",
            "dropout", lambda f, p: apply_point_dropout(f, p),
            (0.0, 0.5), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_wave_seq",
            "wave", lambda f, p: apply_wave(f, int(p), 2.0),
            (0, 120), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_shear_seq",
            "shear", lambda f, p: apply_shear(f, p),
            (0.0, 0.35), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_condense_seq",
            "condense", lambda f, p: apply_condense(f, p),
            (1.0, 0.40), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_quantize_seq",
            "quantize", lambda f, p: apply_quantize(f, max(1, int(p))),
            (2, 48), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_radial_seq",
            "radial", lambda f, p: apply_radial_distortion(f, p),
            (0.0, 1.2), steps
        )

        generate_sequence(
            fontfile, seq_dir / f"{stem}_asc_evap_seq",
            "asc_evap", lambda f, p: apply_ascender_evaporation(f, p),
            (0.0, 0.9), steps
        )

        # ── 3. Compound mutations (stacked transforms) ────────────────────

        compound_dir = out_base / "compound"
        print("\n  [compound]")

        # Full decay: jitter + droop + collapse combined at increasing intensity
        for i in range(steps):
            t = i / max(1, steps - 1)
            font = load_font(fontfile)
            apply_jitter(font, int(t * 40))
            apply_baseline_droop(font, t * 0.6)
            apply_stroke_collapse(font, t * 0.5)
            save_font(font, compound_dir / f"{stem}_full_decay_{i:03d}.ttf")

        # Dissolution: gaussian noise + point dropout
        for i in range(steps):
            t = i / max(1, steps - 1)
            font = load_font(fontfile)
            apply_gaussian_jitter(font, t * 30)
            apply_point_dropout(font, t * 0.35)
            save_font(font, compound_dir / f"{stem}_dissolution_{i:03d}.ttf")

        # Geological: shear + quantize + vertical squash
        for i in range(steps):
            t = i / max(1, steps - 1)
            font = load_font(fontfile)
            apply_shear(font, t * 0.20)
            apply_quantize(font, max(1, int(4 + t * 28)))
            apply_vertical_squash(font, 1.0 - t * 0.3)
            save_font(font, compound_dir / f"{stem}_geological_{i:03d}.ttf")

        # Wave erosion: wave + ascender evaporation + descender erosion
        for i in range(steps):
            t = i / max(1, steps - 1)
            font = load_font(fontfile)
            apply_wave(font, int(t * 80), 2.0)
            apply_ascender_evaporation(font, t * 0.7)
            apply_descender_erosion(font, t * 0.8)
            save_font(font, compound_dir / f"{stem}_wave_erosion_{i:03d}.ttf")

    print(f"\n\nAll done. Variants written to: {out_base}/")
    print("\nDirectory structure:")
    for d in sorted(out_base.rglob("*")):
        if d.is_dir():
            count = len(list(d.glob("*.ttf")))
            print(f"  {d}/  ({count} files)")


if __name__ == "__main__":
    main()
