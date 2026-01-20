# Fontc vs Fontmake Test Results

## Test Date
2026-01-20

## Test Setup
- **Branch**: `fontc-preview-testing`
- **Fontc version**: 0.6.0 (pre-built binary)
- **Fontmake version**: (system default)
- **Test font**: `sources/Crispy.glyphs`

## Compilation Results

### Build Times
- **fontc**: 0s (instantaneous - essentially instant)
- **fontmake**: 2s
- **Speedup**: fontc is significantly faster (essentially instant vs 2 seconds)

### File Sizes
- **fontc output**: 74KB (`test-output/fontc/Crispy-VF.ttf`)
- **fontmake output**: 74KB (`test-output/fontmake/Crispy-VF.ttf`)
- **Difference**: Identical file sizes

### Axes Comparison
- **fontc axes**: `[('XTRA', 94.0, 94.0, 3330.0), ('XOPQ', 2.0, 2.0, 1016.0), ('YOPQ', 2.0, 2.0, 462.0)]`
- **fontmake axes**: `[('XTRA', 94.0, 94.0, 3330.0), ('XOPQ', 2.0, 2.0, 1016.0), ('YOPQ', 2.0, 2.0, 462.0)]`
- **Result**: ✅ **Identical axes** - Same axis tags, ranges, and default values

## Functional Differences

### Axes
- [x] Same axes present ✅
- [x] Same axis ranges ✅
- [x] Same default values ✅

### Output Format
- [x] Both produce valid TTF files ✅
- [ ] Both work in browser (needs testing)
- [ ] Both work in preview tool (needs testing)

## Performance Analysis

### Speed Comparison
- [x] fontc faster ✅ (instantaneous vs 2 seconds)
- [ ] fontc slower
- [ ] Comparable speed

### Resource Usage
- [ ] Memory usage comparison (needs testing)
- [ ] CPU usage comparison (needs testing)

## Key Findings

1. **Speed**: fontc is dramatically faster (instantaneous vs 2 seconds)
2. **Compatibility**: Both produce identical axes and file sizes
3. **Output**: Both generate valid TTF files with same structure

## Browser Compatibility

### Preview Tool Testing
- [ ] fontc output loads correctly
- [ ] Axes detected correctly
- [ ] Sliders work correctly
- [ ] Rendering matches fontmake

## Next Steps

1. Complete side-by-side comparison
2. Test in preview tool
3. Document any differences
4. Decide on implementation approach
