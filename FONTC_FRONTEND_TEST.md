# Fontc Frontend Testing Guide

## Setup Complete ✅

The preview server has been updated to use fontc with fontmake fallback.

## Changes Made

1. **Updated `build_variable_font()` function**:
   - Tries fontc first (if binary exists)
   - Falls back to fontmake if fontc fails
   - Uses `--output-file` flag for fontc (instead of `--output-dir`)

2. **Added command-line flag**:
   - `--no-fontc`: Disable fontc and use fontmake only
   - Default: fontc enabled with fallback

3. **Global state**:
   - `USE_FONTC` flag controls compiler selection

## Testing Steps

### 1. Start Preview Server

```bash
cd /Users/agyei/Documents/Crispy
python3 scripts/glyphs-preview-server.py
```

Expected output:
```
Starting server on 127.0.0.1:5001
Glyphs file: /path/to/sources/Crispy.glyphs
Build directory: preview-fonts
Compiler: fontc (with fontmake fallback)
```

### 2. Start Frontend

In a new terminal:
```bash
cd preview-app
npm start
```

### 3. Test Font Building

1. Open browser to `http://localhost:3000`
2. Click "Build Font" button
3. Check server logs for:
   - "Building variable font with fontc: ..."
   - "✅ fontc compilation successful" (if successful)
   - Or "fontc failed, falling back to fontmake" (if fontc fails)

### 4. Verify Font Works

- [ ] Font loads in browser
- [ ] Axes are detected correctly (XTRA, XOPQ, YOPQ)
- [ ] Sliders work correctly
- [ ] Font renders correctly
- [ ] No console errors

### 5. Compare with Fontmake

To test fontmake only (for comparison):
```bash
python3 scripts/glyphs-preview-server.py --no-fontc
```

Then repeat steps 2-4 and compare:
- Build times
- Font rendering
- Axes behavior

## Expected Results

Based on previous testing:
- ✅ fontc compiles instantly (0s vs 2s for fontmake)
- ✅ Same axes output (XTRA, XOPQ, YOPQ)
- ✅ Same file size (74KB)
- ✅ Should work identically in browser

## Troubleshooting

### Fontc not found
- Check `bin/fontc` exists
- Server will automatically fallback to fontmake

### Build fails
- Check server logs for error messages
- Fontmake fallback should handle most cases

### Font doesn't load
- Check browser console for errors
- Verify font file was created in `preview-fonts/`
- Check CORS headers are correct

## Next Steps

After successful testing:
1. Document any differences found
2. Update `FONTC_TEST_RESULTS.md` with frontend test results
3. Consider making fontc the default (already done)
4. Remove fontmake fallback if fontc works perfectly (optional)
