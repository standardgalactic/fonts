#!/usr/bin/env bash
#
# generate_degrading_pdfs.sh
#
# Runs degrading_pdf_generator.py once per .ttf file found directly in
# --fonts-dir (non-recursive - it will NOT descend into experiments/,
# experiments-v01/, experiments-v02/, etc., since those already hold
# degraded variants rather than base fonts to degrade further).
#
# Usage:
#   ./generate_degrading_pdfs.sh [fonts-dir] [out-dir] [pages] [curve] [text-file]
#
# Defaults: fonts-dir=. out-dir=./degrading-pdfs pages=12 curve=ease_in
# text-file: omitted -> generator's built-in placeholder corpus is used
#
# Examples:
#   ./generate_degrading_pdfs.sh
#   ./generate_degrading_pdfs.sh . ./out 20 cliff mycorpus.txt
#
set -uo pipefail   # deliberately NOT -e: one font's failure must not
                    # abort the batch

FONTS_DIR="${1:-.}"
OUT_DIR="${2:-./degrading-pdfs}"
PAGES="${3:-12}"
CURVE="${4:-ease_in}"
TEXT_FILE="${5:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATOR="$SCRIPT_DIR/degrading_pdf_generator.py"
LOG="$OUT_DIR/generate_degrading_pdfs.log"

if [ ! -f "$GENERATOR" ]; then
    echo "Could not find degrading_pdf_generator.py next to this script ($SCRIPT_DIR)." >&2
    echo "Place this script in the same directory as degrading_pdf_generator.py, glyph_transform.py, degradation_curve.py, and adversarial_ocr_core.py." >&2
    exit 1
fi

if [ -n "$TEXT_FILE" ] && [ ! -f "$TEXT_FILE" ]; then
    echo "Text file not found: $TEXT_FILE" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
: > "$LOG"

log() { echo "$1" | tee -a "$LOG"; }

# Turn a filename stem into a clean, lowercase, hyphenated directory
# name: "Amiri-BoldItalic" -> "amiri-bolditalic", "Lingojam_cipher-Regular"
# -> "lingojam-cipher-regular".
slugify() {
    echo "$1" \
        | tr 'A-Z' 'a-z' \
        | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

log "==== generate_degrading_pdfs.sh ===="
log "fonts-dir: $FONTS_DIR"
log "out-dir:   $OUT_DIR"
log "pages:     $PAGES"
log "curve:     $CURVE"
log "text-file: ${TEXT_FILE:-(built-in placeholder corpus)}"
log ""

mapfile -t FONT_FILES < <(find "$FONTS_DIR" -maxdepth 1 -type f -iname "*.ttf" | sort)

if [ "${#FONT_FILES[@]}" -eq 0 ]; then
    log "No .ttf files found directly in $FONTS_DIR (non-recursive)."
    exit 1
fi

log "Found ${#FONT_FILES[@]} font(s) in $FONTS_DIR"
log ""

succeeded=0
failed=0

for font_path in "${FONT_FILES[@]}"; do
    stem="$(basename "$font_path")"
    stem="${stem%.[tT][tT][fF]}"
    name="$(slugify "$stem")"

    font_out_dir="$OUT_DIR/$name"
    log "----  $name  ($font_path) -> $font_out_dir"

    cmd=(python3 "$GENERATOR" --font "$font_path" --out "$font_out_dir" --pages "$PAGES" --curve "$CURVE")
    if [ -n "$TEXT_FILE" ]; then
        cmd+=(--text-file "$TEXT_FILE")
    fi

    if "${cmd[@]}" >>"$LOG" 2>&1; then
        log "OK    $name -> $font_out_dir/degrading.pdf"
        succeeded=$((succeeded + 1))
    else
        log "FAIL  $name (see $LOG for the full error)"
        failed=$((failed + 1))
    fi
done

log ""
log "==== Summary ===="
log "Fonts found: ${#FONT_FILES[@]}"
log "Succeeded:   $succeeded"
log "Failed:      $failed"
log "Log:         $LOG"
