#!/usr/bin/env python3

import json
from pathlib import Path

ROOTS = [
    Path("experiments"),
    Path("experiments-v01"),
]

def insert_path(tree, rel_parts):
    if len(rel_parts) == 1:
        tree.setdefault("_files", []).append(rel_parts[0])
        return

    head = rel_parts[0]
    rest = rel_parts[1:]
    tree.setdefault(head, {})
    insert_path(tree[head], rest)

def clean_tree(node):
    out = {}

    for key, value in sorted(node.items()):
        if key == "_files":
            continue
        out[key] = clean_tree(value)

    if "_files" in node:
        files = sorted(node["_files"])
        if out:
            out["files"] = files
        else:
            return files

    return out

manifest = {}

for root in ROOTS:
    if not root.exists():
        continue

    tree = {}

    for path in sorted(root.rglob("*.ttf")):
        rel = path.relative_to(root)
        insert_path(tree, list(rel.parts))

    manifest[root.name] = clean_tree(tree)

Path("font-manifest.json").write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)

print("Wrote font-manifest.json")
