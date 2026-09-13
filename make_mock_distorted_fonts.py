"""
make_mock_distorted_fonts.py

Builds a small mock font tree, mirroring the repo's real directory
conventions, using GENUINE glyph-outline transforms (via fontTools),
not pixel-level image tricks. This exists only to integration-test
adversarial_ocr_experiment.py end to end against something structurally
and mechanically like the user's real experiments/, experiments-v01/,
experiments-v02/ trees, since the actual perturbed .ttf files aren't
available in this environment.
"""

import os
import shutil
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

SRC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def transform_glyphs(font, matrix):
    """Apply an affine matrix (a, b, c, d, e, f) to every glyph outline
    in a TrueType (glyf-based) font, in place."""
    glyf_table = font["glyf"]
    glyph_set = font.getGlyphSet()

    for name in font.getGlyphOrder():
        glyph = glyf_table[name]
        if glyph.numberOfContours == 0:
            continue  # space, etc.
        rec = RecordingPen()
        glyph_set[name].draw(rec)

        pen = TTGlyphPen(glyphSet=None)
        a, b, c, d, e, f = matrix

        def tx(pt):
            x, y = pt
            return (a * x + c * y + e, b * x + d * y + f)

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


def build(dest_root):
    if os.path.exists(dest_root):
        shutil.rmtree(dest_root)

    # --- experiments/compound: a clean control + two genuinely distorted variants ---
    compound_dir = os.path.join(dest_root, "experiments", "compound")
    os.makedirs(compound_dir, exist_ok=True)

    # clean control (no transform)
    shutil.copy(SRC, os.path.join(compound_dir, "TestFont-Regular_clean_000.ttf"))

    # mild shear
    f = TTFont(SRC)
    transform_glyphs(f, (1, 0, 0.35, 1, 0, 0))  # horizontal shear
    f.save(os.path.join(compound_dir, "TestFont-Regular_shear_000.ttf"))

    # heavy vertical squash (this is the one expected to genuinely hurt OCR)
    f = TTFont(SRC)
    transform_glyphs(f, (1, 0, 0, 0.28, 0, 620))  # squash to ~28% height, reposition on baseline
    f.save(os.path.join(compound_dir, "TestFont-Regular_squash_000.ttf"))

    # --- experiments-v01: flat dir, no-underscore-before-number naming ---
    v01_dir = os.path.join(dest_root, "experiments-v01")
    os.makedirs(v01_dir, exist_ok=True)
    f = TTFont(SRC)
    transform_glyphs(f, (1, 0.25, 0, 1, 0, 0))  # skew
    f.save(os.path.join(v01_dir, "TestFont-Regular_skew10.ttf"))

    # --- experiments-v02/fields/melt: directory-encoded group ---
    melt_dir = os.path.join(dest_root, "experiments-v02", "fields", "melt")
    os.makedirs(melt_dir, exist_ok=True)
    f = TTFont(SRC)
    transform_glyphs(f, (1, 0, 0.1, 0.55, 0, 300))  # partial "melt" (squash + shear)
    f.save(os.path.join(melt_dir, "TestFont-Regular_melt_000.ttf"))

    print("Built mock font tree at", dest_root)


if __name__ == "__main__":
    build("./mock-fonts")
