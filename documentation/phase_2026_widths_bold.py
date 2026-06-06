"""Generate the three-corners "a" specimen for PHASE_2026.md.

Renders the letter "a" at the three width extremes of Crispy's current
designspace, all at the heaviest weight. The values are taken from the
existing avar2 mappings — i.e. the corners as currently defined by
the master coordinates in ``sources/Crispy-avar.csv``:

    Bold Condensed       (wght=700, wdth=52)   →  XTRA=318    XOPQ=407    YOPQ=347
    Bold                 (wght=700, wdth=100)  →  XTRA=735.6  XOPQ=400.74 YOPQ=324.7
    Bold Ultra Extended  (wght=700, wdth=300)  →  XTRA=2369.9 XOPQ=619.7  YOPQ=362

Run from the repo root:

    python3 documentation/phase_2026_widths_bold.py --output documentation/phase_2026_widths_bold.png
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
    stroke,
    strokeWidth,
    line,
    saveImage,
)


FONT_PATH = "fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ,opsz,wdth,wght].ttf"

# Canvas is sized for an "a" rendered at a realistic display size
# (96pt) rather than at giant specimen scale, so the reader sees the
# typeface at something like its in-use proportions.
WIDTH = 1600
HEIGHT = 480
MARGIN = 60
GLYPH = "a"
GLYPH_SIZE = 96

# Three corners on the wdth axis at the current heaviest weight.
# Order: narrowest → medium → widest, drawn left-to-right.
CORNERS = [
    {
        "label": "Condensed",
        "wdth": 52,
        "wght": 700,
        "XTRA": 318.0,
        "XOPQ": 407.0,
        "YOPQ": 347.0,
    },
    {
        "label": "Normal",
        "wdth": 100,
        "wght": 700,
        "XTRA": 735.6,
        "XOPQ": 400.738,
        "YOPQ": 324.7,
    },
    {
        "label": "Ultra Extended",
        "wdth": 300,
        "wght": 700,
        "XTRA": 2369.9,
        "XOPQ": 619.7,
        "YOPQ": 362.0,
    },
]

LABEL_FONT = "Helvetica"
LABEL_SIZE = 14
SUBLABEL_SIZE = 11


def render(output_path: Path) -> None:
    newDrawing()
    newPage(WIDTH, HEIGHT)

    # White background
    fill(1, 1, 1)
    rect(0, 0, WIDTH, HEIGHT)

    # Glyph baseline — same for all three so the eye reads the width
    # difference directly.
    baseline_y = MARGIN + 180

    # Three columns
    column_width = (WIDTH - 2 * MARGIN) / 3

    for i, corner in enumerate(CORNERS):
        cx = MARGIN + column_width * (i + 0.5)

        # Render glyph centered horizontally within its column
        fill(0)
        font(FONT_PATH)
        fontSize(GLYPH_SIZE)
        fontVariations(
            XTRA=corner["XTRA"],
            XOPQ=corner["XOPQ"],
            YOPQ=corner["YOPQ"],
        )

        glyph_w, _ = textSize(GLYPH)
        text(GLYPH, (cx - glyph_w / 2, baseline_y))

        # Caption below
        caption_y = MARGIN + 60
        fill(0)
        font(LABEL_FONT)
        fontSize(LABEL_SIZE)
        label_w, _ = textSize(corner["label"])
        text(corner["label"], (cx - label_w / 2, caption_y))

        # Sub-caption with the parametric coordinates
        fontSize(SUBLABEL_SIZE)
        sub = f"wght {corner['wght']}, wdth {corner['wdth']}"
        sub_w, _ = textSize(sub)
        fill(0.4)
        text(sub, (cx - sub_w / 2, caption_y - 16))

        sub2 = f"XOPQ {corner['XOPQ']:.0f}  XTRA {corner['XTRA']:.0f}  YOPQ {corner['YOPQ']:.0f}"
        sub2_w, _ = textSize(sub2)
        text(sub2, (cx - sub2_w / 2, caption_y - 30))

    # Thin separator at the very top so the image reads as a single panel
    stroke(0.85)
    strokeWidth(1)
    line((MARGIN, HEIGHT - MARGIN), (WIDTH - MARGIN, HEIGHT - MARGIN))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    saveImage(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        metavar="PNG",
        default="documentation/phase_2026_widths_bold.png",
        help="where to write the PNG file",
    )
    args = parser.parse_args()

    render(Path(args.output))


if __name__ == "__main__":
    main()
