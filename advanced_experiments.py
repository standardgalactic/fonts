"""Second-generation transformations with distinct geometric hypotheses."""

import math
import random

from make_experiments import iter_simple_glyphs


def apply_perspective(font, strength):
    """Expand the top and contract the bottom around each glyph centre."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs, ys = zip(*coords)
        cx, bottom = (min(xs) + max(xs)) / 2, min(ys)
        height = max(1, max(ys) - bottom)
        for i, (x, y) in enumerate(coords):
            scale = 1 + strength * (((y - bottom) / height) - 0.5)
            coords[i] = (int(cx + (x - cx) * scale), y)


def apply_envelope(font, strength):
    """Inflate the middle third of each glyph without moving its extremes."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs, ys = zip(*coords)
        cx, bottom = (min(xs) + max(xs)) / 2, min(ys)
        height = max(1, max(ys) - bottom)
        for i, (x, y) in enumerate(coords):
            phase = math.sin(math.pi * (y - bottom) / height)
            coords[i] = (int(cx + (x - cx) * (1 + strength * phase)), y)


def apply_fold(font, strength, axis_ratio=0.5):
    """Fold points past a vertical internal axis back toward that axis."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs = [p[0] for p in coords]
        axis = min(xs) + (max(xs) - min(xs)) * axis_ratio
        for i, (x, y) in enumerate(coords):
            if x > axis:
                x = x - (x - axis) * 2 * strength
            coords[i] = (int(x), y)


def apply_fracture(font, strength, seed=42, shards=7):
    """Displace angular sectors as coherent shards."""
    rng = random.Random(seed)
    offsets = [(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(shards)]
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs, ys = zip(*coords)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for i, (x, y) in enumerate(coords):
            angle = (math.atan2(y - cy, x - cx) + math.pi) / (2 * math.pi)
            shard = min(shards - 1, int(angle * shards))
            dx, dy = offsets[shard]
            coords[i] = (int(x + dx * strength), int(y + dy * strength))


def apply_wind(font, strength):
    """Push elevated points sideways more strongly than baseline points."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        ys = [p[1] for p in coords]
        bottom, height = min(ys), max(1, max(ys) - min(ys))
        for i, (x, y) in enumerate(coords):
            exposure = max(0, (y - bottom) / height)
            coords[i] = (int(x + strength * exposure ** 2), y)


def apply_polarize(font, strength):
    """Push points away from the vertical centreline into opposing poles."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs = [p[0] for p in coords]
        cx = (min(xs) + max(xs)) / 2
        for i, (x, y) in enumerate(coords):
            direction = -1 if x < cx else 1
            coords[i] = (int(x + direction * strength), y)


def apply_melt(font, strength):
    """Pull lower regions down nonlinearly while leaving upper structure anchored."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        ys = [p[1] for p in coords]
        bottom, height = min(ys), max(1, max(ys) - min(ys))
        for i, (x, y) in enumerate(coords):
            depth = 1 - (y - bottom) / height
            ripple = 0.55 + 0.45 * math.sin(x * math.pi / 190)
            coords[i] = (x, int(y - strength * depth ** 3 * ripple))


def apply_contour_phase(font, strength, seed=42):
    """Rotate each contour around the glyph centre by its own phase."""
    rng = random.Random(seed)
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs, ys = zip(*coords)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        start = 0
        for end in glyph.endPtsOfContours:
            theta = rng.uniform(-strength, strength)
            cosine, sine = math.cos(theta), math.sin(theta)
            for i in range(start, end + 1):
                x, y = coords[i]
                dx, dy = x - cx, y - cy
                coords[i] = (int(cx + dx * cosine - dy * sine),
                             int(cy + dx * sine + dy * cosine))
            start = end + 1


def apply_staircase(font, strength, levels=8):
    """Translate horizontal levels into an accumulating stair-step fault."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        ys = [p[1] for p in coords]
        bottom, height = min(ys), max(1, max(ys) - min(ys))
        for i, (x, y) in enumerate(coords):
            level = min(levels - 1, int((y - bottom) / height * levels))
            coords[i] = (int(x + level * strength / levels), y)


def apply_suture(font, strength):
    """Draw points toward alternating internal seams without collapsing contours."""
    for _, glyph in iter_simple_glyphs(font):
        coords = glyph.coordinates
        if not coords:
            continue
        xs, ys = zip(*coords)
        left, width = min(xs), max(1, max(xs) - min(xs))
        for i, (x, y) in enumerate(coords):
            u = (x - left) / width
            seam = left + width * (0.33 if u < 0.5 else 0.67)
            pull = strength * math.sin(math.pi * min(1, abs(u - 0.5) * 2))
            coords[i] = (int(x + (seam - x) * pull), y)


TRANSFORMS = {
    "perspective": (apply_perspective, (0.0, 1.1)),
    "envelope": (apply_envelope, (0.0, 0.9)),
    "fold": (apply_fold, (0.0, 1.0)),
    "fracture": (apply_fracture, (0.0, 110.0)),
    "wind": (apply_wind, (0.0, 180.0)),
    "polarize": (apply_polarize, (0.0, 90.0)),
    "melt": (apply_melt, (0.0, 190.0)),
    "contour_phase": (apply_contour_phase, (0.0, 0.7)),
    "staircase": (apply_staircase, (0.0, 130.0)),
    "suture": (apply_suture, (0.0, 0.8)),
}
