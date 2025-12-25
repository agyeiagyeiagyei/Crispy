#!/usr/bin/env python3
"""
gen_stat.py

Generate a STAT table YAML section from the CSV mappings.

Based on the traditional axes (wght, wdth, opsz) in the CSV.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Set

import yaml  # PyYAML


def _load_font_key_from_config(config_path: Path) -> str:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config.yaml did not parse to a mapping/dict")

    fvar = data.get("fvarInstances")
    if not isinstance(fvar, dict) or not fvar:
        raise ValueError("config.yaml is missing 'fvarInstances' or it is empty")

    keys = list(fvar.keys())
    if len(keys) != 1:
        raise ValueError(
            f"Found {len(keys)} fvarInstances keys in config.yaml; "
            f"use --font-key to choose one. Keys: {keys}"
        )
    return keys[0]


def extract_axis_values_from_csv(csv_path: Path) -> Dict[str, Set[int]]:
    """Extract unique axis values from CSV."""
    wght_vals = set()
    wdth_vals = set()
    opsz_vals = set()
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wght_vals.add(int(float(row["WGHT-e"])))
            wdth_vals.add(int(float(row["WDTH-e"])))
            opsz_vals.add(int(float(row["OPSZ-e"])))
    
    return {
        "wght": sorted(wght_vals),
        "wdth": sorted(wdth_vals),
        "opsz": sorted(opsz_vals),
    }


def get_weight_name(value: int) -> str:
    """Map weight value to STAT name."""
    names = {
        100: "Thin",
        200: "ExtraLight",
        300: "Light",
        400: "Regular",
        500: "Medium",
        600: "SemiBold",
        700: "Bold",
        800: "ExtraBold",
        900: "Black",
    }
    return names.get(value, str(value))


def get_width_name(value: int) -> str:
    """Map width value to STAT name."""
    names = {
        40: "Condensed",
        100: "Normal",
        160: "Extended",
        220: "Ultra Extended",
    }
    return names.get(value, str(value))


def generate_stat_yaml(
    axis_values: Dict[str, list[int]],
    font_key: str,
) -> str:
    """Generate STAT table YAML section."""
    lines = []
    lines.append("stat:")
    lines.append(f"  {font_key}:")
    
    # Optical Size axis
    lines.append("  - name: Optical Size")
    lines.append("    tag: opsz")
    lines.append("    values:")
    for opsz_val in axis_values["opsz"]:
        lines.append(f"    - name: {opsz_val}pt")
        lines.append(f"      value: {opsz_val}")
    
    # Width axis
    lines.append("  - name: Width")
    lines.append("    tag: wdth")
    lines.append("    values:")
    for wdth_val in axis_values["wdth"]:
        lines.append(f"    - name: {get_width_name(wdth_val)}")
        lines.append(f"      value: {wdth_val}")
    
    # Weight axis
    lines.append("  - name: Weight")
    lines.append("    tag: wght")
    lines.append("    values:")
    for wght_val in axis_values["wght"]:
        weight_name = get_weight_name(wght_val)
        lines.append(f"    - name: {weight_name}")
        lines.append(f"      value: {wght_val}")
        # Style linking: Regular (400) links to Bold (700)
        if wght_val == 400:
            lines.append("      linkedValue: 700")
            lines.append("      flags: 2")
    
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate STAT table section from CSV mappings."
    )
    ap.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path to CSV exported from spreadsheet.",
    )
    ap.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to existing config.yaml (font key read from fvarInstances).",
    )
    ap.add_argument(
        "--font-key",
        default=None,
        help="Override font key (otherwise auto-detected from config fvarInstances).",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stat.yaml in same folder as CSV).",
    )
    args = ap.parse_args(argv)

    if args.font_key:
        font_key = args.font_key
    else:
        font_key = _load_font_key_from_config(args.config)

    axis_values = extract_axis_values_from_csv(args.csv)
    out = generate_stat_yaml(axis_values, font_key)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.csv.parent / "stat.yaml"

    output_path.write_text(out, encoding="utf-8")
    print(f"Generated STAT section: {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

