#!/usr/bin/env python3
"""
gen_instances.py

Generate an `instances:` YAML section from CSV mappings for static font instances.

Parses instance names to determine familyName (with width variants) and styleName (weight).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

import yaml  # PyYAML


@dataclass
class InstanceDef:
    family_name: str
    style_name: str
    coordinates: Dict[str, Decimal]


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


def _get_family_name(base_family: str = "Crispy") -> str:
    """Family name is always just the base family name."""
    return base_family


def _get_style_name(instance_name: str) -> str:
    """Extract style name from instance name - use CSV name exactly as provided."""
    # Use the instance name directly from CSV - it already has the correct format
    return instance_name.strip()


def _fmt_decimal(d: Decimal) -> str:
    """Format decimal for YAML output."""
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def read_csv_instances(
    csv_path: Path,
    base_family: str = "Crispy",
) -> List[InstanceDef]:
    """Read CSV and convert to instance definitions."""
    instances: List[InstanceDef] = []
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            instance_name = row["Instance Name"].strip()
            if not instance_name:
                continue
            
            coordinates = {
                "opsz": Decimal(row["OPSZ-e"]),
                "wdth": Decimal(row["WDTH-e"]),
                "wght": Decimal(row["WGHT-e"]),
            }
            
            family_name = _get_family_name(base_family)
            style_name = _get_style_name(instance_name)
            
            instances.append(
                InstanceDef(
                    family_name=family_name,
                    style_name=style_name,
                    coordinates=coordinates,
                )
            )
    
    return instances


def generate_instances_yaml(
    instances: List[InstanceDef],
    font_key: str,
) -> str:
    """Generate instances YAML section."""
    lines = []
    lines.append("instances:")
    lines.append(f"  {font_key}:")
    
    for inst in instances:
        lines.append("  - familyName: " + f'"{inst.family_name}"')
        lines.append(f"    styleName: {inst.style_name}")
        lines.append("    coordinates:")
        # Order: opsz, wdth, wght (matching typical axis order)
        for axis in ["opsz", "wdth", "wght"]:
            lines.append(f"      {axis}: {_fmt_decimal(inst.coordinates[axis])}")
    
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate static instances section from CSV mappings."
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
        "--family-name",
        default="Crispy",
        help="Base family name (default: Crispy).",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: instances.yaml in same folder as CSV).",
    )
    args = ap.parse_args(argv)

    if args.font_key:
        font_key = args.font_key
    else:
        font_key = _load_font_key_from_config(args.config)

    instances = read_csv_instances(args.csv, base_family=args.family_name)
    out = generate_instances_yaml(instances, font_key)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.csv.parent / "instances.yaml"

    output_path.write_text(out, encoding="utf-8")
    print(f"Generated instances section: {output_path}", file=sys.stderr)
    print(f"Total instances: {len(instances)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

