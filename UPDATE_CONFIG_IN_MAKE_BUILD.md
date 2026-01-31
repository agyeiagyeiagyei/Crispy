# How `update_config.py` Works in `make build`

## Overview

In `make build`, `update_config.py` is called **with the `--add-opsz` flag**, which expands the CSV with MinOPSZ and MaxOPSZ rows before generating STAT and avar2 sections. This is different from other uses where the CSV is used as-is.

## Build Flow in Makefile

### Complete `make build` Process

```makefile
build.stamp: venv sources/config.yaml sources/avar2-mappings.csv sources/Crispy.glyphs $(SOURCES)
	rm -rf fonts;
	. venv/bin/activate && \
	python3 scripts/sync-glyphs-to-avar2.py --glyphs sources/Crispy.glyphs --csv sources/avar2-mappings.csv --once && \
	python3 sources/update_config.py --csv sources/avar2-mappings.csv --config sources/config.yaml --no-backup --add-opsz && \
	(for config in sources/config*.yaml; do gftools builder --experimental-fontc $$(which fontc) $$config; done) && \
	touch build.stamp
```

**Steps:**
1. **Step 0:** Sync CSV from Glyphs file (`sync-glyphs-to-avar2.py`)
2. **Step 1:** Update config.yaml (`update_config.py` with `--add-opsz`) ← **This step**
3. **Steps 2-7:** Build fonts (`gftools builder`)

---

## Step-by-Step: `update_config.py` in `make build`

### Step 1: CSV Expansion with OPSZ (`--add-opsz` flag)

**Input CSV:** `sources/avar2-mappings.csv` (base OPSZ=48 rows only)

**Process:**
1. Reads `sources/opsz.yaml` configuration
2. For each CSV row with `OPSZ=48` (base opsz):
   - **Keeps base row** (OPSZ=48)
   - **Creates MinOPSZ row** (OPSZ=12) with adjusted XOPQ/YOPQ/XTRA
   - **Creates MaxOPSZ row** (OPSZ=72) with adjusted XOPQ/YOPQ/XTRA

**Example Transformation:**

**Input (1 row):**
```csv
Instance Name,WGHT,WDTH,OPSZ,XTRA,XOPQ,YOPQ
Thin Condensed,100,40,48,181.2,40.3,41.3
```

**Output (3 rows):**
```csv
Instance Name,WGHT,WDTH,OPSZ,XTRA,XOPQ,YOPQ,SPAC
Thin Condensed,100,40,48,181.2,40.3,41.3,0
Thin Condensed-MinOPSZ,100,40,12,190.26,42.315,43.365,20
Thin Condensed-MaxOPSZ,100,40,72,181.2,38.285,39.235,-20
```

**Adjustment Logic:**
- **XOPQ/YOPQ adjustments:** Based on weight (from `opsz.yaml` weight_adjustments)
  - Light weights (200): MinOPSZ gets +5%, MaxOPSZ gets -5%
  - Regular (400): No change (1.0x)
  - Bold (700): MinOPSZ gets -5%, MaxOPSZ gets +5%
  - Black (900): MinOPSZ gets -8%, MaxOPSZ gets +8%
- **XTRA adjustments:** Additional adjustment for condensed widths (wdth < 100)
  - Condensed: MinOPSZ gets +5% XTRA multiplier
  - Normal widths: No XTRA adjustment
- **SPAC values:** 
  - Base (OPSZ=48): SPAC = 0
  - MinOPSZ (OPSZ=12): SPAC = +20
  - MaxOPSZ (OPSZ=72): SPAC = -20

**Result:** CSV expands from ~64 rows to ~192 rows (64 base × 3 opsz variants)

---

### Step 2: Generate STAT Section

**Input:** Expanded CSV (with MinOPSZ/MaxOPSZ rows)

**Process:**
1. Extracts unique axis values from expanded CSV:
   - **OPSZ:** [12, 48, 72] (now has variation!)
   - **WDTH:** [40, 100, ...]
   - **WGHT:** [100, 200, 400, 700, 900, ...]
   - **CNTR:** (if present)

2. Generates STAT table structure:
   ```yaml
   stat:
     Crispy:
       - name: Optical Size
         tag: opsz
         values:
           - {name: "12pt", value: 12}
           - {name: "48pt", value: 48}
           - {name: "72pt", value: 72}
       - name: Width
         tag: wdth
         values:
           - {name: "Condensed", value: 40}
           - {name: "Normal", value: 100}
       - name: Weight
         tag: wght
         values:
           - {name: "Thin", value: 100}
           - {name: "Regular", value: 400, linkedValue: 700, flags: 2}
           - {name: "Bold", value: 700}
   ```

**Key Point:** Because CSV was expanded with `--add-opsz`, STAT now includes OPSZ axis with 3 values (12, 48, 72). Without `--add-opsz`, OPSZ would be skipped if all rows had the same value.

---

### Step 3: Generate avar2 Section

**Input:** Expanded CSV mappings (192 rows after OPSZ expansion)

**Process:**
1. Reads all mappings from expanded CSV
2. Groups by width and optical size (with comments)
3. Creates avar2 mappings: `in:` (traditional axes) → `out:` (parametric axes)

**Example Output:**
```yaml
avar2:
  Crispy:
    # =========================
    # Width = 40
    # =========================
    
    # OPSZ = 12
    # Thin Condensed-MinOPSZ
    - in:
        wght: 100
        wdth: 40
        opsz: 12
      out:
        XTRA: 190.26
        XOPQ: 42.315
        YOPQ: 43.365
    
    # OPSZ = 48
    # Thin Condensed
    - in:
        wght: 100
        wdth: 40
        opsz: 48
      out:
        XTRA: 181.2
        XOPQ: 40.3
        YOPQ: 41.3
    
    # OPSZ = 72
    # Thin Condensed-MaxOPSZ
    - in:
        wght: 100
        wdth: 40
        opsz: 72
      out:
        XTRA: 181.2
        XOPQ: 38.285
        YOPQ: 39.235
```

**Key Points:**
- **OPSZ is included** in `in:` because CSV now has variation (12, 48, 72)
- **192 mappings** total (64 base instances × 3 opsz variants)
- **SPAC is NOT included** in avar2 `out:` (SPAC is handled separately by gftools builder's AddSpacingAxis step)

---

### Step 4: Merge into config.yaml

**Process:**
1. Loads existing `sources/config.yaml`
2. Replaces `stat` section with generated STAT data
3. Replaces `avar2` section with generated avar2 mappings
4. Preserves all other config content (sources, familyName, fvarInstances, etc.)
5. Uses hybrid approach: writes most sections as YAML, injects pre-formatted avar2 string to preserve comments

**Output:** Updated `sources/config.yaml` ready for font build

---

## Why `--add-opsz` is Used in `make build`

### Purpose
The `--add-opsz` flag ensures that:
1. **STAT table includes OPSZ axis** - Font has proper optical size axis definition
2. **avar2 mappings include OPSZ** - Mappings work across all optical sizes
3. **Font supports full OPSZ range** - Users can interpolate between 12pt, 48pt, and 72pt

### Without `--add-opsz`
- CSV only has OPSZ=48 rows
- STAT table would skip OPSZ axis (no variation)
- avar2 mappings wouldn't include OPSZ in `in:` section
- Font would only support single optical size (48pt)

### With `--add-opsz` (Production Build)
- CSV expands to include OPSZ=12 and OPSZ=72 rows
- STAT table includes OPSZ axis with 3 values
- avar2 mappings include OPSZ in `in:` section
- Font supports full optical size range (12pt to 72pt)

---

## Configuration: `opsz.yaml`

The OPSZ expansion uses `sources/opsz.yaml` to determine:
- **Base OPSZ:** 48 (reference point)
- **Min OPSZ:** 12 (small text)
- **Max OPSZ:** 72 (large display)
- **Weight-based multipliers:** How XOPQ/YOPQ adjust based on weight
- **Condensed adjustments:** Extra XTRA adjustment for condensed widths

**Example multipliers (from opsz.yaml):**
- Weight 200 (ExtraLight): MinOPSZ +5%, MaxOPSZ -5%
- Weight 400 (Regular): MinOPSZ 1.0x, MaxOPSZ 1.0x (no change)
- Weight 700 (Bold): MinOPSZ -5%, MaxOPSZ +5%
- Weight 900 (Black): MinOPSZ -8%, MaxOPSZ +8%

---

## Complete Flow Summary

```
make build
  │
  ├─ Step 0: sync-glyphs-to-avar2.py
  │   └─ Updates CSV with latest Glyphs file data
  │
  ├─ Step 1: update_config.py --add-opsz
  │   ├─ Expands CSV: 64 rows → 192 rows (adds MinOPSZ/MaxOPSZ)
  │   ├─ Generates STAT section (includes OPSZ axis)
  │   ├─ Generates avar2 section (192 mappings with OPSZ)
  │   └─ Updates sources/config.yaml
  │
  └─ Steps 2-7: gftools builder
      ├─ buildVariable: Builds variable font
      ├─ fix: Applies fixes
      ├─ BuildSTAT: Adds STAT table (from config.yaml)
      ├─ AddSpacingAxis: Adds SPAC axis
      ├─ BuildAvar2: Adds avar2 table (192 mappings)
      └─ BuildFvarInstances: Adds named instances
```

---

## Key Differences: `make build` vs Other Uses

| Context | CSV Used | `--add-opsz`? | STAT OPSZ? | avar2 OPSZ? |
|---------|----------|---------------|------------|-------------|
| `make build` | `sources/avar2-mappings.csv` | ✅ Yes | ✅ Included | ✅ Included |
| `make build-test` | `preview-app/Crispy-avar.csv` | ❌ No | ❌ Skipped | ❌ Skipped |
| Preview server | `preview-app/Crispy-avar.csv` | ❌ No | ❌ Skipped | ❌ Skipped |

---

## Example: Full Transformation

### Input CSV (1 row)
```csv
Instance Name,WGHT,WDTH,OPSZ,XTRA,XOPQ,YOPQ
Regular,400,100,48,200.0,60.0,50.0
```

### After `--add-opsz` Expansion (3 rows)
```csv
Instance Name,WGHT,WDTH,OPSZ,XTRA,XOPQ,YOPQ,SPAC
Regular,400,100,48,200.0,60.0,50.0,0
Regular-MinOPSZ,400,100,12,200.0,60.0,50.0,20
Regular-MaxOPSZ,400,100,72,200.0,60.0,50.0,-20
```
*(Note: Regular weight = 400, so multipliers are 1.0x, no adjustment)*

### Generated STAT Section
```yaml
stat:
  Crispy:
    - name: Optical Size
      tag: opsz
      values:
        - {name: "12pt", value: 12}
        - {name: "48pt", value: 48}
        - {name: "72pt", value: 72}
    # ... width and weight axes ...
```

### Generated avar2 Section
```yaml
avar2:
  Crispy:
    # Regular-MinOPSZ
    - in:
        wght: 400
        wdth: 100
        opsz: 12
      out:
        XTRA: 200.0
        XOPQ: 60.0
        YOPQ: 50.0
    
    # Regular
    - in:
        wght: 400
        wdth: 100
        opsz: 48
      out:
        XTRA: 200.0
        XOPQ: 60.0
        YOPQ: 50.0
    
    # Regular-MaxOPSZ
    - in:
        wght: 400
        wdth: 100
        opsz: 72
      out:
        XTRA: 200.0
        XOPQ: 60.0
        YOPQ: 50.0
```

---

## Summary

In `make build`, `update_config.py`:
1. **Expands CSV** with MinOPSZ/MaxOPSZ rows (using `opsz.yaml` config)
2. **Generates STAT section** with OPSZ axis (because CSV now has variation)
3. **Generates avar2 section** with OPSZ in `in:` mappings (192 total mappings)
4. **Updates `sources/config.yaml`** ready for `gftools builder`

This ensures the production font supports the full optical size range (12pt to 72pt) with proper STAT and avar2 tables.
