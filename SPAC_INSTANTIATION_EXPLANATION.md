# SPAC Axis Instantiation and Data Flow

## Overview

This document explains how SPAC values are instantiated in the variable font and what data gets saved where when the "Update Instance" button is clicked.

## Key Concepts

### 1. SPAC Axis in the Variable Font

**YES, SPAC values ARE instantiated in the variable font**, but in a specific way:

- **The variable font file (`Crispy-SPAC-VF.ttf`) contains a SPAC axis** with a range of 0-100
- **The font has masters at SPAC=0 and SPAC=100** (created by duplicating and modifying UFO masters)
- **SPAC values from CSV are NOT baked into the font file as fixed instance coordinates**
- **Instead, SPAC values are applied dynamically via CSS `font-variation-settings`** at runtime

### 2. How SPAC Works

The SPAC axis is a **variable font axis** (like WGHT, WDTH, etc.), not a static instance property:

1. **Font Generation** (`add-spac-axis-ufo.py`):
   - Generates UFOs from Glyphs file
   - Duplicates all masters to create SPAC=100 versions
   - Modifies sidebearings in duplicated UFOs using logarithmic scaling
   - Updates designspace to add SPAC axis (0-100 range)
   - Compiles with `fontc` to create `Crispy-SPAC-VF.ttf`

2. **Font File Structure**:
   - Contains SPAC axis definition (min: 0, max: 100, default: 0)
   - Contains masters at SPAC=0 (original) and SPAC=100 (modified)
   - Can interpolate any SPAC value between 0-100

3. **Runtime Application**:
   - Frontend reads SPAC value from CSV (or editing state)
   - Applies SPAC value via CSS: `font-variation-settings: "SPAC" 50`
   - Browser interpolates the font to that SPAC value dynamically

## Data Flow: "Update Instance" Button Click

### Frontend Flow (`preview-app/src/App.js`)

1. **User clicks "Update Instance"** (or flyout option)
2. **Extract coordinates**:
   - `editingCoordinates` (for selected instance) OR
   - `instanceEditingCoordinates[instanceName]` (for non-selected instance)
3. **Separate SPAC from parametric axes**:
   - `spacValue = coordinatesToUse.SPAC`
   - `parametricCoordinates = { ...coordinatesToUse }` (without SPAC)
4. **Send to backend**: `api.updateInstance(instanceName, coordinatesToUse)`
5. **Wait for rebuild** (polling health endpoint)
6. **Reload SPAC values** from API after rebuild completes
7. **Update frontend state** to reflect saved values

### Backend Flow (`scripts/glyphs-preview-server.py`)

#### Endpoint: `PUT /api/instance/<instance_name>`

**Step 1: Parse Request**
- Receives coordinates (including SPAC)
- Validates all values are numeric
- Extracts `spac_value = coordinates.get('SPAC')`

**Step 2: Update Parametric Axes (Glyphs File)**
- Filters coordinates to only axes that exist in Glyphs file (XTRA, XOPQ, YOPQ)
- **Excludes SPAC** (SPAC is not in Glyphs file)
- If parametric coordinates exist:
  - Calls `update_instance_in_glyphs()`:
    - Loads Glyphs file
    - Finds instance by name
    - Updates `instance.axes` array with new parametric values
    - Saves Glyphs file
    - Forces Glyphs.app to reload document

**Step 3: Update SPAC Value (CSV File)**
- If `spac_value` is provided:
  - Reads `preview-app/Crispy-avar.csv`
  - Ensures "SPAC" column exists (adds if missing)
  - Finds row matching instance name
  - Updates `row["SPAC"] = str(spac_value)`
  - Writes updated CSV back to disk
  - Updates CSV modification time cache

**Step 4: Sync Avar2 CSV** (if exists)
- Runs `sync-glyphs-to-avar2.py` to sync parametric axis values
- Skips this instance if it's still marked as "editing"

**Step 5: Rebuild Font**
- Checks if SPAC font exists (`preview-app/preview-fonts/spac/Crispy-SPAC-VF.ttf`)
- **If SPAC font exists**:
  - Calls `_regenerate_spac_font()`:
    - Runs `add-spac-axis-ufo.py` with `--compile` flag
    - Regenerates designspace and UFOs from updated Glyphs file
    - Recompiles font with `fontc`
    - Outputs `Crispy-SPAC-VF.ttf`
- **If SPAC font doesn't exist**:
  - Calls `trigger_build()`:
    - Builds regular variable font from Glyphs file
    - Outputs `Crispy-VF.ttf`

## File Locations and What Gets Saved

### 1. Glyphs File (`sources/Crispy.glyphs`)

**What gets saved:**
- **Parametric axes only**: XTRA, XOPQ, YOPQ
- **Instance coordinates**: `instance.axes` array updated with new parametric values
- **NOT saved**: SPAC (SPAC axis doesn't exist in Glyphs file)

**When:**
- Only if parametric axes changed (XTRA, XOPQ, or YOPQ)
- Saved immediately when "Update Instance" is clicked

**How:**
- `update_instance_in_glyphs()` function:
  - Loads Glyphs file with `glyphsLib`
  - Finds instance by name
  - Updates `instance.axes` array
  - Saves file with `font.save()`
  - Forces Glyphs.app to reload document

### 2. Preview CSV (`preview-app/Crispy-avar.csv`)

**What gets saved:**
- **SPAC value**: Saved to "SPAC" column for the instance
- **Parametric axes**: Also synced from Glyphs file (via `sync-glyphs-to-avar2.py`)

**When:**
- SPAC value saved immediately when "Update Instance" is clicked
- Parametric axes synced after Glyphs file update

**Format:**
```csv
Instance Name,XTRA,XOPQ,YOPQ,SPAC
Thin Condensed SmallOpsz,0.0,0.0,0.0,50
Regular,50.0,50.0,50.0,0
...
```

**How:**
- Reads CSV with `csv.DictReader`
- Updates row matching instance name
- Writes back with `csv.DictWriter`
- Updates modification time cache

### 3. Variable Font File (`preview-app/preview-fonts/spac/Crispy-SPAC-VF.ttf`)

**What gets saved:**
- **SPAC axis definition**: Added to font's `fvar` table (min: 0, max: 100, default: 0)
- **Masters**: Original masters at SPAC=0, duplicated/modified masters at SPAC=100
- **NOT saved**: Individual instance SPAC values (these are applied via CSS)

**When:**
- Rebuilt after "Update Instance" is clicked (if SPAC font exists)
- Regenerated from updated Glyphs file + designspace

**How:**
- `add-spac-axis-ufo.py` script:
  1. Generates UFOs from Glyphs file using `fontmake`
  2. Duplicates masters to create SPAC=100 versions
  3. Modifies sidebearings in duplicated UFOs
  4. Updates designspace to add SPAC axis
  5. Compiles with `fontc` to create variable font

### 4. Designspace File (`preview-app/preview-fonts/spac/*.designspace`)

**What gets saved:**
- **SPAC axis**: Added to axes list (min: 0, max: 100, default: 0)
- **Sources**: Original sources at SPAC=0, duplicated sources at SPAC=100
- **Instances**: Not modified (instances use parametric axes only)

**When:**
- Generated/updated when SPAC font is regenerated

## SPAC Value Application in Frontend

### How SPAC Values Are Applied

1. **Source of SPAC Value**:
   - **For selected instance**: From `editingCoordinates.SPAC` (slider value)
   - **For non-selected instances**: From `instanceEditingCoordinates[instanceName].SPAC` OR `spacValues[instanceName]` (from CSV)

2. **CSS Application** (`InstanceRow.js`):
   ```javascript
   const activeCoordinates = isSelected && Object.keys(editingCoordinates).length > 0
     ? editingCoordinates
     : (instanceEditingCoordinates[instance.name] || instance.coordinates);
   
   let fontVariationSettings = Object.entries(activeCoordinates)
     .map(([tag, value]) => `"${tag}" ${value}`)
     .join(', ');
   
   // Applied to preview text:
   style={{ fontVariationSettings: fontVariationSettings }}
   ```

3. **Browser Behavior**:
   - Browser receives CSS: `font-variation-settings: "SPAC" 50`
   - Browser interpolates variable font to SPAC=50
   - Font displays with spacing corresponding to SPAC=50

### State Management After Update

After "Update Instance" completes:

1. **Backend saves**:
   - Parametric axes → Glyphs file
   - SPAC value → CSV file
   - Font rebuilt

2. **Frontend reloads**:
   - Fetches latest SPAC values from API (`api.getSpacValues()`)
   - Updates `spacValues` state
   - Updates `originalCoordinates` and `editingCoordinates` (for selected instance)
   - Updates `instanceOriginalCoordinates` and `instanceEditingCoordinates` (for all instances)

3. **Sync Status**:
   - `getInstanceSyncStatus()` compares `editingCoordinates` vs `originalCoordinates`
   - If SPAC value matches saved value → green dot
   - If SPAC value differs → orange dot

## Summary: What Gets Saved Where

| Data Type | File Location | When Saved | How Applied |
|-----------|--------------|-------------|-------------|
| **Parametric Axes** (XTRA, XOPQ, YOPQ) | `sources/Crispy.glyphs` | On "Update Instance" if changed | Baked into font file as instance coordinates |
| **SPAC Value** | `preview-app/Crispy-avar.csv` | On "Update Instance" if changed | Applied via CSS `font-variation-settings` at runtime |
| **SPAC Axis** (0-100 range) | `preview-app/preview-fonts/spac/Crispy-SPAC-VF.ttf` | On font rebuild | Variable font axis, interpolated by browser |
| **SPAC Masters** (SPAC=0, SPAC=100) | `preview-app/preview-fonts/spac/*.ufo` | On font rebuild | Used for interpolation by variable font |

## Confirmation: SPAC Values ARE Instantiated

**YES, SPAC values are instantiated in the variable font**, but:

1. **The font file contains the SPAC axis** (0-100 range) with masters at SPAC=0 and SPAC=100
2. **SPAC values from CSV are NOT baked into the font** as fixed instance coordinates
3. **SPAC values are applied dynamically** via CSS `font-variation-settings` at runtime
4. **The browser interpolates** the variable font to the specified SPAC value

This is the standard way variable fonts work: the font contains the axis definition and masters, and specific axis values are applied at runtime via CSS or font APIs.
