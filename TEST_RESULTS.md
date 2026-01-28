# Testing Results - UI/UX Updates

**Date:** January 28, 2025
**Tester:** Automated Testing Routine

---

## Pre-Testing Status

✅ **Servers Running:**
- Flask backend: Port 5001 (PID: 1635, 10155)
- React frontend: Port 3000 (serve -s build)

✅ **Files Present:**
- Glyphs file: `sources/Crispy.glyphs` ✓
- Font file: `preview-app/preview-fonts/Crispy-VF.ttf` (77KB, modified Jan 28 14:14) ✓
- SPAC font: `preview-app/preview-fonts/spac/Crispy-SPAC-VF.ttf` ✓

✅ **API Endpoints:**
- `/api/health` - Working ✓
- `/api/instances` - Working ✓
- `/api/spacing/check` - Working ✓ (SPAC range: 0-100) ✓
- `/api/glyphs-file-status` - **NEEDS SERVER RESTART** ⚠️

---

## Test 1: Server Startup Auto-Build ⚠️

**Status:** NEEDS VERIFICATION (Server already running)

**Action Required:** Restart server to verify auto-build on startup

**Current State:**
- Font exists and was built at 14:14 today
- Server is running but was started before auto-build code was added
- Need to restart to see "Auto-building font on startup..." message

**Command to test:**
```bash
# Stop current server, then:
cd scripts && python glyphs-preview-server.py
# Look for: "Auto-building font on startup..." in logs
```

---

## Test 2: Hard Reset Auto-Build (Browser Refresh)

**Status:** READY TO TEST

**Steps:**
1. Open http://localhost:3000 in browser
2. Delete font: `rm preview-app/preview-fonts/Crispy-VF.ttf`
3. Hard refresh: Cmd+Shift+R
4. Check Network tab for `/api/build` request
5. Verify font rebuilds automatically

**Expected:** Font should rebuild automatically without clicking "Build Font"

---

## Test 3: SPAC Axis Slider Styling ✅

**Status:** CODE VERIFIED

**Verification:**
- `SpacAxisControl.js` now imports `AxisControl.css` ✓
- Uses same class names: `axis-control`, `axis-header`, `axis-name`, `axis-slider`, `axis-values` ✓
- Removed custom `SpacAxisControl.css` styling ✓

**Visual Test Required:** Open browser and compare SPAC slider with parametric axes

---

## Test 4: Font Size Label Styling ✅

**Status:** CODE VERIFIED

**Verification:**
- `Sidebar.js` Font Size now uses `axis-header` and `axis-name` classes ✓
- CSS updated to use `.font-size-control .axis-name` styling ✓
- Matches parametric axis label styling ✓

**Visual Test Required:** Check Font Size label matches axis labels

---

## Test 5: Refresh Button Removal ✅

**Status:** CODE VERIFIED

**Verification:**
- `Header.js` has no `onRefresh` prop ✓
- No "Refresh" button in JSX ✓
- Only "Build Font" / "Rebuild Font" button remains ✓

**Visual Test Required:** Confirm no Refresh button in header

---

## Test 6: Add Axis Button Styling ✅

**Status:** CODE VERIFIED

**Verification:**
- `Sidebar.css` `.btn-add-axis` updated to match `.btn-update` ✓
- Same padding: `0.75rem 1rem` ✓
- Same font-size: `0.6375rem` ✓
- Same font-family: `monospace` ✓
- Same width: `100%` ✓

**Visual Test Required:** Compare "Add Axis" with "Update Instance" button

---

## Test 7: Avar2 Shown by Default ✅

**Status:** CODE VERIFIED

**Verification:**
- `Header.js` has no `avar2Mode` toggle checkbox ✓
- `App.js` sets `avar2Mode` to `true` by default ✓
- `loadAvar2Data()` called on mount (not conditional on toggle) ✓
- No "Show Avar2" checkbox in header ✓

**Visual Test Required:** Confirm Avar2 section visible on page load

---

## Test 8: Update Instance Disabled with Unsaved Changes ⚠️

**Status:** CODE VERIFIED, ENDPOINT NEEDS RESTART

**Code Verification:**
- `_check_glyphs_file_unsaved_changes()` function exists ✓
- `/api/glyphs-file-status` endpoint added ✓
- `UpdateButton.js` accepts `disabled` and `title` props ✓
- `Sidebar.js` passes `glyphsFileHasUnsavedChanges` prop ✓
- `App.js` polls `/api/glyphs-file-status` every 2 seconds ✓

**Action Required:** 
1. Restart server to load new endpoint
2. Test with Glyphs.app open and unsaved changes

**Test Steps:**
1. Open `sources/Crispy.glyphs` in Glyphs.app
2. Make a change, **DO NOT SAVE**
3. In preview tool, select instance
4. Verify "Update Instance" button is disabled
5. Save Glyphs file
6. Verify button becomes enabled

---

## Test 9: Scenario - Launching with New Glyphs File

**Status:** READY TO TEST

**Test Command:**
```bash
# Stop current server
# Create test Glyphs file or use different file
python scripts/glyphs-preview-server.py --glyphs path/to/test.glyphs
```

**Expected:**
- Server auto-builds font on startup
- Page auto-builds if font missing
- Instances load correctly

---

## Test 10: Scenario - Launching with Already Edited Glyphs File ✅

**Status:** VERIFIED (Current State)

**Current State:**
- Using existing `sources/Crispy.glyphs` ✓
- Instances load correctly ✓
- Coordinates match Glyphs file ✓

**Note:** This is the current working state

---

## Test 11: Scenario - Updating Instance with Saved Glyphs File

**Status:** READY TO TEST

**Steps:**
1. Ensure Glyphs file is saved
2. Select instance
3. Change coordinates
4. Click "Update Instance"
5. Verify rebuild and persistence

---

## Test 12: Scenario - Updating Instance with Unsaved Glyphs File

**Status:** READY TO TEST (After server restart)

**Requires:** Server restart + Glyphs.app testing

---

## Test 13: Polling for Unsaved Changes

**Status:** CODE VERIFIED, NEEDS SERVER RESTART

**Code Verification:**
- Polling interval: 2 seconds ✓
- Calls `/api/glyphs-file-status` ✓
- Updates `glyphsFileHasUnsavedChanges` state ✓

**Action Required:** Restart server, then test

---

## Test 14: Font Rebuild on Hard Reset

**Status:** READY TO TEST

**Steps:**
1. Delete font: `rm preview-app/preview-fonts/Crispy-VF.ttf`
2. Hard refresh browser
3. Check Network tab for `/api/build` call
4. Verify font rebuilds

---

## Summary

**Code Verification:** ✅ 7/14 tests (all code changes verified)
**API Testing:** ⚠️ 3/14 tests (1 endpoint needs restart)
**Visual/Browser Testing:** ⏳ 4/14 tests (requires browser)

**Critical Actions:**
1. **RESTART SERVER** to load new `/api/glyphs-file-status` endpoint
2. **Open browser** to verify UI changes
3. **Test unsaved changes** with Glyphs.app

**Next Steps:**
1. Restart Flask server
2. Open http://localhost:3000 in browser
3. Verify all UI changes visually
4. Test unsaved changes detection

---

## Quick Test Commands

```bash
# Restart backend (to load new endpoint)
# Kill existing: pkill -f glyphs-preview-server.py
cd scripts && python glyphs-preview-server.py

# Check endpoint after restart
curl http://localhost:5001/api/glyphs-file-status

# Test auto-build on startup (watch logs)
# Should see: "Auto-building font on startup..."

# Open browser
open http://localhost:3000
```
