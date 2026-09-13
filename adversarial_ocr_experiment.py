#!/usr/bin/env python3
"""
adversarial_ocr_experiment.py

Batch pipeline: for every font file under --fonts-dir, render every word
in the word list, run it through Tesseract, and record whether the font's
distortion fooled OCR. Outputs:

  <out>/adversarial-index.json   - one record per (font, word) rendering
  <out>/adversarial-summary.json - fooling-rate aggregated by transform
                                    group and by base font
  <out>/hard-negatives/          - the rendered PNGs where OCR failed
                                    substantially (the actual usable
                                    adversarial training examples: image
                                    + correct label, ready to fold into a
                                    fine-tuning set for a more robust OCR
                                    model)

Usage:
    python3 adversarial_ocr_experiment.py --fonts-dir /path/to/repo \\
        --pattern "experiments*/**/*.ttf" --out ./adversarial-out

Run test_adversarial_ocr_core.py and test_font_path_parser.py first if
you haven't - this script assumes both are already known-good, and
doesn't re-validate the OCR pipeline or the path parser itself.
"""

import argparse
import json
import os
import sys
import time

from adversarial_ocr_core import render_word_image, ocr_read, score_prediction, is_adversarial
from font_path_parser import parse_font_path

DEFAULT_WORDS = [
    "orbit", "comet", "nova", "pulse", "vertex", "meteor", "cosmos", "ember",
    "quasar", "tundra", "umbra", "gravity", "horizon", "rocket", "solar",
    "wander", "zenith", "lumen", "dagger", "jester", "karma", "yonder",
    "flux", "ion", "glyph", "cipher", "galactic", "signal", "drift",
    "hollow", "static", "echo",
]


def discover_fonts(fonts_dir, patterns):
    """Yield (abs_path, rel_path) for every .ttf under fonts_dir matching
    any of the glob patterns. rel_path uses forward slashes regardless of
    OS, since that's what the path parser and the JSON output expect."""
    import glob
    seen = set()
    for pattern in patterns:
        for abs_path in glob.glob(os.path.join(fonts_dir, pattern), recursive=True):
            if not abs_path.lower().endswith(".ttf"):
                continue
            if abs_path in seen:
                continue
            seen.add(abs_path)
            rel_path = os.path.relpath(abs_path, fonts_dir).replace(os.sep, "/")
            yield abs_path, rel_path


def run_experiment(fonts_dir, patterns, words, out_dir, font_size, char_acc_threshold,
                    limit_fonts=None, save_hard_negatives=True, verbose=True):
    os.makedirs(out_dir, exist_ok=True)
    hard_neg_dir = os.path.join(out_dir, "hard-negatives")
    if save_hard_negatives:
        os.makedirs(hard_neg_dir, exist_ok=True)

    fonts = list(discover_fonts(fonts_dir, patterns))
    if limit_fonts:
        fonts = fonts[:limit_fonts]

    if not fonts:
        print("No .ttf files matched under {} with patterns {}".format(fonts_dir, patterns),
              file=sys.stderr)
        return None

    records = []
    t0 = time.time()

    for fi, (abs_path, rel_path) in enumerate(fonts):
        parsed = parse_font_path(rel_path)

        for word in words:
            try:
                img = render_word_image(abs_path, word, font_size=font_size)
                predicted = ocr_read(img)
            except Exception as e:
                # A font that can't render or crashes the OCR call is
                # itself a data point (a font so distorted it can't even
                # be tested) - recorded, not silently skipped.
                records.append({
                    "font_path": rel_path,
                    "base_font": parsed["base_font"],
                    "group": parsed["group"],
                    "word": word,
                    "predicted": None,
                    "error": str(e),
                    "correct": False,
                    "edit_distance": None,
                    "char_accuracy": 0.0,
                    "adversarial": True,
                })
                continue

            score = score_prediction(word, predicted)
            adversarial = is_adversarial(score, char_acc_threshold)

            record = {
                "font_path": rel_path,
                "base_font": parsed["base_font"],
                "group": parsed["group"],
                "word": word,
                "predicted": predicted,
                "correct": score["correct"],
                "edit_distance": score["edit_distance"],
                "char_accuracy": score["char_accuracy"],
                "adversarial": adversarial,
            }
            records.append(record)

            if adversarial and save_hard_negatives:
                safe_stem = "{}__{}".format(parsed["stem"], word)
                img_path = os.path.join(hard_neg_dir, safe_stem + ".png")
                img.save(img_path)
                record["hard_negative_image"] = os.path.relpath(img_path, out_dir)

        if verbose and (fi + 1) % max(1, len(fonts) // 20 or 1) == 0:
            elapsed = time.time() - t0
            print("  {}/{} fonts processed ({:.0f}s elapsed)".format(fi + 1, len(fonts), elapsed))

    index_path = os.path.join(out_dir, "adversarial-index.json")
    with open(index_path, "w") as f:
        json.dump(records, f, indent=2)

    summary = summarize(records)
    summary_path = os.path.join(out_dir, "adversarial-summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    if verbose:
        print()
        print("Wrote {} records -> {}".format(len(records), index_path))
        print("Wrote summary -> {}".format(summary_path))
        print_summary_table(summary)

    return {"records": records, "summary": summary}


def summarize(records):
    """Aggregate fooling rate (fraction of renderings that counted as
    adversarial) by transform group and separately by base font, plus an
    overall total. A higher fooling rate means that group/font more
    reliably defeats OCR - i.e. is a stronger source of adversarial
    examples for training data."""
    def agg(key_fn):
        buckets = {}
        for r in records:
            k = key_fn(r)
            b = buckets.setdefault(k, {"n": 0, "adversarial": 0, "mean_char_accuracy": 0.0})
            b["n"] += 1
            b["adversarial"] += int(r["adversarial"])
            b["mean_char_accuracy"] += r["char_accuracy"]
        for b in buckets.values():
            b["fooling_rate"] = round(b["adversarial"] / b["n"], 4) if b["n"] else 0.0
            b["mean_char_accuracy"] = round(b["mean_char_accuracy"] / b["n"], 4) if b["n"] else 0.0
        return buckets

    by_group = agg(lambda r: r["group"])
    by_base_font = agg(lambda r: r["base_font"])

    total_n = len(records)
    total_adv = sum(int(r["adversarial"]) for r in records)

    return {
        "total_renderings": total_n,
        "total_adversarial": total_adv,
        "overall_fooling_rate": round(total_adv / total_n, 4) if total_n else 0.0,
        "by_group": dict(sorted(by_group.items(), key=lambda kv: -kv[1]["fooling_rate"])),
        "by_base_font": dict(sorted(by_base_font.items(), key=lambda kv: -kv[1]["fooling_rate"])),
    }


def print_summary_table(summary):
    print()
    print("Overall fooling rate: {:.1%}  ({}/{} renderings)".format(
        summary["overall_fooling_rate"], summary["total_adversarial"], summary["total_renderings"]
    ))
    print()
    print("By transform group (highest fooling rate first):")
    print("  {:<28} {:>6}  {:>10}  {:>10}".format("group", "n", "fooling%", "char_acc"))
    for group, stats in summary["by_group"].items():
        print("  {:<28} {:>6}  {:>9.1%}  {:>10.3f}".format(
            group, stats["n"], stats["fooling_rate"], stats["mean_char_accuracy"]
        ))


def main():
    ap = argparse.ArgumentParser(description="Generate OCR-adversarial examples from a font directory.")
    ap.add_argument("--fonts-dir", required=True, help="Root directory to scan for .ttf files")
    ap.add_argument("--pattern", action="append", default=None,
                     help="Glob pattern(s) relative to --fonts-dir (repeatable). "
                          "Default covers experiments/, experiments-v01/, experiments-v02/.")
    ap.add_argument("--words-file", default=None,
                     help="Optional text file, one word per line. Defaults to a built-in word list.")
    ap.add_argument("--out", default="./adversarial-out", help="Output directory")
    ap.add_argument("--font-size", type=int, default=64)
    ap.add_argument("--char-acc-threshold", type=float, default=0.5,
                     help="Below this char_accuracy, a misread counts as adversarial (default 0.5)")
    ap.add_argument("--limit-fonts", type=int, default=None, help="For a quick test run")
    ap.add_argument("--no-hard-negatives", action="store_true", help="Skip saving PNGs of failures")
    args = ap.parse_args()

    patterns = args.pattern or [
        "experiments/**/*.ttf",
        "experiments-v01/**/*.ttf",
        "experiments-v02/**/*.ttf",
    ]

    if args.words_file:
        with open(args.words_file) as f:
            words = [w.strip().lower() for w in f if w.strip()]
    else:
        words = DEFAULT_WORDS

    run_experiment(
        fonts_dir=args.fonts_dir,
        patterns=patterns,
        words=words,
        out_dir=args.out,
        font_size=args.font_size,
        char_acc_threshold=args.char_acc_threshold,
        limit_fonts=args.limit_fonts,
        save_hard_negatives=not args.no_hard_negatives,
    )


if __name__ == "__main__":
    main()
