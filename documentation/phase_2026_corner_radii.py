"""Compose the corner-radii side-by-side panel for PHASE_2026.md section 1a.

Takes the four corner-detail screenshots from disk and joins them
horizontally into a single image. Heights are normalised to the
shortest input so the panel reads as one row.

Run from the repo root:

    python3 documentation/phase_2026_corner_radii.py --output documentation/phase_2026_corner_radii.png
"""

import argparse
from pathlib import Path

from PIL import Image


# Source screenshots, left-to-right in the panel. Order chosen to
# read as a narrative: a corner that's gone almost flat → a corner
# that's gone almost square → a within-master mismatch (rounded vs
# square in the same form) → a generously-rounded reference corner.
# Globbed because macOS inserts U+202F (narrow no-break space) into
# screenshot filenames between the time and "PM", so explicit string
# matching is fragile.
DESKTOP = Path("/Users/agyei/Desktop")
TIMES = ["4.05.35", "4.05.13", "4.05.46", "4.05.22"]


def _resolve(time_str: str) -> Path:
    matches = list(DESKTOP.glob(f"Screenshot 2026-06-06*{time_str}*.png"))
    if not matches:
        raise FileNotFoundError(f"No screenshot matching time {time_str}")
    return matches[0]


SOURCES = [_resolve(t) for t in TIMES]

GAP = 12               # px of white spacing between panels
PAD = 24               # px of white border around the whole strip
BG = (255, 255, 255)
TARGET_HEIGHT = 600    # px — every panel is scaled to this height


def compose(sources, output: Path) -> None:
    imgs = [Image.open(p).convert("RGB") for p in sources]
    scaled = []
    for img in imgs:
        scale = TARGET_HEIGHT / img.height
        new_w = int(round(img.width * scale))
        scaled.append(img.resize((new_w, TARGET_HEIGHT), Image.LANCZOS))

    total_w = sum(i.width for i in scaled) + GAP * (len(scaled) - 1) + 2 * PAD
    total_h = TARGET_HEIGHT + 2 * PAD

    panel = Image.new("RGB", (total_w, total_h), BG)
    x = PAD
    for i, img in enumerate(scaled):
        panel.paste(img, (x, PAD))
        x += img.width
        if i < len(scaled) - 1:
            x += GAP

    output.parent.mkdir(parents=True, exist_ok=True)
    panel.save(output, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        metavar="PNG",
        default="documentation/phase_2026_corner_radii.png",
        help="where to write the PNG file",
    )
    args = parser.parse_args()
    compose(SOURCES, Path(args.output))


if __name__ == "__main__":
    main()
