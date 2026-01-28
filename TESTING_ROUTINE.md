# Testing Routine for UI/UX Updates

## Pre-Testing Setup

1. **Stop all running servers** (Flask backend and React frontend)
2. **Ensure Glyphs file is closed** in Glyphs.app (or note its state)
3. **Clear browser cache** or use incognito/private mode
4. **Check current state**:
   - Verify `sources/Crispy.glyphs` exists
   - Verify `preview-app/preview-fonts/spac/Crispy-SPAC-VF.ttf` may or may not exist (will be auto-generated)

## Test 1: Server Startup Auto-Build

**Steps:**
1. Start Flask backend: `cd scripts && python glyphs-preview-server.py`
2. **Expected:** Server should automatically build the font on startup
3. **Check logs:** Look for "Auto-building font on startup..." and "✓ Font built successfully on startup"
4. **Verify:** Check that `preview-app/preview-fonts/Crispy-VF.ttf` exists

**Pass Criteria:**
- ✅ Font builds automatically without manual trigger
- ✅ No errors in server logs
- ✅ Font file exists after startup

---

## Test 2: Hard Reset Auto-Build (Browser Refresh)

**Steps:**
1. Ensure Flask backend is running
2. Start React frontend: `cd preview-app && npm start` (or serve built version)
3. Open browser to `http://localhost:3000`
4. **Before refresh:** Note if font is built (check `/api/health` response)
5. **Delete font file manually:** `rm preview-app/preview-fonts/Crispy-VF.ttf` (simulate no font)
6. **Hard refresh browser:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)
7. **Expected:** Page should detect missing font and trigger auto-build

**Pass Criteria:**
- ✅ Font builds automatically on page load if missing
- ✅ No manual "Build Font" button click required
- ✅ Font loads and displays correctly after auto-build

---

## Test 3: SPAC Axis Slider Styling

**Steps:**
1. Ensure SPAC font exists (should auto-generate if missing)
2. Enable SPAC mode (toggle should be visible)
3. Select an instance
4. **Compare:** SPAC slider vs parametric axis sliders (XTRA, XOPQ, YOPQ, etc.)

**Pass Criteria:**
- ✅ SPAC slider uses same styling as parametric axis sliders
- ✅ Same slider track, thumb, and value display styling
- ✅ Consistent spacing and layout

---

## Test 4: Font Size Label Styling

**Steps:**
1. Look at "Font Size" label in sidebar
2. Compare with parametric axis labels (e.g., "XTRA", "XOPQ")

**Pass Criteria:**
- ✅ Font Size label uses same styling as axis-name (0.6375rem, monospace, #666 color)
- ✅ Same font-weight and spacing
- ✅ Consistent visual appearance

---

## Test 5: Refresh Button Removal

**Steps:**
1. Check Header component
2. Look for "Refresh" button

**Pass Criteria:**
- ✅ No "Refresh" button visible in header
- ✅ Only "Build Font" / "Rebuild Font" button remains (when not in Avar2 Preview mode)

---

## Test 6: Add Axis Button Styling

**Steps:**
1. Enable Avar2 mode (should be enabled by default)
2. Scroll to Avar2 section in sidebar
3. Find "Add Axis" button
4. Compare with "Update Instance" and "Reset Original" buttons

**Pass Criteria:**
- ✅ "Add Axis" button uses same styling as "Update Instance" and "Reset Original"
- ✅ Same font-size (0.6375rem), padding (0.75rem 1rem), width (100%)
- ✅ Same font-family (monospace) and colors

---

## Test 7: Avar2 Shown by Default

**Steps:**
1. Load the page
2. Check if Avar2 section is visible without toggling
3. Check Header - should NOT have "Show Avar2" toggle checkbox

**Pass Criteria:**
- ✅ Avar2 section visible immediately on page load
- ✅ No "Show Avar2" toggle checkbox in header
- ✅ Avar2 data loads automatically

---

## Test 8: Update Instance Disabled with Unsaved Changes

**Prerequisites:** macOS with Glyphs.app installed

**Steps:**
1. Open `sources/Crispy.glyphs` in Glyphs.app
2. Make a change (e.g., modify a glyph, change an instance name)
3. **DO NOT SAVE** the file
4. In preview tool, select an instance
5. Make changes to axis coordinates
6. Try to click "Update Instance" button

**Pass Criteria:**
- ✅ "Update Instance" button is disabled when Glyphs file has unsaved changes
- ✅ Button shows tooltip: "Save Glyphs file before updating instance"
- ✅ Button becomes enabled after saving Glyphs file

**Alternative Test (if Glyphs.app not available):**
- Backend endpoint `/api/glyphs-file-status` should return `{"has_unsaved_changes": false}` when file is not open or saved

---

## Test 9: Scenario - Launching with New Glyphs File

**Steps:**
1. Create a backup of current Glyphs file
2. Create a new minimal Glyphs file or use a test file
3. Start server with: `python glyphs-preview-server.py --glyphs path/to/new/file.glyphs`
4. Open browser

**Expected Outcome:**
- ✅ Server auto-builds font on startup
- ✅ Page auto-builds font if missing on load
- ✅ Instances load from new file
- ✅ Avar2 section shows (if CSV exists or is created)
- ✅ SPAC font generates if designspace/UFOs don't exist

---

## Test 10: Scenario - Launching with Already Edited Glyphs File

**Steps:**
1. Use existing `sources/Crispy.glyphs` (already has instances edited via tool)
2. Start server
3. Open browser

**Expected Outcome:**
- ✅ Server auto-builds font on startup
- ✅ Instances load with previously saved coordinates
- ✅ SPAC values load from CSV if SPAC axis exists
- ✅ All coordinates match what's in Glyphs file and CSV

---

## Test 11: Scenario - Updating Instance with Saved Glyphs File

**Steps:**
1. Ensure Glyphs file is saved (no unsaved changes)
2. Select an instance
3. Change axis coordinates (parametric axes)
4. Change SPAC value (if SPAC mode enabled)
5. Click "Update Instance"

**Expected Outcome:**
- ✅ "Update Instance" button is enabled
- ✅ Parametric axis changes saved to Glyphs file
- ✅ SPAC value saved to CSV
- ✅ Font rebuilds automatically
- ✅ Orange sync indicator clears after update
- ✅ Changes persist after page refresh

---

## Test 12: Scenario - Updating Instance with Unsaved Glyphs File

**Steps:**
1. Open Glyphs file in Glyphs.app
2. Make a change, **DO NOT SAVE**
3. In preview tool, select an instance
4. Change axis coordinates
5. Try to click "Update Instance"

**Expected Outcome:**
- ✅ "Update Instance" button is disabled
- ✅ Tooltip explains why (save file first)
- ✅ After saving Glyphs file, button becomes enabled
- ✅ Update proceeds normally after enabling

---

## Test 13: Polling for Unsaved Changes

**Steps:**
1. Open Glyphs file in Glyphs.app
2. Make a change, **DO NOT SAVE**
3. In preview tool, wait 2-3 seconds
4. Check "Update Instance" button state

**Expected Outcome:**
- ✅ Button becomes disabled within ~2 seconds of making unsaved change
- ✅ Button becomes enabled within ~2 seconds of saving file
- ✅ No console errors related to polling

---

## Test 14: Font Rebuild on Hard Reset

**Steps:**
1. Ensure font is built
2. Delete font file: `rm preview-app/preview-fonts/Crispy-VF.ttf`
3. Hard refresh browser (Cmd+Shift+R)
4. Monitor network tab for `/api/build` request

**Expected Outcome:**
- ✅ Page detects missing font
- ✅ Automatically calls `/api/build`
- ✅ Font rebuilds
- ✅ Font loads and displays correctly

---

## Summary Checklist

- [ ] Test 1: Server startup auto-build
- [ ] Test 2: Hard reset auto-build
- [ ] Test 3: SPAC axis slider styling
- [ ] Test 4: Font Size label styling
- [ ] Test 5: Refresh button removal
- [ ] Test 6: Add Axis button styling
- [ ] Test 7: Avar2 shown by default
- [ ] Test 8: Update Instance disabled with unsaved changes
- [ ] Test 9: Launching with new Glyphs file
- [ ] Test 10: Launching with already edited Glyphs file
- [ ] Test 11: Updating instance with saved Glyphs file
- [ ] Test 12: Updating instance with unsaved Glyphs file
- [ ] Test 13: Polling for unsaved changes
- [ ] Test 14: Font rebuild on hard reset

---

## Known Limitations

1. **Unsaved changes detection:** Only works on macOS with Glyphs.app. On other platforms, always returns `false` (button always enabled).
2. **Auto-build on startup:** May take 10-30 seconds depending on font complexity.
3. **SPAC font generation:** First-time generation may take longer as it runs `add-spac-axis-ufo.py`.

---

## Quick Test Commands

```bash
# Start backend
cd scripts && python glyphs-preview-server.py

# Start frontend (development)
cd preview-app && npm start

# Build frontend (production)
cd preview-app && npm run build && serve -s build -l 3000

# Check font status
curl http://localhost:5001/api/health

# Check Glyphs file unsaved status
curl http://localhost:5001/api/glyphs-file-status

# Manually trigger build
curl -X POST http://localhost:5001/api/build
```
