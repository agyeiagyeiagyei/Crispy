#!/usr/bin/env python3
"""
expand_contrast.py

Expand CSV with contrast variations using dynamic gap scaling.

This script takes a base CSV and generates contrast variations (cntr=-10, 0, +10)
by applying asymmetric gap scaling formulas that adjust XOPQ and YOPQ based on
width and weight for optimal visual contrast.

Features:
- Asymmetric scaling: different factors for negative vs positive contrast
- Dynamic splitting: adjusts XOPQ/YOPQ changes based on width and weight
- Preserves all other CSV columns
- Adds CONTRAST-e column and modifies Instance Name with suffixes
"""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional


def expand_csv_with_contrast(
    csv_path: Path,
    output_path: Optional[Path] = None,
    reduction_factor: Decimal = Decimal("0.75"),
    fixed_offset: Decimal = Decimal("0"),
    negative_factor: Optional[Decimal] = None,
    negative_offset: Optional[Decimal] = None,
    positive_factor: Optional[Decimal] = None,
    positive_offset: Optional[Decimal] = None,
) -> Path:
    """
    Expand CSV with contrast variations using adaptive gap scaling.
    
    For each row, creates 3 rows:
    - CONTRAST-e = -10: Reduce gap using hybrid formula with dynamic XOPQ/YOPQ splitting
    - CONTRAST-e = 0: Original values
    - CONTRAST-e = +10: Increase gap using hybrid formula with dynamic XOPQ/YOPQ splitting
    
    Gap change formula: gap_change = base_gap * factor + offset
    
    If asymmetric factors/offsets are provided, they override the symmetric reduction_factor/fixed_offset.
    This allows different scaling for negative vs positive contrast to balance perceptual impact.
    
    Dynamic splitting:
    - Negative contrast (cntr=-10): Narrower + bolder → reduce XOPQ more
    - Positive contrast (cntr=+10): Wider + bolder → reduce YOPQ more
    
    Returns path to expanded CSV.
    """
    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_with_contrast{csv_path.suffix}"
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        
        # Check if CONTRAST or CONTRAST-e already exists
        contrast_col = "CONTRAST" if "CONTRAST" in fieldnames else "CONTRAST-e"
        if contrast_col not in fieldnames:
            # Insert CONTRAST after OPSZ (before parametric axes)
            # Support both "OPSZ" and "OPSZ-e" (legacy)
            opsz_col = "OPSZ" if "OPSZ" in fieldnames else "OPSZ-e"
            try:
                opsz_idx = fieldnames.index(opsz_col)
                fieldnames.insert(opsz_idx + 1, "CONTRAST")
            except ValueError:
                # OPSZ not found, append to end of traditional axis columns
                in_cols = [c for c in fieldnames if c in ("WGHT", "WDTH", "OPSZ") or c.endswith("-e")]
                if in_cols:
                    last_in_idx = fieldnames.index(in_cols[-1])
                    fieldnames.insert(last_in_idx + 1, "CONTRAST")
                else:
                    fieldnames.insert(1, "CONTRAST")
        
        rows = list(reader)
    
    expanded_rows = []
    for row in rows:
        xopq_orig = Decimal(str(row.get("XOPQ", "0")))
        yopq_orig = Decimal(str(row.get("YOPQ", "0")))
        
        # Create three variations
        original_name = row.get("Instance Name", "").strip()
        
        for contrast_val in [-10, 0, 10]:
            new_row = row.copy()
            contrast_col = "CONTRAST" if "CONTRAST" in fieldnames else "CONTRAST-e"
            new_row[contrast_col] = str(contrast_val)
            
            if contrast_val == 0:
                # Normal contrast (0): keep original values unchanged
                new_row["Instance Name"] = original_name
                new_row["XOPQ"] = str(xopq_orig)
                new_row["YOPQ"] = str(yopq_orig)
            elif contrast_val == -10:
                # Less contrast: reduce gap using hybrid formula with dynamic splitting
                gap_orig = xopq_orig - yopq_orig
                
                # Extract width and weight for dynamic splitting
                wdth_col = "WDTH" if "WDTH" in row else "WDTH-e"
                wght_col = "WGHT" if "WGHT" in row else "WGHT-e"
                wdth = Decimal(str(row.get(wdth_col, "100")))
                wght = Decimal(str(row.get(wght_col, "400")))
                
                # Normalize width and weight to 0-1 range
                # Width range: 40 (Condensed) to 220 (Ultra Extended)
                # Weight range: 200 (ExtraLight) to 900 (Black)
                wdth_norm = (wdth - Decimal("40")) / (Decimal("220") - Decimal("40"))
                wght_norm = (wght - Decimal("200")) / (Decimal("900") - Decimal("200"))
                wdth_norm = max(Decimal("0"), min(Decimal("1"), wdth_norm))  # Clamp to 0-1
                wght_norm = max(Decimal("0"), min(Decimal("1"), wght_norm))  # Clamp to 0-1
                
                new_row["Instance Name"] = f"{original_name} Contrast-Min"
                # Calculate gap change using hybrid formula
                if negative_factor is not None and negative_offset is not None:
                    gap_change = gap_orig * negative_factor + negative_offset
                else:
                    gap_change = gap_orig * reduction_factor + fixed_offset
                
                # Dynamic splitting: narrower + bolder → reduce XOPQ more
                # Combine width (inverted: narrower = lower) and weight
                # Narrower means lower wdth_norm, bolder means higher wght_norm
                # For negative contrast: we want to favor XOPQ reduction when (1 - wdth_norm) is high AND wght_norm is high
                xopq_weight = ((Decimal("1") - wdth_norm) + wght_norm) / Decimal("2")
                xopq_weight = Decimal("0.3") + xopq_weight * Decimal("0.4")  # Range: 0.3 to 0.7 (30-70% to XOPQ)
                
                xopq_delta = gap_change * xopq_weight
                yopq_delta = gap_change - xopq_delta
                
                new_row["XOPQ"] = str(xopq_orig - xopq_delta)
                new_row["YOPQ"] = str(yopq_orig + yopq_delta)
            else:  # contrast_val == 10
                # More contrast: increase gap using hybrid formula with dynamic splitting
                gap_orig = xopq_orig - yopq_orig
                
                # Extract width and weight for dynamic splitting
                wdth_col = "WDTH" if "WDTH" in row else "WDTH-e"
                wght_col = "WGHT" if "WGHT" in row else "WGHT-e"
                wdth = Decimal(str(row.get(wdth_col, "100")))
                wght = Decimal(str(row.get(wght_col, "400")))
                
                # Normalize width and weight to 0-1 range
                # Width range: 40 (Condensed) to 220 (Ultra Extended)
                # Weight range: 200 (ExtraLight) to 900 (Black)
                wdth_norm = (wdth - Decimal("40")) / (Decimal("220") - Decimal("40"))
                wght_norm = (wght - Decimal("200")) / (Decimal("900") - Decimal("200"))
                wdth_norm = max(Decimal("0"), min(Decimal("1"), wdth_norm))  # Clamp to 0-1
                wght_norm = max(Decimal("0"), min(Decimal("1"), wght_norm))  # Clamp to 0-1
                
                new_row["Instance Name"] = f"{original_name} Contrast-Max"
                
                # Calculate gap change using hybrid formula
                if positive_factor is not None and positive_offset is not None:
                    gap_change = gap_orig * positive_factor + positive_offset
                else:
                    gap_change = gap_orig * reduction_factor + fixed_offset
                
                # Dynamic splitting: wider + bolder → reduce YOPQ more
                # Combine width and weight for YOPQ reduction weight
                # Wider means higher wdth_norm, bolder means higher wght_norm
                yopq_weight = (wdth_norm + wght_norm) / Decimal("2")
                yopq_weight = Decimal("0.3") + yopq_weight * Decimal("0.4")  # Range: 0.3 to 0.7 (30-70% to YOPQ)
                
                yopq_delta = gap_change * yopq_weight
                xopq_delta = gap_change - yopq_delta
                
                new_row["XOPQ"] = str(xopq_orig + xopq_delta)
                new_row["YOPQ"] = str(yopq_orig - yopq_delta)
            
            expanded_rows.append(new_row)
    
    # Write expanded CSV
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(expanded_rows)
    
    return output_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Expand CSV with contrast variations using dynamic gap scaling."
    )
    ap.add_argument("--csv", required=True, type=Path, help="Path to input CSV file.")
    ap.add_argument("--output", type=Path, help="Path to output CSV (default: <input>_with_contrast.csv).")
    ap.add_argument(
        "--negative-factor",
        type=Decimal,
        default=Decimal("1.20"),
        help="Factor for negative contrast (default: 1.20 = 120%%).",
    )
    ap.add_argument(
        "--negative-offset",
        type=Decimal,
        default=Decimal("60"),
        help="Fixed offset for negative contrast (default: 60).",
    )
    ap.add_argument(
        "--positive-factor",
        type=Decimal,
        default=Decimal("0.85"),
        help="Factor for positive contrast (default: 0.85 = 85%%).",
    )
    ap.add_argument(
        "--positive-offset",
        type=Decimal,
        default=Decimal("30"),
        help="Fixed offset for positive contrast (default: 30).",
    )
    args = ap.parse_args(argv)
    
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        return 1
    
    try:
        output_path = expand_csv_with_contrast(
            args.csv,
            output_path=args.output,
            negative_factor=args.negative_factor,
            negative_offset=args.negative_offset,
            positive_factor=args.positive_factor,
            positive_offset=args.positive_offset,
        )
        print(f"Expanded CSV written to: {output_path}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

