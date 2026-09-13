#!/usr/bin/env python3
"""Build the compact index consumed by experiment-analysis-viewer.html."""

import json
import re
from pathlib import Path

ROOTS = [Path("experiments"), Path("experiments-v01"), Path("experiments-v02")]
STEP_RE = re.compile(r"^(?P<series>.+)_(?P<step>\d{3})\.ttf$")


def main():
    source_fonts = sorted(Path(".").glob("*.ttf"))
    source_stems = sorted((p.stem for p in source_fonts), key=len, reverse=True)
    records = []
    for root in ROOTS:
        if not root.exists():
            continue
        for font_path in sorted(root.rglob("*.ttf")):
            rel = font_path.as_posix()
            match = STEP_RE.match(font_path.name)
            stem = next((s for s in source_stems if font_path.stem.startswith(s + "_")), None)
            sidecar = font_path.with_suffix(".json")
            records.append({
                "path": rel,
                "name": font_path.name,
                "root": root.name,
                "group": font_path.parent.relative_to(root).as_posix(),
                "series": match.group("series") if match else font_path.stem,
                "step": int(match.group("step")) if match else None,
                "source": f"{stem}.ttf" if stem else None,
                "metadata": sidecar.as_posix() if sidecar.exists() else None,
            })
    payload = {"schema_version": 1, "fonts": records}
    Path("experiment-index.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote experiment-index.json ({len(records)} fonts)")


if __name__ == "__main__":
    main()
