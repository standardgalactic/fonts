"""
degradation_curve.py

Pure functions mapping a document position (0.0 = first page, 1.0 = last
page) to a distortion intensity (0.0 = clean, 1.0 = maximally degraded).
Kept separate from the font-transform and PDF-generation code so the
curve shapes themselves can be tested and reasoned about independently.
"""

CURVES = {}


def register(name):
    def deco(fn):
        CURVES[name] = fn
        return fn
    return deco


@register("linear")
def linear(t):
    """Steady, constant-rate decay - a fixed amount worse every page."""
    return t


@register("ease_in")
def ease_in(t):
    """Slow to start, accelerating toward the end - stays readable
    longer, then degrades faster near the finish. Quadratic."""
    return t * t


@register("ease_in_cubic")
def ease_in_cubic(t):
    """Even more back-loaded than ease_in: readable for most of the
    document, unreadable only in a shorter final stretch."""
    return t * t * t


@register("cliff")
def cliff(t, cliff_at=0.7, floor=0.15):
    """Stays near-clean until `cliff_at`, then rapidly ramps to full
    degradation over the remaining span. Models a document that's fine
    until it abruptly isn't, e.g. a scan that degrades because of a
    physical defect starting partway through rather than a smooth decay."""
    if t <= cliff_at:
        return floor * (t / cliff_at if cliff_at > 0 else 0)
    span = 1 - cliff_at
    return floor + (1 - floor) * ((t - cliff_at) / span if span > 0 else 1)


@register("ease_in_out")
def ease_in_out(t):
    """Slow start, fast middle, slow finish - smoothstep. Useful when
    you want the two extremes (start, end) to both look deliberate/clean
    at their targets rather than the curve being at a steep slope right
    at the boundary."""
    return t * t * (3 - 2 * t)


def intensity_for_position(position, curve_name="ease_in", **kwargs):
    """
    position: float in [0, 1], 0 = first page/paragraph, 1 = last.
    Returns an intensity float in [0, 1], clamped.
    """
    if position < 0 or position > 1:
        raise ValueError("position must be in [0, 1], got {}".format(position))
    if curve_name not in CURVES:
        raise ValueError("Unknown curve '{}'. Known curves: {}".format(
            curve_name, sorted(CURVES.keys())))
    value = CURVES[curve_name](position, **kwargs)
    return max(0.0, min(1.0, value))


def positions_for_n_pages(n):
    """Evenly spaced positions in [0, 1] for n pages/steps. n=1 returns
    [0.0] (a single page is just the clean baseline, not degraded)."""
    if n <= 0:
        raise ValueError("n must be >= 1")
    if n == 1:
        return [0.0]
    return [i / (n - 1) for i in range(n)]
