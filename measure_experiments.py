#!/usr/bin/env python3
"""Measure experiment states: invariants, recoverability, and projections.

Every generated TTF under an experiments directory is compared, glyph by
glyph, against the same glyph in its source font. Three kinds of evidence
are recorded:

  invariants   point and contour counts, winding signature, control-polygon
               area, advance width, bounding box
  recovery     empirical injectivity evidence (point loss, coordinate
               collisions, contour splitting) and, for round-trip sequences,
               the residual left after the inverse was applied
  projections  geometric: mean/max point displacement (when counts match)
               raster:    IoU against the source glyph in a shared frame
               recognize: nearest-neighbour classification against the
                          source font's own glyph set, with a margin

Directory conventions from make_advanced_experiments.py are used for the
paired analyses:

  order-effects/<name>/   paired sequences compared step by step (raster IoU
                          between the two orders = commutator divergence)
  ensembles/<name>/       seed ensembles: consensus raster vs single seeds
  recovery/<name>/        round trips: displacement from source is the residual

Output is written to measurements.json (experiment-index.json is untouched).

Usage (from the repo root):
  python measure_experiments.py                      # experiments-v02, sources auto-detected
  python measure_experiments.py experiments-v02 --sources Sga-Regular.ttf
  python measure_experiments.py experiments --per-glyph

Without --sources, source fonts are the *.ttf files in the current directory,
matched to each experiment by its filename prefix and loaded only when used.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

RES = 96          # raster resolution of the shared frame
DESC = 32         # side of the position/scale-normalised shape descriptor
CURVE_STEPS = 8   # line segments per curve when flattening
SAME_SHAPE = 0.995  # descriptor cosine above which two source glyphs count as one class

STEP_RE = re.compile(r"_(\d+)\.ttf$")


# ---------------------------------------------------------------- outlines

class FlattenPen(BasePen):
    """Flatten a glyph outline into closed polygons."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.contours = []
        self.current = None

    def _moveTo(self, p):
        self.current = [p]

    def _lineTo(self, p):
        self.current.append(p)

    def _curveToOne(self, p1, p2, p3):
        x0, y0 = self.current[-1]
        for i in range(1, CURVE_STEPS + 1):
            t = i / CURVE_STEPS
            m = 1 - t
            self.current.append((
                m ** 3 * x0 + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t ** 3 * p3[0],
                m ** 3 * y0 + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t ** 3 * p3[1],
            ))

    def _qCurveToOne(self, p1, p2):
        x0, y0 = self.current[-1]
        for i in range(1, CURVE_STEPS + 1):
            t = i / CURVE_STEPS
            m = 1 - t
            self.current.append((
                m * m * x0 + 2 * m * t * p1[0] + t * t * p2[0],
                m * m * y0 + 2 * m * t * p1[1] + t * t * p2[1],
            ))

    def _closePath(self):
        if self.current and len(self.current) >= 3:
            self.contours.append(self.current)
        self.current = None

    def _endPath(self):
        self._closePath()


def control_points(font, name):
    """Raw TrueType control points split by contour (composites resolved)."""
    glyf = font["glyf"]
    coords, ends, _ = glyf[name].getCoordinates(glyf)
    pts = np.array(coords, dtype=float).reshape(-1, 2)
    contours, start = [], 0
    for end in ends:
        contours.append(pts[start:end + 1])
        start = end + 1
    return pts, contours


def signed_area(poly):
    if len(poly) < 3:
        return 0.0
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def invariants(font, name):
    pts, contours = control_points(font, name)
    areas = [signed_area(c) for c in contours]
    bbox = None
    if len(pts):
        bbox = [float(pts[:, 0].min()), float(pts[:, 1].min()),
                float(pts[:, 0].max()), float(pts[:, 1].max())]
    return {
        "points": int(len(pts)),
        "contours": len(contours),
        "winding": "".join("+" if a > 0 else "-" if a < 0 else "0" for a in areas),
        "area": float(sum(areas)),
        "advance": int(font["hmtx"][name][0]),
        "bbox": bbox,
    }, pts


# ---------------------------------------------------------------- projections

def raster(font, glyph_set, name, frame):
    """Even-odd raster of a glyph in a fixed frame (x0, y0, size)."""
    pen = FlattenPen(glyph_set)
    glyph_set[name].draw(pen)
    x0, y0, size = frame
    acc = np.zeros((RES, RES), dtype=bool)
    for contour in pen.contours:
        poly = [((x - x0) / size * RES, RES - (y - y0) / size * RES) for x, y in contour]
        img = Image.new("1", (RES, RES), 0)
        ImageDraw.Draw(img).polygon(poly, fill=1)
        acc ^= np.array(img, dtype=bool)
    return acc


def descriptor(mask):
    """Crop to ink, resize to DESC x DESC, centre and normalise."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # Pad to square so aspect ratio survives (O vs 0, l vs I).
    h, w = crop.shape
    side = max(h, w)
    square = np.zeros((side, side), dtype=bool)
    square[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = crop
    crop = square
    img = Image.fromarray((crop * 255).astype(np.uint8)).resize((DESC, DESC), Image.BILINEAR)
    v = np.asarray(img, dtype=float).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 0 else None


def iou(a, b):
    union = np.logical_or(a, b).sum()
    return 1.0 if union == 0 else float(np.logical_and(a, b).sum() / union)


# ---------------------------------------------------------------- sources

class Source:
    """Cached measurements of a source font: the reference for every state."""

    def __init__(self, path, chars=None):
        self.path = path
        self.font = TTFont(path)
        if "glyf" not in self.font:
            raise ValueError(f"{path}: not a TrueType (glyf) font")
        self.upm = self.font["head"].unitsPerEm
        head = self.font["head"]
        w, h = head.xMax - head.xMin, head.yMax - head.yMin
        size = max(w, h) * 1.3
        self.frame = (head.xMin - (size - w) / 2, head.yMin - (size - h) / 2, size)
        gs = self.font.getGlyphSet()

        cmap = self.font.getBestCmap() or {}
        wanted = {cmap[ord(c)] for c in chars if ord(c) in cmap} if chars else set(cmap.values())
        self.glyphs, self.inv, self.pts, self.masks, descs = [], {}, {}, {}, []
        for name in sorted(wanted):
            inv, pts = invariants(self.font, name)
            if inv["points"] == 0:
                continue
            mask = raster(self.font, gs, name, self.frame)
            d = descriptor(mask)
            if d is None:
                continue
            self.glyphs.append(name)
            self.inv[name], self.pts[name], self.masks[name] = inv, pts, mask
            descs.append(d)
        self.D = np.array(descs)
        self.index = {g: i for i, g in enumerate(self.glyphs)}

        # Glyphs with the same shape (e.g. case-folded duplicates) form one class,
        # so that matching either member counts as recognition.
        sims = self.D @ self.D.T
        self.cls = list(range(len(self.glyphs)))
        for i in range(len(self.glyphs)):
            for j in range(i):
                if sims[i, j] >= SAME_SHAPE:
                    self.cls[i] = self.cls[j]
                    break
        self.cls = np.array(self.cls)
        self.unique = np.array([len(np.unique(np.round(self.pts[g]), axis=0)) for g in self.glyphs])

    def recognize(self, name, d):
        if d is None:
            return False, None, None
        sims = self.D @ d
        target = self.cls[self.index[name]]
        same = self.cls == target
        best = int(np.argmax(sims))
        margin = float(sims[same].max() - (sims[~same].max() if (~same).any() else -1.0))
        return bool(same[best]), self.glyphs[best], margin


# ---------------------------------------------------------------- per-state

def classify(src_inv, out_inv, src_unique, out_pts):
    """Empirical evidence about the operator's behaviour on this glyph.

    deleting   points lost or distinct points merged: no inverse can exist
    faulting   contours split or points added: recoverable only with the cut record
    relocating counts and distinctness preserved: consistent with an invertible map
    """
    if out_inv["points"] < src_inv["points"] or out_inv["contours"] < src_inv["contours"]:
        return "deleting"
    out_unique = len(np.unique(np.round(out_pts), axis=0)) if len(out_pts) else 0
    if out_inv["points"] == src_inv["points"] and out_unique < src_unique:
        return "deleting"
    if out_inv["contours"] > src_inv["contours"] or out_inv["points"] > src_inv["points"]:
        return "faulting"
    return "relocating"


def measure_state(path, source, per_glyph, keep_masks):
    font = TTFont(path)
    if "glyf" not in font:
        return None, None
    gs = font.getGlyphSet()
    order = set(font.getGlyphOrder())
    glyph_records, masks = {}, {}
    for name in source.glyphs:
        if name not in order:
            continue
        inv, pts = invariants(font, name)
        src_inv = source.inv[name]
        rec = {"invariants": inv}
        rec["preserved"] = {k: inv[k] == src_inv[k] for k in ("points", "contours", "winding", "advance")}
        rec["area_ratio"] = inv["area"] / src_inv["area"] if src_inv["area"] else None
        if inv["points"] == src_inv["points"] and len(pts):
            disp = np.linalg.norm(pts - source.pts[name], axis=1) / source.upm
            rec["displacement"] = {"mean": float(disp.mean()), "max": float(disp.max())}
        else:
            rec["displacement"] = None
        rec["class"] = classify(src_inv, inv, source.unique[source.index[name]], pts)

        mask = raster(font, gs, name, source.frame)
        rec["iou"] = iou(mask, source.masks[name])
        ok, best, margin = source.recognize(name, descriptor(mask))
        rec["recognized"], rec["read_as"], rec["margin"] = ok, best, margin
        glyph_records[name] = rec
        if keep_masks:
            masks[name] = mask
    font.close()

    n = len(glyph_records)
    if n == 0:
        return None, None
    recs = glyph_records.values()
    disps = [r["displacement"]["mean"] for r in recs if r["displacement"]]
    margins = [r["margin"] for r in recs if r["margin"] is not None]
    summary = {
        "glyphs": n,
        "iou": float(np.mean([r["iou"] for r in recs])),
        "recognition": sum(r["recognized"] for r in recs) / n,
        "margin": float(np.mean(margins)) if margins else None,
        "displacement": float(np.mean(disps)) if disps else None,
        "preserved": {k: sum(r["preserved"][k] for r in recs) / n
                      for k in ("points", "contours", "winding", "advance")},
        "classes": {c: sum(r["class"] == c for r in recs) for c in ("relocating", "faulting", "deleting")},
        # Divergences are the interesting cases: one projection loses the glyph
        # while another still carries it.
        "hidden_but_readable": sorted(g for g, r in glyph_records.items() if r["iou"] < 0.5 and r["recognized"]),
        "intact_but_unreadable": sorted(g for g, r in glyph_records.items()
                                        if all(r["preserved"].values()) and not r["recognized"]),
    }
    if per_glyph:
        summary["per_glyph"] = glyph_records
    return summary, masks


# ---------------------------------------------------------------- provenance

def load_provenance(path, index):
    for candidate in (path.with_suffix(".json"), path.with_name(path.name + ".json")):
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except json.JSONDecodeError:
                pass
    return index.get(path.name)


def load_index(root):
    """Map file name -> provenance, if an experiment-index.json exists."""
    index = {}
    idx = root / "experiment-index.json"
    if not idx.exists():
        return index
    try:
        data = json.loads(idx.read_text())
    except json.JSONDecodeError:
        return index
    entries = data if isinstance(data, list) else data.get("experiments", data.get("fonts", []))
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            p = entry.get("path") or entry.get("file") or entry.get("font")
            if p:
                index[Path(p).name] = entry.get("provenance", entry)
    return index


class SourcePool:
    """Candidate source fonts, loaded lazily the first time an experiment needs one."""

    def __init__(self, paths, chars):
        self.paths = {p.stem: p for p in paths}
        self.chars = chars
        self.loaded, self.failed = {}, set()

    def get(self, stem):
        if stem in self.loaded:
            return self.loaded[stem]
        if stem in self.failed or stem not in self.paths:
            return None
        try:
            src = Source(self.paths[stem], self.chars)
            print(f"source {src.path.name}: {len(src.glyphs)} glyphs", file=sys.stderr)
            self.loaded[stem] = src
            return src
        except Exception as e:
            print(f"skipping source {self.paths[stem]}: {e}", file=sys.stderr)
            self.failed.add(stem)
            return None

    def match(self, path, prov):
        if prov and prov.get("source_path"):
            sp = Path(prov["source_path"])
            if sp.stem not in self.paths and sp.exists():
                self.paths[sp.stem] = sp
            if sp.stem in self.paths:
                return self.get(sp.stem)
        stems = [s for s in self.paths if path.name.startswith(s + "_")]
        return self.get(max(stems, key=len)) if stems else None


# ---------------------------------------------------------------- paired analyses

def order_effects(states, masks):
    """Divergence between two orders of the same operators, step by step."""
    groups = defaultdict(lambda: defaultdict(dict))
    for st in states:
        parts = Path(st["path"]).parts
        if "order-effects" not in parts:
            continue
        seq = parts[parts.index("order-effects") + 1]
        groups[st["source"]][st["step"]][seq] = st["path"]
    out = {}
    for src, steps in groups.items():
        rows = []
        for step in sorted(steps):
            pair = steps[step]
            if len(pair) != 2:
                continue
            (na, pa), (nb, pb) = sorted(pair.items())
            ma, mb = masks[pa], masks[pb]
            shared = set(ma) & set(mb)
            rows.append({"step": step, "pair": [na, nb],
                         "iou_between_orders": float(np.mean([iou(ma[g], mb[g]) for g in shared]))})
        out[src] = rows
    return out


def ensembles(states, masks, sources):
    """Does the seed consensus recover the source better than any one seed?"""
    groups = defaultdict(list)
    for st in states:
        parts = Path(st["path"]).parts
        if "ensembles" in parts:
            groups[(st["source"], parts[parts.index("ensembles") + 1])].append(st["path"])
    out = {}
    for (src_stem, name), paths in groups.items():
        src = sources[src_stem]
        shared = set.intersection(*(set(masks[p]) for p in paths))
        single, consensus, recog = [], [], 0
        for g in shared:
            stack = np.stack([masks[p][g] for p in paths])
            single.append(np.mean([iou(m, src.masks[g]) for m in stack]))
            vote = stack.mean(axis=0) >= 0.5
            consensus.append(iou(vote, src.masks[g]))
            recog += src.recognize(g, descriptor(vote))[0]
        out[f"{src_stem}/{name}"] = {
            "members": len(paths),
            "mean_single_iou": float(np.mean(single)),
            "consensus_iou": float(np.mean(consensus)),
            "consensus_recognition": recog / len(shared) if shared else None,
        }
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, nargs="?", default=Path("experiments-v02"),
                    help="experiments directory (default: experiments-v02)")
    ap.add_argument("--sources", nargs="+", type=Path,
                    help="source TTFs (default: every *.ttf in the current directory)")
    ap.add_argument("--chars", help="restrict to these characters (default: whole cmap)")
    ap.add_argument("--per-glyph", action="store_true", help="include per-glyph records")
    ap.add_argument("--out", type=Path, help="output path (default: <root>/measurements.json)")
    args = ap.parse_args()

    if not args.root.is_dir():
        sys.exit(f"{args.root} is not a directory. Pass the experiments folder, e.g. "
                 f"python measure_experiments.py experiments-v02")
    candidates = args.sources or sorted(Path(".").glob("*.ttf"))
    if not candidates:
        sys.exit("no source fonts: run from the repo root or pass --sources")
    pool = SourcePool(candidates, args.chars)

    index = load_index(args.root)
    states, masks = [], {}
    files = sorted(args.root.rglob("*.ttf"))
    for i, path in enumerate(files, 1):
        prov = load_provenance(path, index)
        src = pool.match(path, prov)
        if src is None:
            continue
        rel = path.relative_to(args.root)
        keep = "order-effects" in rel.parts or "ensembles" in rel.parts
        try:
            summary, m = measure_state(path, src, args.per_glyph, keep)
        except Exception as e:
            print(f"  {rel}: {e}", file=sys.stderr)
            continue
        if summary is None:
            continue
        step = (prov or {}).get("step")
        if step is None:
            hit = STEP_RE.search(path.name)
            step = int(hit.group(1)) if hit else None
        st = {"path": str(rel), "source": src.path.stem, "sequence": str(rel.parent),
              "step": step, "provenance": prov, **summary}
        kind = (prov or {}).get("sequence_kind")
        if kind == "round_trip" or "recovery" in rel.parts:
            st["recovery_residual"] = summary["displacement"]
        states.append(st)
        if keep:
            masks[str(rel)] = m
        if i % 25 == 0:
            print(f"  {i}/{len(files)}", file=sys.stderr)

    sources = pool.loaded
    if not states:
        sys.exit(f"no experiment fonts under {args.root} matched a source font")

    sequences = defaultdict(list)
    for st in states:
        sequences[st["sequence"]].append({k: st[k] for k in
                                          ("step", "iou", "recognition", "margin", "displacement", "classes")})
    for rows in sequences.values():
        rows.sort(key=lambda r: (r["step"] is None, r["step"]))

    result = {
        "generated_by": "measure_experiments.py",
        "raster_resolution": RES,
        "sources": {s: {"path": str(v.path), "glyphs": len(v.glyphs),
                        "shape_classes": int(len(np.unique(v.cls)))} for s, v in sources.items()},
        "states": states,
        "sequences": dict(sequences),
        "order_effects": order_effects(states, masks),
        "ensembles": ensembles(states, masks, sources),
    }
    out = args.out or args.root / "measurements.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"{len(states)} states measured -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
