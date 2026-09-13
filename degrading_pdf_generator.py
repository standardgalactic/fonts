#!/usr/bin/env python3
"""
degrading_pdf_generator.py

Generates a PDF where the body font starts clean and degrades page by
page according to a chosen curve, ending unreadable (or near it) by the
last page. Produces:

  <out>/degrading.pdf              - the document itself
  <out>/manifest.json              - per-page {text, intensity, curve
                                      position, font variant used} -
                                      the ground-truth labels a training
                                      pipeline actually needs
  <out>/page_fonts/                - the generated font variant for
                                      each page (kept, not temporary -
                                      useful on their own for other
                                      experiments)
  <out>/validation.json            - OCR run against a rasterized copy
                                      of every page, proving the curve
                                      actually produced a readable-to-
                                      unreadable progression rather than
                                      asserting it

Usage:
    python3 degrading_pdf_generator.py --font /path/to/Base-Regular.ttf \\
        --text-file mycorpus.txt --pages 10 --curve ease_in --out ./out

Text handling: --text-file should contain one paragraph per line (blank
lines are skipped). If omitted, a small built-in placeholder corpus is
used - fine for testing the pipeline, but real training data should
point this at real prose, since coherent language interacts with how
language-model-assisted OCR fails in ways generic filler text won't
represent.
"""

import argparse
import json
import os
import subprocess
import sys

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLFont

from degradation_curve import intensity_for_position, positions_for_n_pages, CURVES
from glyph_transform import degrade_font
from adversarial_ocr_core import ocr_read, score_prediction

PLACEHOLDER_PARAGRAPHS = [
    "The signal arrived on schedule, faint but unmistakable, and the crew began the long work of confirming what they already suspected.",
    "Every measurement agreed with the last, which was itself the first sign that something had been overlooked.",
    "Records from the earlier expedition described the same drift, though nobody at the time had thought to name it.",
    "A pattern this consistent does not arise by accident, the technician said, though she could not yet say what had caused it.",
    "By the third week, the anomaly had stopped being an anomaly and started being simply how things worked here.",
    "The archive held thousands of similar reports, each one a small, careful account of something nobody had fully explained.",
    "Nothing about the terrain suggested instability, and yet the readings continued to shift by the same small margin.",
    "It was easier, in the end, to adjust the instruments than to admit the instruments had been right all along.",
    "The final report noted the discrepancy without resolving it, which was itself a kind of honesty.",
    "Whatever had caused the drift was still there, unbothered, when the next team arrived to measure it again.",
]


def load_paragraphs(text_file, n_pages):
    if text_file:
        with open(text_file, encoding="utf-8") as f:
            paragraphs = [line.strip() for line in f if line.strip()]
        if not paragraphs:
            raise ValueError("--text-file was empty after stripping blank lines")
    else:
        paragraphs = PLACEHOLDER_PARAGRAPHS

    # Cycle the corpus if there are more pages than paragraphs, rather
    # than erroring - repeated text is still valid for testing whether a
    # given intensity is readable, even if a real training corpus should
    # normally supply enough unique text to cover all pages.
    return [paragraphs[i % len(paragraphs)] for i in range(n_pages)]


def wrap_text(text, font_name, font_size, max_width, canvas_obj):
    """Greedy word-wrap using reportlab's actual string-width metrics for
    the specific (possibly degraded) font, so wrapping is correct even
    though each page's font has different glyph geometry."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if canvas_obj.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_pdf(font_variants, paragraphs, out_pdf_path, font_size=18, page_size=LETTER):
    """font_variants: list of (font_name_for_reportlab, ttf_path) pairs,
    one per page, already registered with pdfmetrics by the caller."""
    c = canvas.Canvas(out_pdf_path, pagesize=page_size)
    width, height = page_size
    margin = 72
    max_width = width - 2 * margin
    line_height = font_size * 1.4

    for (font_name, _), text in zip(font_variants, paragraphs):
        c.setFont(font_name, font_size)
        lines = wrap_text(text, font_name, font_size, max_width, c)
        y = height - margin
        for line in lines:
            c.drawString(margin, y, line)
            y -= line_height
        c.showPage()

    c.save()


def rasterize_pdf(pdf_path, out_dir, dpi=150):
    """Render each PDF page to a PNG via pdftoppm (poppler), returning
    the sorted list of produced image paths."""
    prefix = os.path.join(out_dir, "page")
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix],
        check=True, capture_output=True
    )
    pages = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.startswith("page") and f.endswith(".png")
    )
    return pages


def validate_pages(page_images, ground_truth_texts):
    """OCR each rasterized page and score against its ground-truth
    paragraph. Uses the same score_prediction machinery as the
    adversarial-OCR experiment, applied here at the paragraph level
    rather than the single-word level."""
    from PIL import Image
    results = []
    for img_path, text in zip(page_images, ground_truth_texts):
        img = Image.open(img_path)
        predicted = ocr_read(img, psm=6)  # psm=6: uniform block of text
        score = score_prediction(text, predicted)
        results.append({
            "page_image": os.path.basename(img_path),
            "ground_truth": text,
            "predicted": predicted,
            "char_accuracy": score["char_accuracy"],
        })
    return results


def run(font_path, out_dir, n_pages=10, curve_name="ease_in", text_file=None,
        font_size=18, seed=0, dpi=150, curve_kwargs=None, validate=True):
    curve_kwargs = curve_kwargs or {}
    os.makedirs(out_dir, exist_ok=True)
    font_dir = os.path.join(out_dir, "page_fonts")
    os.makedirs(font_dir, exist_ok=True)

    positions = positions_for_n_pages(n_pages)
    paragraphs = load_paragraphs(text_file, n_pages)

    manifest = []
    font_variants = []

    for i, position in enumerate(positions):
        intensity = intensity_for_position(position, curve_name, **curve_kwargs)
        variant_path = os.path.join(font_dir, "page_{:03d}_intensity_{:.3f}.ttf".format(i, intensity))
        params = degrade_font(font_path, intensity, variant_path, seed=seed)

        font_name = "PageFont{:03d}".format(i)
        pdfmetrics.registerFont(RLFont(font_name, variant_path))
        font_variants.append((font_name, variant_path))

        manifest.append({
            "page": i + 1,
            "position": round(position, 4),
            "curve": curve_name,
            "intensity": round(intensity, 4),
            "transform_params": params,
            "font_variant": os.path.relpath(variant_path, out_dir),
            "text": paragraphs[i],
        })

    pdf_path = os.path.join(out_dir, "degrading.pdf")
    build_pdf(font_variants, paragraphs, pdf_path, font_size=font_size)

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print("Wrote {} ({} pages) -> {}".format(os.path.basename(pdf_path), n_pages, pdf_path))
    print("Wrote manifest -> {}".format(os.path.join(out_dir, "manifest.json")))

    if validate:
        raster_dir = os.path.join(out_dir, "rasterized")
        os.makedirs(raster_dir, exist_ok=True)
        page_images = rasterize_pdf(pdf_path, raster_dir, dpi=dpi)
        results = validate_pages(page_images, paragraphs)

        with open(os.path.join(out_dir, "validation.json"), "w") as f:
            json.dump(results, f, indent=2)

        print()
        print("Validation (OCR char-accuracy per page):")
        for r, m in zip(results, manifest):
            bar_len = int(r["char_accuracy"] * 30)
            bar = "#" * bar_len + "-" * (30 - bar_len)
            print("  page {:>3}  intensity {:.3f}  [{}] {:.3f}".format(
                m["page"], m["intensity"], bar, r["char_accuracy"]
            ))
        print()
        print("Wrote validation -> {}".format(os.path.join(out_dir, "validation.json")))

    return manifest


def main():
    ap = argparse.ArgumentParser(description="Generate a PDF whose font degrades page by page.")
    ap.add_argument("--font", required=True, help="Path to the source .ttf to degrade")
    ap.add_argument("--out", default="./degrading-out", help="Output directory")
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--curve", default="ease_in", choices=sorted(CURVES.keys()))
    ap.add_argument("--text-file", default=None, help="One paragraph per line; defaults to a small built-in corpus")
    ap.add_argument("--font-size", type=int, default=18)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--no-validate", action="store_true", help="Skip the OCR self-check pass")
    args = ap.parse_args()

    run(
        font_path=args.font,
        out_dir=args.out,
        n_pages=args.pages,
        curve_name=args.curve,
        text_file=args.text_file,
        font_size=args.font_size,
        seed=args.seed,
        dpi=args.dpi,
        validate=not args.no_validate,
    )


if __name__ == "__main__":
    main()
