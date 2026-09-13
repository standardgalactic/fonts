#!/usr/bin/env python3
"""Generate v02 experiments: fields, order effects, recovery, and ensembles."""

import argparse
from pathlib import Path

from advanced_experiments import TRANSFORMS, apply_fracture
from experiment_support import measure_font
from make_experiments import (
    apply_quantize, apply_shear, apply_wave, generate_sequence, load_font, save_font,
)


def provenance(source, name, parameters, kind, step, steps, metrics, parent=None):
    return {
        "source_path": source, "transform": name, "parameters": parameters,
        "sequence_kind": kind, "step": step, "steps": steps,
        "parent": parent or source, "source_metrics": metrics,
    }


def generate(source, out, steps):
    source_font = load_font(source)
    baseline = measure_font(source_font)
    source_font.close()

    for name, (function, bounds) in TRANSFORMS.items():
        generate_sequence(source, out / "fields" / name, name, function, bounds, steps)

    for i in range(steps):
        t = i / max(1, steps - 1)
        paths = (
            ("wave_then_grid", ((apply_wave, (t * 90, 1.7)), (apply_quantize, (max(1, int(2 + t * 34)),)))),
            ("grid_then_wave", ((apply_quantize, (max(1, int(2 + t * 34)),)), (apply_wave, (t * 90, 1.7)))),
        )
        for name, operations in paths:
            font = load_font(source)
            for function, parameters in operations:
                function(font, *parameters)
            path = out / "order-effects" / name / f"{source.stem}_{name}_{i:03d}.ttf"
            save_font(font, path, provenance=provenance(
                source, name, {"intensity": t}, "order_comparison", i, steps, baseline
            ))

    for i in range(steps):
        t = i / max(1, steps - 1)
        font = load_font(source)
        apply_shear(font, t * 0.45)
        apply_shear(font, -t * 0.45)
        name = "shear_round_trip"
        path = out / "recovery" / name / f"{source.stem}_{name}_{i:03d}.ttf"
        save_font(font, path, provenance=provenance(
            source, name, {"forward": t * 0.45, "reverse": -t * 0.45},
            "round_trip", i, steps, baseline
        ))

    for seed in range(steps):
        font = load_font(source)
        apply_fracture(font, 85, seed=seed)
        name = "fracture_ensemble"
        path = out / "ensembles" / name / f"{source.stem}_{name}_{seed:03d}.ttf"
        save_font(font, path, provenance=provenance(
            source, name, {"strength": 85, "seed": seed},
            "seed_ensemble", seed, steps, baseline
        ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fonts", nargs="*", type=Path, default=[Path("Sga-Regular.ttf")])
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("experiments-v02"))
    args = parser.parse_args()
    for source in args.fonts:
        if not source.exists():
            parser.error(f"font not found: {source}")
        generate(source, args.out, args.steps)
    print(f"Advanced experiments written to {args.out}")


if __name__ == "__main__":
    main()
