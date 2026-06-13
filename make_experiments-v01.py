#!/usr/bin/env python3

import os
import random
from pathlib import Path

from fontTools.ttLib import TTFont

OUTDIR = Path("experiments")
OUTDIR.mkdir(exist_ok=True)

VARIANTS = [
    ("jitter10", 10),
    ("jitter20", 20),
    ("jitter40", 40),
    ("jitter80", 80),
]

random.seed(42)

def mutate_font(source_path, output_path, strength):
    font = TTFont(source_path)

    if "glyf" not in font:
        print(f"Skipping {source_path} (no glyf table)")
        return

    glyf = font["glyf"]

    for glyph_name in glyf.keys():

        glyph = glyf[glyph_name]

        if glyph.isComposite():
            continue

        if glyph.numberOfContours <= 0:
            continue

        try:
            coords = glyph.coordinates

            for i in range(len(coords)):
                x, y = coords[i]

                dx = random.randint(-strength, strength)
                dy = random.randint(-strength, strength)

                coords[i] = (x + dx, y + dy)

        except Exception:
            pass

    font.save(output_path)


def condense_font(source_path, output_path, factor):
    font = TTFont(source_path)

    if "glyf" not in font:
        return

    glyf = font["glyf"]

    for glyph_name in glyf.keys():

        glyph = glyf[glyph_name]

        if glyph.isComposite():
            continue

        if glyph.numberOfContours <= 0:
            continue

        try:
            coords = glyph.coordinates

            for i in range(len(coords)):
                x, y = coords[i]
                coords[i] = (int(x * factor), y)

        except Exception:
            pass

    font.save(output_path)


def shear_font(source_path, output_path, shear):
    font = TTFont(source_path)

    if "glyf" not in font:
        return

    glyf = font["glyf"]

    for glyph_name in glyf.keys():

        glyph = glyf[glyph_name]

        if glyph.isComposite():
            continue

        if glyph.numberOfContours <= 0:
            continue

        try:
            coords = glyph.coordinates

            for i in range(len(coords)):
                x, y = coords[i]
                coords[i] = (
                    int(x + shear * y),
                    y
                )

        except Exception:
            pass

    font.save(output_path)


fonts = sorted(Path(".").glob("*.ttf"))

for fontfile in fonts:

    stem = fontfile.stem

    print(f"Processing {fontfile}")

    for name, strength in VARIANTS:

        mutate_font(
            fontfile,
            OUTDIR / f"{stem}_{name}.ttf",
            strength
        )

    condense_font(
        fontfile,
        OUTDIR / f"{stem}_condense70.ttf",
        0.70
    )

    condense_font(
        fontfile,
        OUTDIR / f"{stem}_expand130.ttf",
        1.30
    )

    shear_font(
        fontfile,
        OUTDIR / f"{stem}_shear10.ttf",
        0.10
    )

    shear_font(
        fontfile,
        OUTDIR / f"{stem}_shear20.ttf",
        0.20
    )

print("Done.")
