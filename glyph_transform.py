"""
glyph_transform.py

Applies a combined jitter + shear + vertical-squash distortion to every
glyph outline in a TrueType (glyf-based) font, scaled by a single
`intensity` parameter in [0, 1]. This is the mechanism the degrading-PDF
generator uses to produce one font variant per page: intensity 0.0 is
the untouched source font, intensity 1.0 is maximally distorted.

Reuses the same pen-recording/replay approach validated in the
adversarial-OCR experiment's mock font generator, generalized to take
a continuous intensity rather than a fixed hand-picked matrix per call,
and adding reproducible per-point jitter (a fixed seed derived from the
glyph name + intensity, so results are deterministic across runs).
"""

import random
import os

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


def _params_for_intensity(intensity, max_shear=0.55, min_scale=0.22, max_jitter_units=140):
    """
    Maps a single intensity in [0, 1] to the three underlying distortion
    parameters. Jitter grows fastest at the end (squared) since a small
    jitter is barely noticeable but a large one is what actually breaks
    glyph legibility - so error should be back-loaded like the intensity
    curve itself typically is.
    """
    intensity = max(0.0, min(1.0, intensity))
    shear = intensity * max_shear
    scale_y = 1.0 - intensity * (1.0 - min_scale)
    jitter = (intensity ** 1.5) * max_jitter_units
    return shear, scale_y, jitter


def _make_unique_name(font, unique_id):
    """
    Rewrite the font's internal name-table records (family, full name,
    PostScript name) so this variant is never mistaken for another one
    derived from the same source. This matters beyond cosmetics: tools
    that embed/subset fonts (reportlab among them) can cache or key
    embedded font data by the font's own declared PostScript name rather
    than by file path, which silently collapses multiple same-named
    variants into whichever one was embedded first - exactly the
    failure mode this function exists to prevent.
    """
    name_table = font["name"]
    safe_id = "".join(ch if ch.isalnum() else "-" for ch in str(unique_id))
    new_family = "Degraded-{}".format(safe_id)
    new_ps_name = "Degraded-{}".format(safe_id)  # PostScript names should avoid spaces

    for record in name_table.names:
        if record.nameID in (1, 4, 16):   # family, full name, preferred family
            record.string = new_family.encode(record.getEncoding()) if isinstance(new_family, str) else new_family
        elif record.nameID in (6,):        # PostScript name
            record.string = new_ps_name.encode(record.getEncoding()) if isinstance(new_ps_name, str) else new_ps_name

    # Rewrite via setName so encoding/platform variants are handled
    # consistently rather than only patching whichever records already existed.
    name_table.setName(new_family, 1, 3, 1, 0x409)
    name_table.setName(new_family, 4, 3, 1, 0x409)
    name_table.setName(new_ps_name, 6, 3, 1, 0x409)
    name_table.setName(new_family, 16, 3, 1, 0x409)


def degrade_font(src_path, intensity, out_path, seed=0,
                  max_shear=0.55, min_scale=0.22, max_jitter_units=140):
    """
    Write a degraded copy of the font at src_path to out_path, with
    distortion scaled by `intensity` (0 = untouched copy, 1 = maximal).
    Deterministic for a given (src_path, intensity, seed): outline
    coordinates are exactly reproduced across runs.

    The output font's internal name-table records are rewritten to a
    name unique to (src_path, intensity, seed) - see _make_unique_name.
    Without this, every variant derived from the same source font
    silently shares its internal PostScript name, which causes some
    downstream tools (notably reportlab's font embedding) to treat all
    variants as literally the same font and reuse cached glyph data
    from whichever was embedded first - so, for example, a document's
    later "more degraded" pages would silently render with the first
    page's glyphs instead. This was caught by end-to-end testing
    against a real PDF, not anticipated in advance.

    Note: because this rebuilds every glyph via a pen-recording/replay
    round trip, TrueType hinting instructions are not preserved even at
    intensity=0. This has a small (cosmetically negligible) effect on
    anti-aliasing at small sizes but does not affect the outline
    geometry or OCR readability - a font degraded at intensity=0.0 is
    still exactly as recognizable as the source.
    """
    shear, scale_y, jitter = _params_for_intensity(
        intensity, max_shear=max_shear, min_scale=min_scale, max_jitter_units=max_jitter_units
    )

    font = TTFont(src_path)
    glyf_table = font["glyf"]
    glyph_set = font.getGlyphSet()

    for name in font.getGlyphOrder():
        glyph = glyf_table[name]
        if glyph.numberOfContours <= 0:
            continue  # space and other outline-less glyphs

        rec = RecordingPen()
        glyph_set[name].draw(rec)

        # Deterministic per-glyph RNG: same seed + intensity always
        # produces the same jitter for a given glyph, but different
        # glyphs don't all jitter identically in lockstep.
        rng = random.Random("{}:{}:{}".format(seed, name, round(intensity, 6)))

        def tx(pt):
            x, y = pt
            # shear + vertical squash (squash re-centered so text stays
            # roughly on the baseline rather than collapsing toward y=0)
            sx = x + shear * y
            sy = y * scale_y + (1 - scale_y) * 250  # ~x-height-ish anchor
            if jitter > 0:
                sx += rng.uniform(-jitter, jitter)
                sy += rng.uniform(-jitter, jitter)
            return (sx, sy)

        pen = TTGlyphPen(glyphSet=None)
        for op, args in rec.value:
            if op == "moveTo":
                pen.moveTo(tx(args[0]))
            elif op == "lineTo":
                pen.lineTo(tx(args[0]))
            elif op == "curveTo":
                pen.curveTo(*[tx(p) for p in args])
            elif op == "qCurveTo":
                pen.qCurveTo(*[tx(p) if p is not None else None for p in args])
            elif op == "closePath":
                pen.closePath()
            elif op == "endPath":
                pen.endPath()

        glyf_table[name] = pen.glyph()

    _make_unique_name(font, "{}-{:.6f}-{}".format(seed, intensity, os.path.basename(out_path)))
    font.save(out_path)
    return {"shear": shear, "scale_y": scale_y, "jitter": jitter}