"""Generate animated GIFs for the parametric axes in DESIGNSPACE.md.

Each GIF demonstrates one parametric axis in isolation: every other
parametric axis is pinned at its minimum and the target axis sweeps
from min to max and back (ping-pong). The intent is for a reader of
DESIGNSPACE.md to see what each axis actually does, decoupled from
the others.

XOPQ / YOPQ / XTRA animations use a single ``O`` (the canonical shape
for showing horizontal/vertical opacity and horizontal counter).
The SPAC animation uses ``OO`` because spacing is only visible
between two glyphs.

Run from the repo root:

    # one axis
    python3 documentation/phase_2026_param_axes.py --axis XOPQ

    # all four
    python3 documentation/phase_2026_param_axes.py --axis all
"""

import argparse
import tempfile
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
from PIL import Image, ImageChops


FONT_PATH = "fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ,opsz,wdth,wght].ttf"

# Axis ranges, in order they appear in DESIGNSPACE.md.
# Values are taken from the *fvar* table of the shipped font, not the
# avar2-studio metadata — speaking to reality. Notable: SPAC actually
# runs -100 to 110 in the font (the metadata says -1000 to 1000, both
# wrong); wght caps at 700 in fvar even though the metadata aspires
# to 900.
AXIS_SPECS = {
    "XOPQ": {"min": 2.0, "max": 1016.0},
    "YOPQ": {"min": 2.0, "max": 462.0},
    "XTRA": {"min": 94.0, "max": 3330.0},
    "SPAC": {"min": -100.0, "max": 110.0},
}

# Animation parameters
FRAMES = 30                # frames per direction
FRAME_DURATION_MS = 70     # per frame; ping-pong loop is ~4 seconds
CANVAS_W = 1000
CANVAS_H = 500
GLYPH_SIZE = 180


def _variation_for_frame(axis: str, t: float) -> dict:
    """Other parametric axes at minimum; the target axis at progress t."""
    variations = {name: spec["min"] for name, spec in AXIS_SPECS.items()}
    spec = AXIS_SPECS[axis]
    variations[axis] = spec["min"] + t * (spec["max"] - spec["min"])
    return variations


LABEL_FONT = "Helvetica"
LABEL_SIZE = 18
LABEL_GAP = 32
LABEL_SEPARATOR = "   "
TARGET_COLOR = 0.10   # near-black for the changing axis
FIXED_COLOR = 0.62    # mid-grey for the pinned axes


def _render_frame(axis: str, t: float, frame_path: Path) -> None:
    newDrawing()
    newPage(CANVAS_W, CANVAS_H)
    fill(1, 1, 1)
    rect(0, 0, CANVAS_W, CANVAS_H)

    variations = _variation_for_frame(axis, t)
    glyph_text = "OO" if axis == "SPAC" else "O"

    # Glyph — sits a bit above centre to leave room for the label below.
    fill(0)
    font(FONT_PATH)
    fontSize(GLYPH_SIZE)
    fontVariations(**variations)
    text_w, _ = textSize(glyph_text)
    text_x = (CANVAS_W - text_w) / 2
    glyph_baseline = CANVAS_H * 0.50
    text(glyph_text, (text_x, glyph_baseline))

    # Caption — show ALL four parametric axis values so the eye reads
    # that the others stay fixed at min while the target one sweeps.
    # The target axis is rendered in near-black; the fixed axes in
    # mid-grey so they recede visually.
    font(LABEL_FONT)
    fontSize(LABEL_SIZE)
    parts = []
    for ax_name in AXIS_SPECS.keys():
        val = variations[ax_name]
        part_text = f"{ax_name} {val:.1f}"
        part_w, _ = textSize(part_text)
        parts.append({
            "text": part_text,
            "width": part_w,
            "color": TARGET_COLOR if ax_name == axis else FIXED_COLOR,
        })

    sep_w, _ = textSize(LABEL_SEPARATOR)
    total_w = sum(p["width"] for p in parts) + sep_w * (len(parts) - 1)

    x_cursor = (CANVAS_W - total_w) / 2
    label_y = glyph_baseline - LABEL_GAP - LABEL_SIZE

    for i, p in enumerate(parts):
        fill(p["color"])
        text(p["text"], (x_cursor, label_y))
        x_cursor += p["width"]
        if i < len(parts) - 1:
            x_cursor += sep_w

    saveImage(str(frame_path))


def _union_bbox(images, pad: int = 16) -> tuple:
    """Compute the union of every frame's non-white bounding box.

    Each frame's content is the dark glyph on a white field; we diff
    against a white image of the same size so PIL's ``getbbox`` returns
    the bounding box of any non-white pixel. The union across all
    frames is the tightest crop that still shows every animation
    extreme.
    """
    bboxes = []
    for img in images:
        rgb = img.convert("RGB")
        white = Image.new("RGB", rgb.size, (255, 255, 255))
        diff = ImageChops.difference(rgb, white)
        bbox = diff.getbbox()
        if bbox:
            bboxes.append(bbox)
    if not bboxes:
        return (0, 0, images[0].width, images[0].height)

    left = max(0, min(b[0] for b in bboxes) - pad)
    upper = max(0, min(b[1] for b in bboxes) - pad)
    right = min(images[0].width, max(b[2] for b in bboxes) + pad)
    lower = min(images[0].height, max(b[3] for b in bboxes) + pad)
    return (left, upper, right, lower)


def make_gif(axis: str, output_path: Path) -> None:
    if axis not in AXIS_SPECS:
        raise ValueError(f"Unknown axis: {axis}")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for i in range(FRAMES):
            t = i / (FRAMES - 1)
            _render_frame(axis, t, tmpdir / f"frame_{i:03d}.png")

        forward = sorted(tmpdir.glob("frame_*.png"))
        # Ping-pong: append the reverse (excluding the endpoints to
        # avoid a one-frame pause at min and max).
        sequence = forward + forward[-2:0:-1]

        rgb_frames = [Image.open(p).convert("RGB") for p in sequence]
        crop = _union_bbox(rgb_frames)
        cropped = [im.crop(crop) for im in rgb_frames]
        images = [im.convert("P", palette=Image.ADAPTIVE) for im in cropped]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=FRAME_DURATION_MS,
            loop=0,
            optimize=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--axis",
        choices=list(AXIS_SPECS) + ["all"],
        default="all",
        help="Which axis to render (default: all four)",
    )
    parser.add_argument(
        "--output-dir",
        default="documentation",
        help="Where to write the .gif files",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    axes = [args.axis] if args.axis != "all" else list(AXIS_SPECS)
    for axis in axes:
        gif_path = out_dir / f"phase_2026_axis_{axis.lower()}.gif"
        print(f"Rendering {axis} → {gif_path}", flush=True)
        make_gif(axis, gif_path)
        print(f"  done ({gif_path.stat().st_size // 1024} KB)", flush=True)


if __name__ == "__main__":
    main()
