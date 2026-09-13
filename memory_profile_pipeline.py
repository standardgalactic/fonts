"""
memory_profile_pipeline.py

Runs the actual render_word_image + ocr_read loop from
adversarial_ocr_core.py thousands of times in a single process (the same
pattern adversarial_ocr_experiment.py uses) and records RSS memory at
each iteration, to see empirically whether memory grows unboundedly
(a real leak worth fixing) or stays flat (no problem, no fix needed).

Cycles a handful of real fonts repeatedly rather than requiring
thousands of distinct font files - the leak risk under discussion is
about repeated FreeType/Pillow font loading and repeated Tesseract
subprocess calls, both of which happen identically whether the font
bytes differ or not.
"""

import gc
import json
import os
import sys
import time

import psutil

from adversarial_ocr_core import render_word_image, ocr_read, score_prediction

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]
WORDS = ["gravity", "horizon", "meteor", "cosmos", "wander", "orbit", "signal", "hollow"]


def run(n_iterations, sample_every=10, out_path="memory_trace.json"):
    proc = psutil.Process(os.getpid())
    trace = []
    t0 = time.time()

    fonts = [f for f in FONTS if os.path.exists(f)]
    if not fonts:
        print("No test fonts found on this system.", file=sys.stderr)
        return

    for i in range(n_iterations):
        font_path = fonts[i % len(fonts)]
        word = WORDS[i % len(WORDS)]

        img = render_word_image(font_path, word, font_size=48)
        predicted = ocr_read(img)
        score_prediction(word, predicted)

        if i % sample_every == 0 or i == n_iterations - 1:
            rss_mb = proc.memory_info().rss / (1024 * 1024)
            trace.append({"iteration": i, "rss_mb": round(rss_mb, 2), "elapsed_s": round(time.time() - t0, 2)})
            print("iter {:>5}  rss {:>8.2f} MB  ({:.1f}s elapsed)".format(i, rss_mb, time.time() - t0))

    with open(out_path, "w") as f:
        json.dump(trace, f, indent=2)

    # Simple trend check: compare mean RSS of the first 20% of samples
    # against the last 20%, ignoring the very first few samples where
    # one-time import/warm-up allocations inflate the baseline.
    warm = trace[2:] if len(trace) > 10 else trace
    n = len(warm)
    first_chunk = warm[: max(1, n // 5)]
    last_chunk = warm[-max(1, n // 5):]
    first_avg = sum(t["rss_mb"] for t in first_chunk) / len(first_chunk)
    last_avg = sum(t["rss_mb"] for t in last_chunk) / len(last_chunk)

    print()
    print("First-fifth average RSS: {:.2f} MB".format(first_avg))
    print("Last-fifth average RSS:  {:.2f} MB".format(last_avg))
    print("Growth: {:.2f} MB ({:+.1%})".format(last_avg - first_avg, (last_avg - first_avg) / first_avg))
    print()
    print("Wrote trace -> {}".format(out_path))

    return trace


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    run(n)
