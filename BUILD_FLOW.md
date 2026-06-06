# Crispy Font Build Flow

Complete explanation of the automated build process for the Crispy variable font.

## Overview

The build process transforms source files (Glyphs file, CSV mappings) into final variable TTF fonts with proper STAT, avar2, and fvar tables.

## Complete Build Steps

### Step 1: Update config.yaml
**Script:** `sources/update_config.py`

- **Input:** `sources/Crispy-avar.csv`, `sources/config.yaml`
- **Action:**
  - Expands CSV with contrast variations (`--add-contrast` flag)
  - Generates `stat` section (4 axes: opsz, wdth, wght, cntr)
  - Generates `avar2` section (192 mappings: 64 instances × 3 contrast variants)
  - Automatically adds `cntr: 0` to all `fvarInstances`
  - Injects both sections into `config.yaml`
- **Output:** Updated `sources/config.yaml` with STAT and avar2 sections

**What happens:**
1. CSV validation (checks required columns)
2. CSV expansion: Creates 3 rows per original row (contrast: -10, 0, +10)
3. STAT generation: Extracts unique axis values, creates style linking for Regular→Bold
4. avar2 generation: Creates mappings from traditional axes → parametric axes
5. Config merge: Replaces stat/avar2 sections in config.yaml (preserves formatting)

---

### Steps 2-7: Build Fonts with gftools builder
**Command:** `gftools builder sources/config.yaml`

**gftools builder performs 6 operations automatically:**

#### Step 2: buildVariable
- Reads `config.yaml` and source files (`Crispy.glyphs`)
- Generates variable font designspace
- Builds initial variable TTF with fvar table

#### Step 3: fix
- Applies font fixes and optimizations
- Validates font structure

#### Step 4: BuildSTAT
- Reads `stat` section from `config.yaml`
- Builds STAT table with axis definitions and style linking
- Sets up proper axis names (Optical Size, Width, Weight, Contrast)

#### Step 5: AddSpacingAxis
- Reads `spacingAxis` configuration from `config.yaml`
- Adds SPAC (Spacing) axis to the variable font
- Sets min/max values (-20 to 100)

#### Step 6: BuildAvar2
- Reads `avar2` section from `config.yaml`
- Builds avar2 table with 192 mappings
- Maps traditional axes (wght, wdth, opsz, cntr) → parametric axes (XOPQ, YOPQ, XTRA, SPAC)

#### Step 7: BuildFvarInstances
- Reads `fvarInstances` section from `config.yaml`
- Creates named instances in the font
- 8 instances: ExtraLight, Light, Regular, Medium, SemiBold, Bold, ExtraBold, Black
- All include `cntr: 0` coordinate

**Output:** `fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf`

---

### Step 8: Convert avar2 to avar1
**Command:** `gftools avar2-to-avar1`

- **Input:** Variable font with avar2 table
- **Input:** `scripts/mapping.yaml` (axis value mappings)
- **Action:**
  - Converts avar2 table to avar1 table
  - Uses mapping.yaml to translate axis values
  - Creates backward-compatible font with avar1
- **Output:** `fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf`

**Why?** Some software requires avar1 (older format) instead of avar2.

---

### Step 9: Set Axis Defaults (fvar table)
**Script:** `scripts/set_axis_defaults.py`

- **Input:** Built variable fonts
- **Input:** `sources/axis_defaults.yaml` (desired default values)
- **Action:**
  - Reads axis defaults from YAML
  - Patches `fvar.axes[].defaultValue` for all 8 axes:
    - Traditional: wght, wdth, opsz, cntr
    - Parametric: SPAC, XOPQ, XTRA, YOPQ
  - Validates defaults are within axis ranges
  - Does NOT regenerate font or touch other tables
- **Output:** Fonts with corrected axis defaults

**Applied to both:**
- `fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf` (avar2 version)
- `fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf` (avar1 version)

**What this fixes:**
- Changes defaults from axis minimums (cntr=-10, wdth=40, wght=200) to sensible values
- Sets defaults to Regular Display: wght=400, wdth=100, opsz=72, cntr=0
- Sets parametric defaults from avar2 mapping: SPAC=25, XOPQ=187.67, XTRA=627, YOPQ=135.92

---

## File Flow Diagram

```
sources/Crispy-avar.csv
         ↓
    [Step 1: update_config.py]
         ↓
sources/config.yaml (updated with stat + avar2)
         ↓
sources/Crispy.glyphs
         ↓
    [Steps 2-7: gftools builder]
         ↓
fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf
         ↓
    [Step 8: gftools avar2-to-avar1]
         ↓
fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf
         ↓
    [Step 9: set_axis_defaults.py (both fonts)]
         ↓
Final fonts with correct axis defaults ✓
```

## Configuration Files

### `sources/config.yaml`
- Defines build configuration for gftools builder
- Contains: `fvarInstances`, `stat`, `avar2` sections
- Updated automatically by `update_config.py`

### `sources/Crispy-avar.csv`
- Source data for STAT and avar2 generation
- Columns: Instance Name, XTRA, XOPQ, YOPQ, SPAC, WGHT-e, WDTH-e, OPSZ-e
- Expanded automatically with contrast variations

### `scripts/mapping.yaml`
- Used by `gftools avar2-to-avar1`
- Maps axis values for avar2→avar1 conversion
- Contains mappings for all axes: cntr, wdth, wght, opsz, XTRA, XOPQ, YOPQ, SPAC

### `sources/axis_defaults.yaml`
- Defines desired default values for all 8 axes
- Used by `set_axis_defaults.py` to patch fvar table
- Separate from config.yaml (post-build patch)

## Running the Build

```bash
make build
```

This runs all 9 steps in sequence, creating final fonts with:
- ✅ Correct STAT table (4 axes with style linking)
- ✅ Complete avar2 table (192 mappings)
- ✅ Proper fvarInstances (8 named instances)
- ✅ avar1 version for backward compatibility
- ✅ Correct axis defaults (UI sliders start at sensible values)

## Dependencies

- `venv/` - Python virtual environment with required packages
- `sources/config.yaml` - Main build configuration
- `sources/Crispy-avar.csv` - Source mappings
- `sources/Crispy.glyphs` - Source font file
- `scripts/mapping.yaml` - Axis mappings for avar1 conversion
- `sources/axis_defaults.yaml` - Axis default values

## Build Output

Final fonts in `fonts/variable/`:
- `Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf` - avar2 version
- `Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf` - avar1 version (backward compatible)

Both fonts have:
- 8 axes: wght, wdth, opsz, cntr, SPAC, XOPQ, XTRA, YOPQ
- Proper defaults (Regular Display with Normal contrast)
- Complete STAT table
- Complete avar2/avar1 table
- 8 named instances

