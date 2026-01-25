# Avar2 Font Build Process

## Overview
This document outlines the complete process involved in building an avar2 font from the preview tool, from user interaction to final font output.

## Process Flow

### 1. **User Interaction (Frontend)**
   - **Location**: `preview-app/src/components/BuildAvar2Modal.js`
   - **Trigger**: User clicks "Build Avar2 Font" button in Header (when in Avar2 Preview mode)
   - **User Selections**:
     - **Traditional Axes** (Input to Avar2): Dynamically determined from CSV columns that aren't parametric axes from Glyphs file
       - Examples: `WGHT`, `WDTH`, `OPSZ` (from CSV)
       - Excludes: SPAC axis (handled separately)
     - **Parametric Axes** (Output from Avar2): Dynamically determined from axes in Glyphs file
       - Examples: `XTRA`, `XOPQ`, `YOPQ` (from Glyphs file)
     - **Include SPAC**: Checkbox to include SPAC axis (always available)
   - **Validation**: At least one traditional axis must be selected
   - **Sync Check**: Modal displays sync status warning if CSV is not synced with Glyphs file
   - **Action**: Calls `onBuild()` handler with selected axes

### 2. **API Request (Frontend)**
   - **Location**: `preview-app/src/api.js` → `buildAvar2Font()`
   - **Endpoint**: `POST /api/build-avar2`
   - **Payload**:
     ```json
     {
       "traditional_axes": ["WGHT", "WDTH", "OPSZ"],  // Original CSV column names
       "avar2_axes": ["XTRA", "XOPQ", "YOPQ"],        // Parametric axis names
       "include_spac": true
     }
     ```
   - **Note**: Currently, `traditional_axes` and `avar2_axes` are received but **not yet used** to filter the CSV. The build uses the entire CSV as-is.

### 3. **Backend Build Endpoint**
   - **Location**: `scripts/glyphs-preview-server.py` → `build_avar2_font()`
   - **Steps**:

   #### 3.1. **Validation & Setup**
   - Check if build is already in progress (prevent concurrent builds)
   - Validate request payload
   - Check CSV sync status (for informational purposes)
   - Verify preview CSV exists: `preview-app/Crispy-avar.csv`
   - Create output directory: `preview-app/fonts-avar2/variable/`

   #### 3.2. **Create Isolated Build Environment**
   - **Temporary Directory**: `preview-app/build-temp/`
   - **Structure**:
     ```
     build-temp/
     ├── sources/
     │   ├── Crispy.glyphs (symlink to sources/Crispy.glyphs)
     │   └── test-config.yaml (copy of sources/config.yaml)
     └── fonts/ (symlink to preview-app/fonts-avar2/)
     ```
   - **Purpose**: Isolated build that doesn't affect main `fonts/` or `sources/` directories
   - **Symlinks**: Use absolute paths for robustness

   #### 3.3. **Prepare Configuration**
   - Copy `sources/config.yaml` → `build-temp/sources/test-config.yaml`
   - Base config includes necessary sections: `spacingAxis`, `fvarInstances`, etc.
   - Fix Glyphs path in config using `sed` (if needed)

   #### 3.4. **Update Config with CSV Data**
   - **Script**: `sources/update_config.py`
   - **Command**:
     ```bash
     python sources/update_config.py \
       --csv preview-app/Crispy-avar.csv \
       --config build-temp/sources/test-config.yaml \
       --no-backup
     ```
   - **Process** (`update_config.py`):
     1. **Read CSV**: Parse `preview-app/Crispy-avar.csv`
     2. **Detect Columns**:
        - **Traditional axes** (`in:`): Columns not in Glyphs file (e.g., `WGHT`, `WDTH`, `OPSZ`)
        - **Parametric axes** (`out:`): Columns that are axes in Glyphs file (e.g., `XTRA`, `XOPQ`, `YOPQ`)
     3. **Validate CSV Structure**:
        - Must have "Instance Name" column
        - Traditional axes: Can have blanks (optional)
        - Parametric axes: Must be populated (no blanks allowed)
        - Required axes: `wght`, `wdth`, `opsz` must exist
     4. **Generate STAT Section**:
        - Creates STAT table entries for all axes
        - Groups by width, then weight, then optical size
        - Removes OPSZ if no variation (all instances have same opsz value)
     5. **Generate Avar2 Section**:
        - Creates avar2 mappings from CSV rows
        - Format: `in:` (traditional axes) → `out:` (parametric axes)
        - Sorts by width, weight, optical size
        - Groups with comments (Width/OPSZ headers)
        - Skips OPSZ in `in:` if no variation
     6. **Merge into Config**:
        - Replaces/updates `stat:` section
        - Replaces/updates `avar2:` section
        - Validates merged config structure
     7. **Write Updated Config**: Saves `test-config.yaml` with new sections

   #### 3.5. **Build Font with gftools**
   - **Command**:
     ```bash
     cd build-temp/sources
     gftools builder \
       --experimental-fontc $(which fontc) \
       test-config.yaml
     ```
   - **Process**:
     - `gftools builder` reads `test-config.yaml`
     - Uses `fontc` (experimental compiler) for compilation
     - Builds variable font from Glyphs file
     - Applies STAT table from config
     - Applies avar2 mappings from config
     - Outputs to: `build-temp/fonts/variable/` (symlinked to `preview-app/fonts-avar2/variable/`)
   - **Output Font**: `Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf`
     - Contains parametric axes: `SPAC`, `XOPQ`, `XTRA`, `YOPQ`
     - Contains avar2 table mapping traditional axes → parametric axes

   #### 3.6. **Verify & Cleanup**
   - Check that font file exists: `preview-app/fonts-avar2/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf`
   - Clean up temporary directory: `rm -rf preview-app/build-temp/`
   - Return success response with font path

### 4. **Font Loading (Frontend)**
   - **Location**: `preview-app/src/App.js` → `handleBuildAvar2Font()`
   - **After Successful Build**:
     1. **Auto-switch Mode**: If not already in Avar2 Preview mode, switch to it
     2. **Get Font URL**: `api.getAvar2FontUrl()` → `/api/avar2-font?t={timestamp}`
     3. **Load Font via FontFace API**:
        - Remove old font instance if exists (force reload)
        - Create new `FontFace` object: `new FontFace('Crispy-VF', url(...))`
        - Load font: `await fontFace.load()`
        - Add to document: `document.fonts.add(fontFace)`
        - Wait for ready: `await document.fonts.ready`
     4. **Update State**:
        - `setAvar2FontUrl(fontUrl)`
        - `setAvar2FontLoaded(true)`
     5. **Update Sync Status**: Display sync status from build response

### 5. **Font Serving (Backend)**
   - **Location**: `scripts/glyphs-preview-server.py` → `get_avar2_font()`
   - **Endpoint**: `GET /api/avar2-font`
   - **Process**:
     - Check if font directory exists: `preview-app/fonts-avar2/variable/`
     - Look for font file: `Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf`
     - Serve file with `send_file()` (Flask)
     - MIME type: `font/ttf`
     - Cache busting: URL includes timestamp query parameter

### 6. **Avar2 Preview Mode (Frontend)**
   - **Location**: `preview-app/src/components/Avar2Preview.js`
   - **Display**:
     - **Sidebar**: Parametric axes (XTRA, XOPQ, YOPQ, SPAC) + Traditional axes (wght, wdth, opsz, cntr)
     - **Main Area**: Preview text with font-variation-settings
     - **Mapping**: Traditional axis changes → Find closest avar2 mapping → Update parametric axes
   - **Download Button**: Downloads the built avar2 font file

## Key Files & Directories

### Input Files
- **Preview CSV**: `preview-app/Crispy-avar.csv`
  - Contains instance mappings: traditional axes → parametric axes
  - Source of truth for avar2 mappings
- **Glyphs File**: `sources/Crispy.glyphs`
  - Source font file
  - Defines parametric axes
- **Base Config**: `sources/config.yaml`
  - Base configuration with `spacingAxis`, `fvarInstances`, etc.

### Temporary Files (Cleaned Up)
- **Build Temp**: `preview-app/build-temp/`
  - Isolated build environment
  - Removed after build completes

### Output Files
- **Avar2 Font**: `preview-app/fonts-avar2/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf`
  - Final built font with avar2 table
  - Served via `/api/avar2-font` endpoint

## Error Handling

### Build Failures
- **Config Update Failure**: Returns error with `update_config.py` stderr
- **Font Build Failure**: Returns error with `gftools builder` stdout/stderr
- **Font Not Found**: Returns error if font file doesn't exist after build
- **Cleanup**: Always removes `build-temp/` directory on error

### Frontend Errors
- **Build Failed**: Displays error message in modal
- **Font Load Failed**: Logs error to console, doesn't block UI

## Current Limitations

1. **Axis Selection Not Implemented**: 
   - `traditional_axes` and `avar2_axes` parameters are received but not used to filter CSV
   - Build uses entire CSV as-is
   - Future enhancement: Filter CSV rows/columns based on selected axes

2. **SPAC Handling**:
   - `include_spac` parameter is received but not used
   - SPAC axis is always included if present in CSV
   - Future enhancement: Conditionally include/exclude SPAC axis

## Dependencies

- **Python**: `update_config.py` script
- **gftools**: Font build tool (`gftools builder`)
- **fontc**: Experimental font compiler (via `--experimental-fontc`)
- **Font Libraries**: `glyphsLib`, `fontTools` (used by `update_config.py`)

## Build Isolation

The build process is completely isolated:
- Uses temporary directory (`build-temp/`)
- Symlinks to source files (doesn't copy)
- Outputs to separate directory (`fonts-avar2/`)
- Never modifies `sources/` or main `fonts/` directories
- Safe to run on public Git branches
