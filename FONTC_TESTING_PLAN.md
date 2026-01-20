# Fontc Testing Plan for Preview Tool

## Testing Objectives

1. **Functional Comparison**: Compare fontc vs fontmake output
2. **Performance Benchmarking**: Measure build time differences
3. **Compatibility Testing**: Verify fontc output works in browser
4. **Error Handling**: Test error scenarios

## Test Setup

### Branch
- **Branch**: `fontc-preview-testing`
- **Status**: New branch created for testing

### Fontc Installation
- **Method**: Bundle with preview tool
- **Approach**: Download pre-built binary or build from source
- **Location**: TBD (likely `scripts/fontc` or `bin/fontc`)

## Test Cases

### Test 1: Basic Compilation
**Goal**: Verify fontc can compile Crispy.glyphs to variable TTF

**Steps**:
1. Install/build fontc binary
2. Run: `fontc sources/Crispy.glyphs --output-dir test-output/fontc`
3. Run: `fontmake -o variable -g sources/Crispy.glyphs --output-dir test-output/fontmake`
4. Compare outputs

**Metrics**:
- Build time (fontc vs fontmake)
- File size
- Number of axes
- Axis ranges

### Test 2: Output Compatibility
**Goal**: Verify fontc output works in browser

**Steps**:
1. Load fontc-built font in preview tool
2. Load fontmake-built font in preview tool
3. Compare rendering
4. Test axis sliders with both fonts

**Check**:
- Do fonts render correctly?
- Are axes detected correctly?
- Do sliders work?
- Are axis ranges correct?

### Test 3: Functional Differences
**Goal**: Identify any functional differences

**Compare**:
- fvar table structure
- Axis definitions (min, max, default)
- Named instances
- Font metrics
- Glyph outlines (visual comparison)

**Document**:
- Any differences found
- Impact on preview tool
- Whether differences are acceptable

### Test 4: Error Handling
**Goal**: Test error scenarios

**Scenarios**:
- Invalid Glyphs file
- Missing dependencies
- Build failures
- Timeout handling

**Check**:
- Error messages are user-friendly
- Errors are caught and displayed
- Fallback to fontmake works

### Test 5: Performance Benchmarking
**Goal**: Measure speed improvements

**Metrics**:
- Build time (seconds)
- Memory usage
- CPU usage

**Test**:
- Run 10 builds each, average times
- Compare fontc vs fontmake

## Success Criteria

### Must Have
- ✅ Fontc compiles Crispy.glyphs successfully
- ✅ Output works in browser/preview tool
- ✅ Axes are detected correctly
- ✅ Build time is faster (or at least not slower)
- ✅ Error handling works

### Nice to Have
- ✅ Significant speed improvement (2x+ faster)
- ✅ Smaller file sizes
- ✅ Better error messages

## Implementation Plan

### Phase 1: Setup (Current)
- [x] Create testing branch
- [ ] Install/build fontc binary
- [ ] Set up test directories

### Phase 2: Basic Testing
- [ ] Test fontc compilation
- [ ] Compare outputs side-by-side
- [ ] Document differences

### Phase 3: Integration Testing
- [ ] Integrate fontc into preview server
- [ ] Add fallback to fontmake
- [ ] Test end-to-end

### Phase 4: Performance Testing
- [ ] Benchmark build times
- [ ] Measure resource usage
- [ ] Compare with fontmake

### Phase 5: Documentation
- [ ] Document differences found
- [ ] Create migration guide
- [ ] Update README

## Rollback Plan

If tests fail or show unacceptable differences:
- Keep fontmake as default
- Document issues found
- Consider fontc again when issues are resolved

## Next Steps

1. Install/build fontc binary
2. Run Test 1 (Basic Compilation)
3. Compare outputs
4. Document findings
