"""
adversarial_ocr_core.py

Pure, testable core for the adversarial-OCR-example pipeline: render a word
in a given font, run it through a real OCR engine, and score whether the
font's distortion successfully fooled recognition.

This module deliberately contains no CLI or batch-orchestration logic -
that lives in adversarial_ocr_experiment.py, which imports this module.
Keeping the two separate means the scoring/rendering logic can be unit
tested (see test_adversarial_ocr_core.py) without needing a real font
directory or a real Tesseract install wired up in the test itself, beyond
what's needed to prove the pipeline actually works end to end.
"""

import difflib
import io

from PIL import Image, ImageDraw, ImageFont
import pytesseract


def render_word_image(font_path, word, font_size=64, padding=24,
                       fg=(20, 20, 20), bg=(255, 255, 255)):
    """
    Render `word` in the font at `font_path` onto a plain background,
    sized to fit with `padding` on all sides. Returns a PIL Image.

    A plain, high-contrast background is deliberate: this isolates the
    font's own glyph distortion as the thing being tested for OCR
    robustness, rather than confounding it with a second, independent
    perturbation (background noise, low contrast, rotation of the whole
    image). Those are legitimate adversarial dimensions too, but they
    belong in a separate experiment so the results here can be
    attributed cleanly to the font itself.
    """
    font = ImageFont.truetype(font_path, font_size)

    # Measure first on a scratch image, then render on a correctly sized one.
    scratch = Image.new("RGB", (10, 10), bg)
    draw = ImageDraw.Draw(scratch)
    bbox = draw.textbbox((0, 0), word, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    img = Image.new("RGB", (text_w + padding * 2, text_h + padding * 2), bg)
    draw = ImageDraw.Draw(img)
    draw.text((padding - bbox[0], padding - bbox[1]), word, font=font, fill=fg)
    return img


def ocr_read(image, psm=7):
    """
    Run Tesseract on `image` and return the recognized text, stripped and
    lowercased. psm=7 ("treat the image as a single text line") matches
    the single-word rendering this pipeline produces.
    """
    config = "--psm {}".format(psm)
    text = pytesseract.image_to_string(image, config=config)
    return text.strip().lower()


def score_prediction(ground_truth, predicted):
    """
    Compare OCR output to the ground-truth word. Returns a dict with:
      - correct: exact match (case-insensitive, already lowercased upstream)
      - edit_distance: Levenshtein-style distance via difflib's opcodes
      - char_accuracy: 1 - (edit_distance / max(len(gt), 1)), clamped to [0, 1]

    char_accuracy matters alongside the boolean: a font that reliably
    gets OCR "close but wrong" (one character off) is a meaningfully
    different failure mode from one that produces total garbage, and a
    training-data curation pass would likely want to treat those
    differently (near-misses make good hard negatives; total garbage
    may just indicate the font broke rendering entirely).
    """
    gt = ground_truth.lower().strip()
    pred = predicted.lower().strip()

    sm = difflib.SequenceMatcher(None, gt, pred)
    ops = sm.get_opcodes()
    edits = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in ops if tag != "equal")

    denom = max(len(gt), 1)
    char_accuracy = max(0.0, 1.0 - edits / denom)

    return {
        "correct": gt == pred,
        "edit_distance": edits,
        "char_accuracy": round(char_accuracy, 4),
    }


def is_adversarial(score, char_accuracy_threshold=0.5):
    """
    A rendering counts as a successful adversarial example when OCR
    didn't just make a small mistake but substantially failed to read
    it - i.e. char_accuracy below threshold. Exact-match failures with
    high char_accuracy (one letter off) are recorded but not counted as
    "the font defeated OCR"; they're closer to ordinary OCR noise and
    would be misleading to report as adversarial successes.
    """
    return (not score["correct"]) and (score["char_accuracy"] < char_accuracy_threshold)
