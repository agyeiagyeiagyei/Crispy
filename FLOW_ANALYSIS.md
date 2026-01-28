# Update Instance Flow Analysis

## Current Implementation

### Flow When SPAC Font EXISTS (SPAC mode ON):
1. ✅ Confirm update instance
2. ✅ Update Glyphs file (parametric axes)
3. ✅ Update CSV (SPAC value)
4. ✅ Sync CSV
5. ✅ **Background thread:** Call `_regenerate_spac_font()`
   - Runs `add-spac-axis-ufo.py`:
     - **Step 1:** `generate_ufos_from_glyphs()` → Uses fontmake: Glyphs → UFOs + Designspace
     - **Step 2:** Duplicate masters for SPAC=100
     - **Step 3:** Update designspace with SPAC axis
     - **Step 4:** Compile designspace with fontc → Font
6. ✅ **Font rebuilt ONCE** ✓

### Flow When SPAC Font DOESN'T EXIST (SPAC mode OFF):
1. ✅ Confirm update instance
2. ✅ Update Glyphs file (parametric axes)
3. ✅ Update CSV (SPAC value)
4. ✅ Sync CSV
5. ❌ **Background thread:** Call `trigger_build()`
   - Calls `build_variable_font()`:
     - Uses fontc **directly on Glyphs file**
     - **NO designspace involved** ✗
6. ✅ **Font rebuilt ONCE** ✓

## Expected Flow (Per User Requirements)

### Flow Should Be:
1. ✅ Confirm update instance
2. ✅ Update Glyphs file and CSV
3. ✅ **Convert Glyphs to Designspace:**
   - **If SPAC is ON:** With SPAC master duplication
   - **If SPAC is OFF:** Without SPAC master duplication (regular designspace)
4. ✅ **Build font from designspace** (always)

## Issues Identified

### Issue 1: No Designspace When SPAC is OFF
**Current:** When SPAC font doesn't exist, `trigger_build()` builds directly from Glyphs file (no designspace).

**Expected:** Always generate designspace, then build from designspace.

### Issue 2: SPAC Mode Detection
**Current:** Checks if SPAC font file exists (`spac_font_path.exists()`).

**Expected:** Should check if SPAC mode is enabled (frontend state), not just if file exists.

### Issue 3: Single Build Confirmation
**Current:** Font is rebuilt ONCE ✓ (either via `_regenerate_spac_font()` OR `trigger_build()`)

**Expected:** Font should be rebuilt ONCE ✓ (always via designspace)

## Solution Needed

1. **Always generate designspace** (with or without SPAC masters)
2. **Always build from designspace** (never directly from Glyphs)
3. **Check SPAC mode state** (not just file existence)
4. **Ensure single build** (already working, but needs to be consistent)

## Code Changes Required

1. Modify `update_instance` to:
   - Always generate designspace (via fontmake)
   - If SPAC mode ON: Add SPAC masters and axis
   - If SPAC mode OFF: Use regular designspace (no SPAC masters)
   - Always compile designspace with fontc

2. Remove direct Glyphs → Font path (`trigger_build()` should not be used for instance updates)

3. Pass SPAC mode state from frontend to backend (or check CSV for SPAC column existence)
