#!/usr/bin/env python3
"""
make_degradation_doc.py — Generates LaTeX for a typographically degrading document.

Usage:
    python3 make_degradation_doc.py \
        --fonts experiments/sequences/Sga-Regular_jitter_seq/ \
        --text source.txt \
        --granularity paragraph
        --out output/

Compile with:
    lualatex main.tex
"""

import argparse
import re
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Text splitting
# ─────────────────────────────────────────────────────────────────────────────

def split_paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]

def split_words(text):
    return text.split()

def split_pages(text, words_per_page=300):
    words = text.split()
    return [" ".join(words[i:i+words_per_page]) for i in range(0, len(words), words_per_page)]


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX escaping
# ─────────────────────────────────────────────────────────────────────────────

LATEX_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

def latex_escape(s):
    return "".join(LATEX_SPECIAL.get(c, c) for c in s)


# ─────────────────────────────────────────────────────────────────────────────
# Font declaration generation
# ─────────────────────────────────────────────────────────────────────────────

def make_font_cmd(index):
    # Returns bare name (no backslash) — used both for \newfontfamily and \csname
    return f"fontseqX{index:03d}"

def make_decls(font_paths, font_dir_latex):
    lines = [
        "% Auto-generated font declarations — do not edit by hand.",
        "",
    ]
    for i, fp in enumerate(font_paths):
        cmd = make_font_cmd(i)
        lines.append(
            "\\newfontfamily\\" + cmd +
            "[Path={" + font_dir_latex + "/},Ligatures=TeX]" +
            "{" + fp.name + "}"
        )
    lines.append("")
    # Generic macro: \FontStep{003} expands to \fontseqX003
    lines.append(r"\newcommand{\FontStep}[1]{\csname fontseqX#1\endcsname}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Body generation
# ─────────────────────────────────────────────────────────────────────────────

def assign_fonts(chunks, n_fonts):
    result = []
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        t = i / max(1, n - 1)
        font_idx = round(t * (n_fonts - 1))
        result.append((font_idx, chunk))
    return result

def emit_chunk(font_idx, text):
    step = f"{font_idx:03d}"
    escaped = latex_escape(text)
    return "{\\FontStep{" + step + "} " + escaped + "}"

def make_body(chunks_with_fonts, granularity):
    lines = [
        "% Auto-generated body — do not edit by hand.",
        "",
    ]
    if granularity in ("paragraph", "page"):
        for font_idx, chunk in chunks_with_fonts:
            lines.append(emit_chunk(font_idx, chunk))
            lines.append("")
            lines.append("\\medskip")
            lines.append("")
    elif granularity == "sentence":
        for font_idx, chunk in chunks_with_fonts:
            lines.append(emit_chunk(font_idx, chunk))
    elif granularity == "word":
        buf = []
        for font_idx, word in chunks_with_fonts:
            buf.append(emit_chunk(font_idx, word))
            if len(buf) >= 12:
                lines.append(" ".join(buf))
                buf = []
        if buf:
            lines.append(" ".join(buf))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Root document template
# ─────────────────────────────────────────────────────────────────────────────

MAIN_TEMPLATE = """\
\\documentclass[12pt,a4paper]{article}

\\usepackage[no-math]{fontspec}
\\usepackage{geometry}
\\geometry{margin=2.5cm}

\\input{font_decls.tex}

\\setmainfont[Path=FONT_DIR/]{FIRST_FONT}

\\begin{document}

\\input{body.tex}

\\end{document}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TEXT = """\
Reality is not a collection of things.

It is what remains reachable from a given position.

The quick brown fox jumps over the lazy dog.

ABCDEFGHIJKLMNOPQRSTUVWXYZ
abcdefghijklmnopqrstuvwxyz
0123456789
"""

def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX for a degrading document.")
    parser.add_argument("--fonts", required=True, help="Directory containing sorted .ttf sequence")
    parser.add_argument("--text", help="Source text file (omit to use built-in test text)")
    parser.add_argument("--granularity", default="paragraph",
                        choices=["paragraph", "sentence", "word", "page"],
                        help="Unit at which font switches")
    parser.add_argument("--out", default="output", help="Output directory for .tex files")
    args = parser.parse_args()

    fonts_dir = Path(args.fonts)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect fonts
    font_paths = sorted(fonts_dir.glob("*.ttf"))
    if not font_paths:
        print(f"No .ttf files found in {fonts_dir}")
        sys.exit(1)
    print(f"Found {len(font_paths)} font steps in sequence.")

    # Load text
    if args.text:
        text = Path(args.text).read_text(encoding="utf-8")
    else:
        text = DEFAULT_TEXT
        print("No --text supplied; using built-in test text.")

    # Split
    if args.granularity == "paragraph":
        chunks = split_paragraphs(text)
    elif args.granularity == "sentence":
        chunks = split_sentences(text)
    elif args.granularity == "word":
        chunks = split_words(text)
    elif args.granularity == "page":
        chunks = split_pages(text)

    print(f"Split into {len(chunks)} {args.granularity}(s).")

    # Assign fonts
    assigned = assign_fonts(chunks, len(font_paths))

    # Relative path: output/main.tex looks one level up for fonts
    font_dir_latex = ("../" + str(fonts_dir).replace("\\", "/")).replace("//", "/")

    # Write font_decls.tex
    decls = make_decls(font_paths, font_dir_latex)
    (out_dir / "font_decls.tex").write_text(decls, encoding="utf-8")
    print(f"Wrote {out_dir}/font_decls.tex  ({len(font_paths)} declarations)")

    # Write body.tex
    body = make_body(assigned, args.granularity)
    (out_dir / "body.tex").write_text(body, encoding="utf-8")
    print(f"Wrote {out_dir}/body.tex  ({len(chunks)} chunks)")

    # Write main.tex
    main_doc = MAIN_TEMPLATE.replace("FONT_DIR", font_dir_latex)
    main_doc = main_doc.replace("FIRST_FONT", font_paths[0].name)
    (out_dir / "main.tex").write_text(main_doc, encoding="utf-8")
    print(f"Wrote {out_dir}/main.tex")

    print(f"""
Done. To compile:
    cd {out_dir}
    lualatex main.tex

Font series: {fonts_dir}
Granularity: {args.granularity}
""")


if __name__ == "__main__":
    main()