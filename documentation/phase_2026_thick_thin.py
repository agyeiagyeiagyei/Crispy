"""Generate the thick-thin transitions specimen for PHASE_2026.md section 1b.

Renders ``a`` and ``g`` side by side at three weights (Thin, Regular,
Bold), all at the same font size and width (Normal, wdth=100), so the
reader can see how the unintentional thick-thin moments in these
glyphs evolve as weight increases.

Parametric coordinates come from the existing avar2 mappings in
``preview-app/Crispy-avar.csv``:

    Thin     (wght=100, wdth=100)  →  XTRA=461.8  XOPQ=46.9    YOPQ=44.0
    Regular  (wght=400, wdth=100)  →  XTRA=627.0  XOPQ=187.672 YOPQ=160.0
    Bold     (wght=700, wdth=100)  →  XTRA=735.6  XOPQ=400.738 YOPQ=324.7

Run from the repo root:

    python3 documentation/phase_2026_thick_thin.py --output documentation/phase_2026_thick_thin.png
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

WIDTH = 1600
HEIGHT = 520
MARGIN = 60
PAIR = "ag"
GLYPH_SIZE = 96

# Three weights at Normal width. Same wdth, same font size — the
# only thing that changes is the parametric weight, so the reader
# tracks the thick-thin moments as the strokes thicken.
COLUMNS = [
    {
        "label": "Thin",
        "wght": 100,
        "wdth": 100,
        "XTRA": 461.8,
        "XOPQ": 46.9,
        "YOPQ": 44.0,
    },
    {
        "label": "Regular",
        "wght": 400,
        "wdth": 100,
        "XTRA": 627.0,
        "XOPQ": 187.672,
        "YOPQ": 160.0,
    },
    {
        "label": "Bold",
        "wght": 700,
        "wdth": 100,
        "XTRA": 735.6,
        "XOPQ": 400.738,
        "YOPQ": 324.7,
    },
]

LABEL_FONT = "Helvetica"
LABEL_SIZE = 14
SUBLABEL_SIZE = 11


def render(output_path: Path) -> None:
    newDrawing()
    newPage(WIDTH, HEIGHT)

    fill(1, 1, 1)
    rect(0, 0, WIDTH, HEIGHT)

    baseline_y = MARGIN + 200
    column_width = (WIDTH - 2 * MARGIN) / 3

    for i, col in enumerate(COLUMNS):
        cx = MARGIN + column_width * (i + 0.5)

        fill(0)
        font(FONT_PATH)
        fontSize(GLYPH_SIZE)
        fontVariations(XTRA=col["XTRA"], XOPQ=col["XOPQ"], YOPQ=col["YOPQ"])

        pair_w, _ = textSize(PAIR)
        text(PAIR, (cx - pair_w / 2, baseline_y))

        caption_y = MARGIN + 60
        fill(0)
        font(LABEL_FONT)
        fontSize(LABEL_SIZE)
        label_w, _ = textSize(col["label"])
        text(col["label"], (cx - label_w / 2, caption_y))

        fontSize(SUBLABEL_SIZE)
        fill(0.4)
        sub = f"wght {col['wght']}, wdth {col['wdth']}"
        sub_w, _ = textSize(sub)
        text(sub, (cx - sub_w / 2, caption_y - 16))

        sub2 = f"XOPQ {col['XOPQ']:.0f}  XTRA {col['XTRA']:.0f}  YOPQ {col['YOPQ']:.0f}"
        sub2_w, _ = textSize(sub2)
        text(sub2, (cx - sub2_w / 2, caption_y - 30))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    saveImage(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        metavar="PNG",
        default="documentation/phase_2026_thick_thin.png",
        help="where to write the PNG file",
    )
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
