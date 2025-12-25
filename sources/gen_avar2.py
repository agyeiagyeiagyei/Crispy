#!/usr/bin/env python3
"""
gen_avar2.py

Generate an `avar2:` YAML section from a CSV exported from your spreadsheet.

Rules:
- "Instance Name" column is used ONLY for YAML comments.
- Columns ending with "-e" are non-parametric ("traditional") axes -> `in:` (strip "-e", lowercase).
- All other columns (except "Instance Name") are parametric axes -> `out:` (preserve CSV header order).
- SPAC is OPTIONAL:
    - If SPAC column exists, it is treated like any other parametric axis (must be populated; blanks error).
    - If SPAC column does not exist, that's fine.
- No blanks allowed for any parametric axis column that exists in the CSV header (for any non-empty row).
- Sorting/grouping:
    primary: wdth
    secondary: wght
    tertiary: -opsz  (so 72 before 12)
- Error on duplicate `in:` coordinate tuples.
- Output ONLY the `avar2:` section, wrapped under the font key.
- Font key is pulled from config.yaml's `fvarInstances` keys (must be exactly 1 unless --font-key override is used).
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import yaml  # PyYAML


@dataclass(frozen=True)
class RowMapping:
    instance_name: str
    in_axes: Dict[str, Decimal]      # from *-e columns
    out_axes: Dict[str, Decimal]     # parametric columns (non *-e)
    out_axis_order: Tuple[str, ...]  # preserve CSV header order for out:


def _is_blank(v: Optional[str]) -> bool:
    return v is None or str(v).strip() == ""


def _parse_decimal(raw: str, *, context: str) -> Decimal:
    s = str(raw).strip()
    if s == "":
        raise ValueError(f"Blank numeric value for {context}")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Non-numeric value '{raw}' for {context}")


def _normalize_in_axis_name(col: str) -> str:
    # "WGHT-e" -> "wght"
    return col[:-2].strip().lower()


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


def _detect_columns(fieldnames: List[str]) -> Tuple[str, List[str], List[str]]:
    name_col = "Instance Name"
    if name_col not in fieldnames:
        raise ValueError(f"CSV must include a '{name_col}' column. Found: {fieldnames}")

    in_cols = [c for c in fieldnames if c.endswith("-e")]
    if not in_cols:
        raise ValueError("CSV contains no '*-e' columns; cannot build 'in:' locations")

    # Parametric columns are everything else (except name and *-e)
    out_cols = [c for c in fieldnames if c not in (name_col,) and c not in in_cols]
    if not out_cols:
        raise ValueError("CSV contains no parametric axis columns for 'out:'")

    return name_col, in_cols, out_cols


def read_csv_mappings(csv_path: Path) -> List[RowMapping]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        fieldnames = [h.strip() for h in reader.fieldnames]
        name_col, in_cols, out_cols = _detect_columns(fieldnames)
        out_order = tuple(out_cols)

        mappings: List[RowMapping] = []

        for line_no, row in enumerate(reader, start=2):  # header is line 1
            # Strip header keys
            row = {k.strip(): (v if v is not None else "") for k, v in row.items()}

            # Skip fully empty rows
            if all(_is_blank(row.get(c, "")) for c in fieldnames):
                continue

            inst_name = str(row.get(name_col, "")).strip()
            if _is_blank(inst_name):
                raise ValueError(f"Line {line_no}: '{name_col}' is blank")

            # Build in_axes (allow blanks generally, but required sort axes enforced later)
            in_axes: Dict[str, Decimal] = {}
            for c in in_cols:
                raw = row.get(c, "")
                if _is_blank(raw):
                    continue
                in_axes[_normalize_in_axis_name(c)] = _parse_decimal(raw, context=f"line {line_no} / {c}")

            # Build out_axes (STRICT: no blanks for any parametric column that exists)
            out_axes: Dict[str, Decimal] = {}
            for c in out_cols:
                raw = row.get(c, "")
                if _is_blank(raw):
                    raise ValueError(f"Line {line_no}: parametric axis '{c}' is blank (not allowed)")
                out_axes[c] = _parse_decimal(raw, context=f"line {line_no} / {c}")

            # Required sort/group axes must exist and be populated on every non-empty row
            for required in ("wght", "wdth", "opsz"):
                if required not in in_axes:
                    raise ValueError(
                        f"Line {line_no}: missing required traditional axis '{required}' "
                        f"(need {required.upper()}-e value for sorting/grouping)"
                    )

            mappings.append(
                RowMapping(
                    instance_name=inst_name,
                    in_axes=in_axes,
                    out_axes=out_axes,
                    out_axis_order=out_order,
                )
            )

        return mappings


def _dedupe_check(mappings: List[RowMapping]) -> None:
    # Dedup by full set of in_axes on the row (sorted by axis name)
    seen: Dict[Tuple[Tuple[str, str], ...], str] = {}
    for m in mappings:
        key = tuple((k, str(v)) for k, v in sorted(m.in_axes.items()))
        if key in seen:
            raise ValueError(
                "Duplicate 'in:' coordinates detected:\n"
                f"  First: {seen[key]}\n"
                f"  Second: {m.instance_name}\n"
                f"  Coords: {dict(key)}"
            )
        seen[key] = m.instance_name


def _sort_key(m: RowMapping) -> Tuple[Decimal, Decimal, Decimal]:
    # primary: wdth, secondary: wght, tertiary: -opsz (72 before 12)
    wdth = m.in_axes["wdth"]
    wght = m.in_axes["wght"]
    opsz = m.in_axes["opsz"]
    return (wdth, wght, -opsz)


def _fmt_decimal(d: Decimal) -> str:
    # ints as ints; decimals as trimmed fixed-point (no exponent)
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def generate_avar2_yaml_section(
    mappings: List[RowMapping],
    *,
    font_key: str,
    include_group_headers: bool = True,
) -> str:
    _dedupe_check(mappings)
    mappings = sorted(mappings, key=_sort_key)

    lines: List[str] = []
    lines.append("avar2:")
    lines.append(f"  {font_key}:")

    current_wdth: Optional[Decimal] = None
    current_opsz: Optional[Decimal] = None

    for m in mappings:
        wdth = m.in_axes["wdth"]
        opsz = m.in_axes["opsz"]

        if include_group_headers:
            if current_wdth is None or wdth != current_wdth:
                lines.append("")
                lines.append("  # =========================")
                lines.append(f"  # Width = {_fmt_decimal(wdth)}")
                lines.append("  # =========================")
                current_wdth = wdth
                current_opsz = None

            if current_opsz is None or opsz != current_opsz:
                lines.append("")
                lines.append(f"  # OPSZ = {_fmt_decimal(opsz)}")
                current_opsz = opsz

        lines.append("")
        lines.append(f"  # {m.instance_name}")
        lines.append("  - in:")

        # Stable ordering for in: (sorted by axis name)
        for k in sorted(m.in_axes.keys()):
            lines.append(f"      {k}: {_fmt_decimal(m.in_axes[k])}")

        lines.append("    out:")
        # Preserve out-axis order from CSV header; include only parametric axes
        for k in m.out_axis_order:
            lines.append(f"      {k}: {_fmt_decimal(m.out_axes[k])}")

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate avar2 section from a CSV mapping sheet.")
    ap.add_argument("--csv", required=True, type=Path, help="Path to CSV exported from spreadsheet.")
    ap.add_argument("--config", required=True, type=Path, help="Path to existing config.yaml (font key read from fvarInstances).")
    ap.add_argument("--font-key", default=None, help="Override font key (otherwise auto-detected from config fvarInstances).")
    ap.add_argument("--no-group-headers", action="store_true", help="Disable group header comments (Width/OPSZ).")
    ap.add_argument("--output", type=Path, default=None, help="Output file path (default: avar2.yaml in same folder as CSV).")
    args = ap.parse_args(argv)

    if args.font_key:
        font_key = args.font_key
    else:
        font_key = _load_font_key_from_config(args.config)

    mappings = read_csv_mappings(args.csv)
    out = generate_avar2_yaml_section(
        mappings,
        font_key=font_key,
        include_group_headers=not args.no_group_headers,
    )
    
    # Determine output path: use --output if provided, otherwise avar2.yaml in CSV's directory
    if args.output:
        output_path = args.output
    else:
        output_path = args.csv.parent / "avar2.yaml"
    
    output_path.write_text(out, encoding="utf-8")
    print(f"Generated avar2 section: {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

