"""Generate the core-spacing specimen for PHASE_2026.md section 5.

Renders the word ``ADHESION`` at both width extremes of Crispy's
current designspace (Condensed and Ultra Extended), stacked, at the
same nominal weight (Regular, wght=400) and point size — so the
reader sees the current tracking honestly at each extreme.

Parametric values are taken from the existing avar2 mappings in
``preview-app/Crispy-avar.csv``:

    Regular Condensed       (wght=400, wdth=52)   →  XTRA=290     XOPQ=147   YOPQ=130
    Regular Ultra Extended  (wght=400, wdth=300)  →  XTRA=2210.6  XOPQ=235.2 YOPQ=199.5

ADHESION is a long-running spacing test word in type design — it
contains a mix of curves (D, S, O), straights (H, N, I), and joins
(A, E) that all need to read evenly when the spacing is correct.

Run from the repo root:

    python3 documentation/phase_2026_spacing.py --output documentation/phase_2026_spacing.png
"""

import argparse
from pathlib import Path

from drawbot_skia.drawbot import (
    newDrawing,
    newPage,
    fill,
    rect,
    font,
    fontSize,
    fontVariations,
    textSize,
    text,
    saveImage,
)


FONT_PATH = "preview-app/fonts-avar2/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf"

WORD = "ADHESION"
GLYPH_SIZE = 96
MARGIN = 60
GAP_BETWEEN_LINES = 50

# Two extremes at Regular weight. Stacked narrow-over-wide, both at
# the same point size and weight — the only thing that varies is
# wdth, so the eye reads the spacing-at-width directly.
ROWS = [
    {
        "label": "Condensed",
        "wght": 400,
        "wdth": 52,
        "XTRA": 290.0,
        "XOPQ": 147.0,
        "YOPQ": 130.0,
    },
    {
        "label": "Ultra Extended",
        "wght": 400,
        "wdth": 300,
        "XTRA": 2210.6,
        "XOPQ": 235.2,
        "YOPQ": 199.5,
    },
]

LABEL_FONT = "Helvetica"
LABEL_SIZE = 14
SUBLABEL_SIZE = 11


def render(output_path: Path) -> None:
    # First pass: measure widths at each variation so we can size
    # the canvas. We use a throwaway drawing and discard it before
    # the real one so drawbot_skia's saveImage doesn't see two pages.
    newDrawing()
    newPage(2000, 1000)
    widest = 0
    for row in ROWS:
        font(FONT_PATH)
        fontSize(GLYPH_SIZE)
        fontVariations(XTRA=row["XTRA"], XOPQ=row["XOPQ"], YOPQ=row["YOPQ"])
        w, _ = textSize(WORD)
        widest = max(widest, w)

    # Layout budget per row: caption block + glyph band. The glyph
    # band is GLYPH_SIZE plus a small descender allowance.
    caption_block = 26   # caption + sublabel + a hair
    descender_pad = 14
    row_band = caption_block + GLYPH_SIZE + descender_pad

    bottom_margin = 20   # tighter than the top margin
    width = int(widest + 2 * MARGIN + 40)
    height = MARGIN + len(ROWS) * row_band + (len(ROWS) - 1) * GAP_BETWEEN_LINES + bottom_margin

    # Second pass: start fresh and render at the computed size.
    newDrawing()
    newPage(width, height)
    fill(1, 1, 1)
    rect(0, 0, width, height)

    # drawbot's origin is bottom-left; we walk down from the top.
    y_cursor = height - MARGIN

    for row in ROWS:
        cap_y = y_cursor - 14  # caption baseline a little below the top of the row band
        fill(0)
        font(LABEL_FONT)
        fontSize(LABEL_SIZE)
        label_w, _ = textSize(row["label"])
        text(row["label"], (MARGIN, cap_y))

        fontSize(SUBLABEL_SIZE)
        fill(0.4)
        sub = f"wght {row['wght']}, wdth {row['wdth']}"
        text(sub, (MARGIN + label_w + 12, cap_y))

        glyph_baseline = cap_y - GLYPH_SIZE + 4

        fill(0)
        font(FONT_PATH)
        fontSize(GLYPH_SIZE)
        fontVariations(XTRA=row["XTRA"], XOPQ=row["XOPQ"], YOPQ=row["YOPQ"])
        text(WORD, (MARGIN, glyph_baseline))

        # Drop the cursor to the bottom of this row band, then gap to the next.
        y_cursor = glyph_baseline - descender_pad - GAP_BETWEEN_LINES

    output_path.parent.mkdir(parents=True, exist_ok=True)
    saveImage(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        metavar="PNG",
        default="documentation/phase_2026_spacing.png",
        help="where to write the PNG file",
    )
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
