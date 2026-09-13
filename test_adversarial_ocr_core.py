"""
test_adversarial_ocr_core.py

Sanity tests for adversarial_ocr_core.py, run against real fonts and a
real Tesseract install (not mocked) - the whole point of this pipeline is
whether an actual OCR engine gets fooled, so a mocked OCR call would prove
nothing. Run with: python3 test_adversarial_ocr_core.py
"""

import sys
from PIL import ImageFilter, ImageOps

from adversarial_ocr_core import (
    render_word_image, ocr_read, score_prediction, is_adversarial
)

CLEAN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def make_heavily_distorted(image):
    """
    Stand-in distortion for local testing only, since the real perturbed
    TTFs (jitter/shear/dropout/wave/etc.) live in the user's own repo and
    aren't available in this environment. This applies pixel-level noise
    and blur to a clean rendering, which is a different mechanism than
    glyph-level TTF distortion but serves the same purpose here: proving
    the OCR/scoring pipeline actually differentiates "readable" from
    "not readable" before it's pointed at the real font variants.
    """
    img = image.convert("L")
    img = img.filter(ImageFilter.GaussianBlur(radius=3.2))
    img = ImageOps.autocontrast(img)
    # Heavy salt noise
    import random
    px = img.load()
    w, h = img.size
    for _ in range(int(w * h * 0.12)):
        x = random.randrange(w)
        y = random.randrange(h)
        px[x, y] = random.choice([0, 255])
    return img.convert("RGB")


def test_clean_rendering_is_readable():
    img = render_word_image(CLEAN_FONT, "orbit", font_size=64)
    text = ocr_read(img)
    score = score_prediction("orbit", text)
    print("  clean 'orbit' -> OCR read: {!r}  score: {}".format(text, score))
    assert score["correct"], (
        "Sanity check failed: Tesseract could not read a clean, high-contrast "
        "rendering of a plain word in a normal font. Either Tesseract isn't "
        "installed correctly, or the rendering function has a bug - fix that "
        "before trusting any result from the distorted-font experiments."
    )
    print("  PASS: clean rendering is correctly read")


def test_heavy_distortion_measurably_hurts_ocr():
    words = ["gravity", "horizon", "meteor", "cosmos", "wander"]
    clean_correct = 0
    distorted_correct = 0

    for w in words:
        clean_img = render_word_image(CLEAN_FONT, w, font_size=64)
        clean_text = ocr_read(clean_img)
        clean_score = score_prediction(w, clean_text)
        clean_correct += int(clean_score["correct"])

        distorted_img = make_heavily_distorted(clean_img)
        distorted_text = ocr_read(distorted_img)
        distorted_score = score_prediction(w, distorted_text)
        distorted_correct += int(distorted_score["correct"])

        print("  {:>8}  clean={!r} (correct={})   distorted={!r} (correct={}, char_acc={})".format(
            w, clean_text, clean_score["correct"],
            distorted_text, distorted_score["correct"], distorted_score["char_accuracy"]
        ))

    print("  clean correct: {}/{}   distorted correct: {}/{}".format(
        clean_correct, len(words), distorted_correct, len(words)
    ))

    assert clean_correct >= distorted_correct, (
        "Distortion should not improve OCR accuracy relative to clean text. "
        "If this fails, the scoring or rendering pipeline has a bug."
    )
    assert clean_correct > distorted_correct, (
        "Expected heavy distortion to measurably hurt OCR accuracy on at "
        "least one word - if clean and distorted scored identically, the "
        "distortion function likely isn't distorting enough to be a "
        "meaningful test of the pipeline's ability to differentiate."
    )
    print("  PASS: heavy distortion measurably reduces OCR accuracy")


def test_is_adversarial_flag_logic():
    # A total misread (low char accuracy) should count as adversarial.
    total_miss = score_prediction("gravity", "xzq")
    assert is_adversarial(total_miss), "Near-total misread should be flagged adversarial"

    # A one-character slip (high char accuracy) should NOT count as
    # adversarial - that's ordinary OCR noise, not the font defeating it.
    near_miss = score_prediction("gravity", "gravitv")
    assert not is_adversarial(near_miss), "A one-character slip should not count as adversarial"

    # An exact match is obviously not adversarial.
    exact = score_prediction("gravity", "gravity")
    assert not is_adversarial(exact)

    print("  PASS: is_adversarial distinguishes near-misses from real failures")


if __name__ == "__main__":
    print("test_clean_rendering_is_readable")
    test_clean_rendering_is_readable()
    print()
    print("test_heavy_distortion_measurably_hurts_ocr")
    test_heavy_distortion_measurably_hurts_ocr()
    print()
    print("test_is_adversarial_flag_logic")
    test_is_adversarial_flag_logic()
    print()
    print("All tests passed.")
