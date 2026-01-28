# Testing Status - Ready for Manual Testing

## ✅ Code Implementation Complete

All code changes have been implemented and verified:

1. ✅ SPAC axis slider styling - Uses `AxisControl.css`
2. ✅ Font Size label styling - Matches `axis-name` styling  
3. ✅ Auto-build on server startup - Code added
4. ✅ Auto-build on hard reset - Code added to `loadData()`
5. ✅ Refresh button removed - Removed from `Header.js`
6. ✅ Update Instance disabled logic - Code added (needs server restart)
7. ✅ Add Axis button styling - Matches Update/Reset buttons
8. ✅ Avar2 shown by default - Always enabled, no toggle

## ⚠️ Server Restart Required

The `/api/glyphs-file-status` endpoint has been added but the server needs to be restarted to load it.

**Current Status:**
- Endpoint added to code ✓
- Function `_check_glyphs_file_unsaved_changes()` exists ✓
- Endpoint route added ✓

## 🧪 Testing Instructions

### Step 1: Restart Backend Server (WITH VENV ACTIVATION)

**IMPORTANT:** You must activate the virtual environment first!

```bash
# Activate virtual environment
cd /Users/agyei/Documents/Crispy
source venv/bin/activate

# Stop any running servers
pkill -f glyphs-preview-server.py

# Start server (will auto-build font on startup)
cd scripts
python glyphs-preview-server.py --glyphs ../sources/Crispy.glyphs --build-dir ../preview-app/preview-fonts
```

**OR use the launch script (recommended):**
```bash
cd /Users/agyei/Documents/Crispy
./scripts/launch-preview.sh
```

**Expected Output:**
```
Auto-building font on startup...
Building font from /Users/agyei/Documents/Crispy/sources/Crispy.glyphs...
✓ Font built successfully on startup: /Users/agyei/Documents/Crispy/preview-app/preview-fonts/Crispy-VF.ttf
```

### Step 2: Verify Endpoint

In a new terminal (with venv activated):
```bash
cd /Users/agyei/Documents/Crispy
source venv/bin/activate
curl http://localhost:5001/api/glyphs-file-status | python3 -m json.tool

# Expected response:
# {
#     "has_unsaved_changes": false,
#     "file_path": "/Users/agyei/Documents/Crispy/sources/Crispy.glyphs"
# }
```

### Step 3: Open Browser and Test UI

1. **Open:** http://localhost:3000
2. **Verify Visual Changes:**
   - ✅ No "Refresh" button in header
   - ✅ No "Show Avar2" checkbox (Avar2 section visible by default)
   - ✅ SPAC slider matches parametric axis sliders
   - ✅ Font Size label matches axis labels
   - ✅ "Add Axis" button matches "Update Instance" button

### Step 4: Test Auto-Build on Hard Reset

1. Delete font: `rm preview-app/preview-fonts/Crispy-VF.ttf`
2. Hard refresh browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
3. Check Network tab for `/api/build` request
4. Verify font rebuilds automatically

### Step 5: Test Unsaved Changes Detection

**Prerequisites:** macOS with Glyphs.app installed

1. Open `sources/Crispy.glyphs` in Glyphs.app
2. Make a change (e.g., modify a glyph)
3. **DO NOT SAVE**
4. In preview tool (http://localhost:3000):
   - Select an instance
   - Change axis coordinates
   - Verify "Update Instance" button is **disabled**
   - Check tooltip: "Save Glyphs file before updating instance"
5. Save Glyphs file (Cmd+S)
6. Wait 2-3 seconds
7. Verify "Update Instance" button becomes **enabled**

### Step 6: Test Instance Update Flow

1. Ensure Glyphs file is saved
2. Select an instance
3. Change parametric axis coordinates (XTRA, XOPQ, YOPQ)
4. Change SPAC value (if SPAC mode enabled)
5. Click "Update Instance"
6. Verify:
   - ✅ Parametric axes saved to Glyphs file
   - ✅ SPAC value saved to CSV
   - ✅ Font rebuilds automatically
   - ✅ Orange sync indicator clears
   - ✅ Changes persist after page refresh

## 📋 Quick Test Checklist

- [ ] Activate venv: `source venv/bin/activate`
- [ ] Restart backend server
- [ ] Verify `/api/glyphs-file-status` endpoint works
- [ ] Verify auto-build on startup (check logs)
- [ ] Open browser and verify UI changes
- [ ] Test hard reset auto-build
- [ ] Test unsaved changes detection (with Glyphs.app)
- [ ] Test instance update flow
- [ ] Verify all styling matches requirements

## 🐛 Troubleshooting

### Flask Module Not Found
**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:** Activate the virtual environment first:
```bash
source venv/bin/activate
```

Then run the server. The venv has Flask and all dependencies installed.

### Using Launch Script (Easiest)
The `launch-preview.sh` script handles venv activation automatically:
```bash
./scripts/launch-preview.sh
```

## 📝 Notes

- Unsaved changes detection only works on macOS with Glyphs.app
- Auto-build may take 10-30 seconds depending on font complexity
- SPAC font generation on first run may take longer

## ✅ Ready to Commit

Once all tests pass, the changes are ready to commit.
