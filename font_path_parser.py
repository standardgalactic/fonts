"""
font_path_parser.py

Extracts (base_font, transform_group) from a font file's path, honoring
the three different naming conventions actually used across the repo:

  experiments/compound/Amiri-BoldItalic_dissolution_000.ttf
    -> filename-encoded: base + "_" + group + "_" + index

  experiments/sequences/Amiri-BoldItalic_jitter_seq/Amiri-BoldItalic_jitter_000.ttf
    -> group encoded in the parent "*_seq" directory name

  experiments-v02/fields/melt/shapeform_melt_000.ttf
  experiments-v02/order-effects/grid_then_wave/shapeform_grid_then_wave_000.ttf
  experiments-v02/recovery/shear_round_trip/shapeform_shear_round_trip_000.ttf
    -> group encoded directly as the parent directory name (v02's
       fields/order-effects/ensembles/recovery are organizational
       buckets, not the group label itself)

  experiments-v01/Amiri-BoldItalic_jitter10.ttf
    -> filename-encoded, no underscore between the effect name and its
       numeric parameter

Directory names are preferred over filename parsing whenever the
directory itself is semantic (not one of the generic organizational
bucket names) - this is deliberately hybrid rather than a single
regex, because the repo's own naming isn't consistent enough for one
pattern to cover it honestly.
"""

import re

DEFAULT_KNOWN_BASES = [
    "Amiri-BoldItalic", "Amiri-Bold", "Amiri-Italic", "Amiri-Regular",
    "Cheiro-Regular", "Clypto-Regular", "CursiveGalactic-Regular",
    "Lingojam_cipher-Regular", "Logico_philosophicus-Regular",
    "NovaMonoStandardGalactic", "Sga-Regular", "Systada-Regular",
    "Systada", "dactyl", "shapeform",
]

# Directory names that are purely organizational (v02's category buckets,
# the experiments-v0x roots, and the "sequences" wrapper) rather than a
# transform's actual name - these never get used as the group label.
GENERIC_BUCKETS = {
    "static", "compound", "fields", "order-effects", "ensembles",
    "recovery", "experiments", "experiments-v01", "experiments-v02",
    "sequences",
}

_TRAILING_INDEX_RE = re.compile(r"^(.*?)[_]?(\d+)$")


def _strip_known_base(stem, known_bases):
    """Return (base_font, remainder) - remainder has the leading '_'
    (if any) stripped. Longest base name wins so 'Systada-Regular'
    matches before the shorter 'Systada'."""
    for base in sorted(known_bases, key=len, reverse=True):
        if stem == base:
            return base, ""
        if stem.startswith(base + "_"):
            return base, stem[len(base) + 1:]
    return "unknown", stem


def parse_font_path(rel_path, known_bases=None):
    """
    rel_path: the font file's path relative to the scan root, using '/'
    separators (e.g. "experiments/compound/Amiri-Bold_dissolution_000.ttf").

    Returns {"base_font": str, "group": str, "stem": str}.
    """
    if known_bases is None:
        known_bases = DEFAULT_KNOWN_BASES

    parts = rel_path.replace("\\", "/").split("/")
    filename = parts[-1]
    dirs = parts[:-1]
    stem = re.sub(r"\.(ttf|ttx)$", "", filename, flags=re.IGNORECASE)

    base_font, remainder = _strip_known_base(stem, known_bases)

    group = None

    if dirs:
        last_dir = dirs[-1]
        if last_dir.endswith("_seq"):
            g = last_dir
            g_base, g_rest = _strip_known_base(g, known_bases)
            g = g_rest if g_rest else g
            if g.endswith("_seq"):
                g = g[:-len("_seq")]
            group = g
        elif last_dir not in GENERIC_BUCKETS:
            group = last_dir

    if group is None:
        m = _TRAILING_INDEX_RE.match(remainder)
        if m and m.group(1):
            group = m.group(1)
        else:
            group = remainder if remainder else "unlabeled"

    return {"base_font": base_font, "group": group, "stem": stem}
