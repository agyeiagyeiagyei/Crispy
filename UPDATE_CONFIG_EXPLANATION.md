# How `update_config.py` Works on glyphs-preview-tool Branch

## Overview

`update_config.py` is a script that generates and injects STAT table and avar2 mapping sections into `config.yaml` from CSV mappings. It's called automatically by the preview server when instances are updated.

## Location

- **Script:** `sources/update_config.py`
- **Called from:** `scripts/glyphs-preview-server.py` (in `update_instance` endpoint)

## Purpose

The script synchronizes the `config.yaml` file with instance data from the CSV file. It ensures that:
1. STAT table reflects all instance coordinates
2. avar2 mappings match CSV data
3. Config file stays in sync with Glyphs file changes

## How It's Called

### In `update_instance` Endpoint

When an instance is updated via the preview tool:

```python
# After updating Glyphs file and CSV
update_config_script = Path.cwd() / "sources" / "update_config.py"
update_config_cmd = [
    sys.executable,
    str(update_config_script),
    "--csv", str(preview_csv),
    "--config", str(config_to_update),
    "--no-backup"
]

result = subprocess.run(update_config_cmd, ...)
```

**Parameters:**
- `--csv`: Path to preview CSV (`preview-app/Crispy-avar.csv`)
- `--config`: Path to config file (`preview-app/config-preview.yaml` or `sources/config.yaml`)
- `--no-backup`: Don't create backup (since this is automated)

## Workflow

### Step 1: Validate CSV Structure
- Checks for required columns: "Instance Name", WGHT, WDTH, OPSZ
- Validates traditional axes (WGHT/WDTH/OPSZ) vs parametric axes (XTRA/XOPQ/YOPQ)
- Ensures all parametric axis values are present (no blanks)

### Step 2: Read CSV Mappings
- Parses CSV into `RowMapping` objects
- Each mapping contains:
  - `instance_name`: Instance name
  - `in_axes`: Traditional axis coordinates (wght, wdth, opsz, optionally cntr)
  - `out_axes`: Parametric axis coordinates (XTRA, XOPQ, YOPQ)
  - `out_axis_order`: Order of parametric axes (preserved from CSV header)

### Step 3: Optional Expansions
- **`--add-opsz`**: Expands CSV with MinOPSZ/MaxOPSZ rows based on `opsz.yaml`
- **`--add-contrast`**: Expands CSV with contrast variations (not used in preview tool)

### Step 4: Generate STAT Section
- Extracts unique axis values from CSV
- Creates STAT table structure:
  - Optical Size axis (only if variation exists)
  - Width axis (always present)
  - Weight axis (always present, with style linking)
  - Contrast axis (if present in CSV)
- Maps values to names (e.g., 400 → "Regular", 700 → "Bold")

### Step 5: Generate avar2 Section
- Creates avar2 mappings from CSV rows
- Format: `in:` (traditional axes) → `out:` (parametric axes)
- Groups by width and optical size (with comments)
- Skips opsz in `in:` if no variation (all instances have same OPSZ)
- Preserves parametric axis order from CSV

### Step 6: Merge into Config
- Loads existing `config.yaml`
- Replaces/updates `stat` section
- Replaces/updates `avar2` section
- Updates `fvarInstances` if contrast was added

### Step 7: Write Config
- Uses hybrid approach: writes most sections as YAML, but injects pre-formatted avar2 YAML string to preserve comments
- Finds section boundaries in original file
- Replaces sections while preserving other content
- Creates backup (unless `--no-backup`)

## CSV Structure Expected

```csv
Instance Name,WGHT,WDTH,OPSZ,XTRA,XOPQ,YOPQ,SPAC
Thin Condensed,100,40,48,181.2,40.3,41.3,0
...
```

**Columns:**
- **Instance Name**: Required
- **WGHT, WDTH, OPSZ**: Required traditional axes (for `in:`)
- **XTRA, XOPQ, YOPQ**: Parametric axes (for `out:`)
- **SPAC**: Optional (CSV-only, not used in config generation)

## Output Sections

### STAT Section
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

### avar2 Section
```yaml
avar2:
  Crispy:
    # =========================
    # Width = 40
    # =========================
    
    # Thin Condensed
    - in:
        wght: 100
        wdth: 40
        opsz: 48
      out:
        XTRA: 181.2
        XOPQ: 40.3
        YOPQ: 41.3
```

## Integration Points

### 1. Makefile - `make build`

**Location:** `Makefile` line 32

**When Called:** During production font build (`make build`)

**Command:**
```bash
python3 sources/update_config.py \
  --csv sources/avar2-mappings.csv \
  --config sources/config.yaml \
  --no-backup \
  --add-opsz
```

**Purpose:** 
- Step 1 of build process (after CSV sync, before font build)
- Updates `sources/config.yaml` with STAT and avar2 sections
- **Includes `--add-opsz` flag** to expand CSV with MinOPSZ/MaxOPSZ rows

**Build Flow:**
1. Sync CSV from Glyphs (`sync-glyphs-to-avar2.py`)
2. **Update config.yaml** (`update_config.py` with `--add-opsz`)
3. Build fonts (`gftools builder`)

### 2. Makefile - `make build-test`

**Location:** `Makefile` line 64

**When Called:** During test build (`make build-test`)

**Command:**
```bash
python3 sources/update_config.py \
  --csv preview-app/Crispy-avar.csv \
  --config preview-app/config-preview.yaml \
  --no-backup
```

**Purpose:**
- Test build using preview CSV and config
- Updates `preview-app/config-preview.yaml`
- **No `--add-opsz` flag** (uses CSV as-is)

### 3. Preview Server - `/api/build-avar2`

**Location:** `scripts/glyphs-preview-server.py` line ~2997

**When Called:** When user clicks "Build Avar2 Font" button in preview tool

**Command:**
```python
python3 sources/update_config.py \
  --csv preview-app/Crispy-avar.csv \
  --config preview-app/config-preview.yaml \
  --no-backup
```

**Purpose:**
- Syncs `config-preview.yaml` with CSV before building Avar2 font
- Ensures config is ready for font build
- **NOT called during instance updates** (instance updates only modify Glyphs/CSV)

### Config Files Used

- **Production build (`make build`)**: `sources/config.yaml`
- **Test build (`make build-test`)**: `preview-app/config-preview.yaml`
- **Preview tool (`/api/build-avar2`)**: `preview-app/config-preview.yaml` (preferred) or `sources/config.yaml` (fallback)

## Key Features

1. **Preserves Comments**: Uses pre-formatted YAML string for avar2 section to keep comments
2. **Validates Everything**: Validates CSV, generated sections, and merged config
3. **Handles OPSZ Variation**: Automatically skips opsz in avar2 if no variation
4. **Style Linking**: Adds style linking for Regular → Bold in STAT table
5. **Error Handling**: Returns error codes and detailed error messages

## Error Handling

If `update_config.py` fails:
- Returns non-zero exit code
- Preview server logs error
- Instance update may still succeed (Glyphs/CSV updated), but config won't be synced
- User can manually run script to sync config

## Example Usage

```bash
# Manual run
python sources/update_config.py \
  --csv preview-app/Crispy-avar.csv \
  --config preview-app/config-preview.yaml \
  --no-backup

# With OPSZ expansion
python sources/update_config.py \
  --csv preview-app/Crispy-avar.csv \
  --config preview-app/config-preview.yaml \
  --add-opsz \
  --no-backup
```

## Notes

- SPAC column in CSV is **ignored** by `update_config.py` (SPAC is not in config.yaml)
- Only parametric axes (XTRA, XOPQ, YOPQ) go into avar2 `out:` section
- Traditional axes (WGHT, WDTH, OPSZ) go into avar2 `in:` section
- The script ensures config.yaml stays synchronized with CSV data
