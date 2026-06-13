#!/usr/bin/env python3

import argparse
import html
from pathlib import Path

DEFAULT_TEXT = """
Reality is not a collection of things.
It is what remains reachable.

The quick brown fox jumps over the lazy dog.

ABCDEFGHIJKLMNOPQRSTUVWXYZ
abcdefghijklmnopqrstuvwxyz
0123456789

!@#$%^&*()[]{}<>?/\\|+=-_~
"""

HTML_HEADER = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Font Sequence Sampler</title>

<style>
body {
    background: #111;
    color: #ddd;
    font-family: sans-serif;
    margin: 0;
    padding: 20px;
}

h1 {
    color: #8fd16a;
}

.card {
    background: #1b1b1b;
    border: 1px solid #333;
    margin-bottom: 24px;
    padding: 16px;
    border-radius: 8px;
}

.name {
    color: #8fd16a;
    margin-bottom: 12px;
    font-family: monospace;
}

.sample {
    font-size: 36px;
    line-height: 1.4;
    word-break: break-word;
}
</style>

"""

HTML_FOOTER = """
</body>
</html>
"""


def make_family(i):
    return f"fontseq{i:03d}"


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fonts",
        required=True,
        help="directory containing sequence"
    )

    parser.add_argument(
        "--text",
        help="sample text file"
    )

    parser.add_argument(
        "--out",
        default="sample.html"
    )

    args = parser.parse_args()

    font_dir = Path(args.fonts)

    fonts = sorted(font_dir.glob("*.ttf"))

    if not fonts:
        raise SystemExit("No fonts found")

    if args.text:
        sample_text = Path(args.text).read_text(
            encoding="utf-8"
        )
    else:
        sample_text = DEFAULT_TEXT

    html_parts = [HTML_HEADER]

    #
    # Font declarations
    #

    html_parts.append("<style>\n")

    for i, font in enumerate(fonts):

        family = make_family(i)

        html_parts.append(f"""
@font-face {{
    font-family: "{family}";
    src: url("{font.name}");
}}
""")

    html_parts.append("</style>\n")
    html_parts.append("</head><body>")

    html_parts.append(
        f"<h1>{html.escape(font_dir.name)}</h1>"
    )

    #
    # Samples
    #

    for i, font in enumerate(fonts):

        family = make_family(i)

        html_parts.append(f"""
<div class="card">

<div class="name">
{i:03d} — {html.escape(font.name)}
</div>

<div class="sample"
     style='font-family:"{family}"'>

{html.escape(sample_text)}

</div>

</div>
""")

    html_parts.append(HTML_FOOTER)

    Path(args.out).write_text(
        "\n".join(html_parts),
        encoding="utf-8"
    )

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
