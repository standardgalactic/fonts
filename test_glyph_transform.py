import os
import shutil
import filecmp

from glyph_transform import degrade_font
from adversarial_ocr_core import render_word_image, ocr_read, score_prediction

SRC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TMP = "./_transform_test_tmp"

if os.path.exists(TMP):
    shutil.rmtree(TMP)
os.makedirs(TMP)

failures = 0
def check(cond, msg):
    global failures
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures += 1


# --- determinism: same intensity+seed twice -> identical glyph outlines.
# (Not byte-identical files: fontTools stamps a save timestamp in the
# 'head' table on every save, which differs run to run and is cosmetic -
# what actually matters is that the outline coordinates themselves,
# which are what gets rendered, are exactly reproduced.) ---
out_a = os.path.join(TMP, "a.ttf")
out_b = os.path.join(TMP, "b.ttf")
degrade_font(SRC, 0.6, out_a, seed=42)
degrade_font(SRC, 0.6, out_b, seed=42)

from fontTools.ttLib import TTFont as _TTFont
font_a = _TTFont(out_a)
font_b = _TTFont(out_b)
outlines_match = all(
    list(font_a["glyf"][name].coordinates) == list(font_b["glyf"][name].coordinates)
    for name in font_a.getGlyphOrder()
    if font_a["glyf"][name].numberOfContours > 0
)
check(outlines_match, "same intensity+seed produces identical glyph outline coordinates")

# --- different seeds at the same intensity should generally differ ---
out_c = os.path.join(TMP, "c.ttf")
degrade_font(SRC, 0.6, out_c, seed=99)
check(not filecmp.cmp(out_a, out_c, shallow=False), "different seeds at same intensity produce different output")

# --- intensity 0 should render very close to the untouched source.
# Not pixel-exact: recreating glyphs via RecordingPen -> TTGlyphPen drops
# TrueType hinting instructions, which shifts anti-aliasing at the pixel
# level even when the outline coordinates are geometrically identical.
# The invariant that actually matters is that this is cosmetically
# negligible, not that OCR or a viewer could ever notice - checked via
# mean pixel difference rather than exact equality. ---
import numpy as np
from PIL import ImageChops

clean_path = os.path.join(TMP, "clean.ttf")
degrade_font(SRC, 0.0, clean_path, seed=1)
img_src = render_word_image(SRC, "gravity", font_size=64)
img_zero = render_word_image(clean_path, "gravity", font_size=64)
diff = np.array(ImageChops.difference(img_src.convert("L"), img_zero.convert("L")))
check(diff.mean() < 5.0,
      "intensity=0.0 renders nearly identical to the untouched source (mean pixel diff {:.3f}/255, "
      "small difference expected from hinting loss during pen reconstruction)".format(diff.mean()))

# --- genuine OCR-measured degradation across the intensity range ---
words = ["gravity", "horizon", "meteor", "cosmos", "wander", "orbit", "signal", "hollow"]
intensities = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
accuracy_by_intensity = []

for intensity in intensities:
    font_path = os.path.join(TMP, "deg_{:.1f}.ttf".format(intensity))
    degrade_font(SRC, intensity, font_path, seed=7)
    correct = 0
    for w in words:
        img = render_word_image(font_path, w, font_size=64)
        predicted = ocr_read(img)
        score = score_prediction(w, predicted)
        correct += int(score["correct"])
    accuracy = correct / len(words)
    accuracy_by_intensity.append(accuracy)
    print("  intensity={:.1f}  OCR accuracy={}/{}".format(intensity, correct, len(words)))

check(accuracy_by_intensity[0] >= 0.75,
      "intensity 0.0 should be highly readable (got {})".format(accuracy_by_intensity[0]))
check(accuracy_by_intensity[-1] <= 0.25,
      "intensity 1.0 should be nearly unreadable (got {})".format(accuracy_by_intensity[-1]))
check(accuracy_by_intensity[0] > accuracy_by_intensity[-1],
      "accuracy at intensity 0 should exceed accuracy at intensity 1")

# Overall trend should be generally downward (allow minor local
# non-monotonicity from OCR noise, but the broad direction must hold).
first_half_avg = sum(accuracy_by_intensity[:3]) / 3
second_half_avg = sum(accuracy_by_intensity[3:]) / 3
check(first_half_avg > second_half_avg,
      "average accuracy in the first half of the range should exceed the second half ({} > {})".format(
          first_half_avg, second_half_avg))

print()
if failures:
    print("{} FAILURES".format(failures))
    raise SystemExit(1)
print("All glyph_transform tests passed.")
