#!/usr/bin/env python3
"""
Test script to generate MinOPSZ and MaxOPSZ rows from base CSV.
This is a standalone test before integrating into update_config.py.
"""

import csv
import yaml
from pathlib import Path
from decimal import Decimal
from typing import Dict, List, Tuple

def interpolate_multiplier(weight: int, axis: str, weight_points: List[Dict]) -> Tuple[float, float]:
    """Interpolate multiplier for given weight and axis (xopq or yopq)."""
    # Sort weight points by weight
    sorted_points = sorted(weight_points, key=lambda x: x['weight'])
    
    if weight <= sorted_points[0]['weight']:
        return (
            sorted_points[0]['min_opsz_multipliers'][axis],
            sorted_points[0]['max_opsz_multipliers'][axis]
        )
    if weight >= sorted_points[-1]['weight']:
        return (
            sorted_points[-1]['min_opsz_multipliers'][axis],
            sorted_points[-1]['max_opsz_multipliers'][axis]
        )
    
    # Find interpolation points
    for i in range(len(sorted_points) - 1):
        w1, w2 = sorted_points[i]['weight'], sorted_points[i+1]['weight']
        if w1 <= weight <= w2:
            # Linear interpolation
            t = (weight - w1) / (w2 - w1)
            min_m1 = sorted_points[i]['min_opsz_multipliers'][axis]
            min_m2 = sorted_points[i+1]['min_opsz_multipliers'][axis]
            max_m1 = sorted_points[i]['max_opsz_multipliers'][axis]
            max_m2 = sorted_points[i+1]['max_opsz_multipliers'][axis]
            min_mult = min_m1 + (min_m2 - min_m1) * t
            max_mult = max_m1 + (max_m2 - max_m1) * t
            return min_mult, max_mult
    
    return 1.0, 1.0


def generate_opsz_rows(csv_path: Path, opsz_config_path: Path, output_path: Path):
    """Generate MinOPSZ and MaxOPSZ rows from base CSV."""
    # Load opsz config
    with opsz_config_path.open('r') as f:
        config = yaml.safe_load(f)
    
    base_opsz = config['base_opsz']
    min_opsz = config['min_opsz']
    max_opsz = config['max_opsz']
    weight_points = config['weight_adjustments']
    xtra_condensed = config['xtra_adjustments']['condensed_widths']
    
    # Read base CSV
    rows = []
    with csv_path.open('r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)
    
    # Generate new rows
    new_rows = []
    
    for row in rows:
        # Keep base row (OPSZ=48)
        base_row = row.copy()
        new_rows.append(base_row)
        
        # Get values
        wght = int(row['WGHT'])
        wdth = int(row['WDTH'])
        base_xopq = float(row['XOPQ'])
        base_yopq = float(row['YOPQ'])
        base_xtra = float(row['XTRA'])
        instance_name = row['Instance Name']
        
        # Get multipliers
        min_xopq_mult, max_xopq_mult = interpolate_multiplier(wght, 'xopq', weight_points)
        min_yopq_mult, max_yopq_mult = interpolate_multiplier(wght, 'yopq', weight_points)
        
        # Apply XTRA adjustments for condensed
        min_xtra_mult = xtra_condensed['min_opsz_multiplier'] if wdth < 100 else 1.0
        max_xtra_mult = xtra_condensed['max_opsz_multiplier'] if wdth < 100 else 1.0
        
        # Calculate adjusted values
        min_xopq = base_xopq * min_xopq_mult
        max_xopq = base_xopq * max_xopq_mult
        min_yopq = base_yopq * min_yopq_mult
        max_yopq = base_yopq * max_yopq_mult
        min_xtra = base_xtra * min_xtra_mult
        max_xtra = base_xtra * max_xtra_mult
        
        # Create MinOPSZ row
        min_row = row.copy()
        min_row['Instance Name'] = f"{instance_name}-MinOPSZ"
        min_row['OPSZ'] = str(min_opsz)
        min_row['XOPQ'] = f"{min_xopq:.3f}"
        min_row['YOPQ'] = f"{min_yopq:.3f}"
        min_row['XTRA'] = f"{min_xtra:.3f}"
        new_rows.append(min_row)
        
        # Create MaxOPSZ row
        max_row = row.copy()
        max_row['Instance Name'] = f"{instance_name}-MaxOPSZ"
        max_row['OPSZ'] = str(max_opsz)
        max_row['XOPQ'] = f"{max_xopq:.3f}"
        max_row['YOPQ'] = f"{max_yopq:.3f}"
        max_row['XTRA'] = f"{max_xtra:.3f}"
        new_rows.append(max_row)
    
    # Write output
    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    
    return new_rows


if __name__ == '__main__':
    csv_path = Path('sources/avar2-mappings-opsz-test.csv')
    opsz_config_path = Path('sources/opsz.yaml')
    output_path = Path('sources/avar2-mappings-opsz-test-output.csv')
    
    print("=== Generating OPSZ Rows ===")
    print(f"Input: {csv_path}")
    print(f"Config: {opsz_config_path}")
    print(f"Output: {output_path}")
    print()
    
    new_rows = generate_opsz_rows(csv_path, opsz_config_path, output_path)
    
    print(f"✅ Generated {len(new_rows)} rows (from {len(new_rows)//3} base rows)")
    print()
    print("=== Sample Rows (first 9 rows) ===")
    for i, row in enumerate(new_rows[:9], 1):
        print(f"{i:2d}. {row['Instance Name']:30s} | OPSZ={row['OPSZ']:2s} | XOPQ={row['XOPQ']:7s} | YOPQ={row['YOPQ']:7s} | XTRA={row['XTRA']:7s}")
    
    print()
    print("=== Sample by Weight (wdth=100) ===")
    for wght in [200, 400, 700, 900]:
        for row in new_rows:
            if int(row['WGHT']) == wght and int(row['WDTH']) == 100:
                print(f"{row['Instance Name']:30s} | OPSZ={row['OPSZ']:2s} | XOPQ={row['XOPQ']:7s} | YOPQ={row['YOPQ']:7s} | XTRA={row['XTRA']:7s}")
    
    print()
    print("=== Condensed Example (wdth=40) ===")
    for row in new_rows:
        if int(row['WGHT']) == 400 and int(row['WDTH']) == 40:
            print(f"{row['Instance Name']:30s} | OPSZ={row['OPSZ']:2s} | XOPQ={row['XOPQ']:7s} | YOPQ={row['YOPQ']:7s} | XTRA={row['XTRA']:7s}")
    
    print()
    print(f"✅ Output written to: {output_path}")
