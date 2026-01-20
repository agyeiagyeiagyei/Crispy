# Fontc for Web Preview Tool - Analysis

## Current Preview Tool Build Process

### Current Implementation
- **Location**: `scripts/glyphs-preview-server.py`
- **Function**: `build_variable_font()`
- **Tool Used**: `fontmake`
- **Command**: `fontmake -o variable -g sources/Crispy.glyphs --output-dir <dir>`

### What the Preview Tool Needs
1. ✅ Compile Glyphs file to variable TTF
2. ✅ Serve font file to frontend via `/api/font` endpoint
3. ✅ Extract axes from built font for display
4. ✅ Fast build times (user-facing, needs to be quick)
5. ✅ Reliable builds (shouldn't fail unexpectedly)

### Current Limitations
- **Speed**: fontmake (Python) can be slow for large fonts
- **Dependencies**: Requires Python environment with fontmake installed
- **Build time**: May take several seconds for complex fonts

---

## Fontc for Preview Tool

### Potential Benefits
1. **Speed**: Rust-based, significantly faster than Python fontmake
2. **Self-contained**: Single binary, no Python dependencies
3. **Better performance**: Faster compilation = better UX

### What Fontc Supports (for preview tool)
- ✅ Glyphs file compilation (`.glyphs` → variable TTF)
- ✅ Variable font output
- ✅ Fast compilation
- ✅ Can be called as CLI tool

### What Preview Tool Doesn't Need
- ❌ config.yaml support (preview tool doesn't use it)
- ❌ STAT table generation (not needed for preview)
- ❌ avar2 table generation (not needed for preview)
- ❌ SPAC axis addition (not needed for preview)
- ❌ fvarInstances (not needed for preview)
- ❌ avar2-to-avar1 conversion (not needed for preview)

**Key Insight**: Preview tool only needs basic Glyphs → variable TTF compilation!

---

## Implementation Considerations

### 1. **Fontc Installation**
- **Question**: How do we install fontc?
  - Option A: Download pre-built binary
  - Option B: Build from source (requires Rust toolchain)
  - Option C: Include in Docker/container if using one

### 2. **Command Line Interface**
- **Current**: `fontmake -o variable -g <glyphs> --output-dir <dir>`
- **Fontc**: `fontc <glyphs>` or `fontc <designspace>`
- **Question**: Does fontc support equivalent output options?

### 3. **Output Format**
- **Current**: fontmake outputs `.ttf` files
- **Fontc**: Also outputs `.ttf` files
- **Question**: Are output formats compatible?

### 4. **Error Handling**
- **Current**: fontmake errors are caught and displayed
- **Fontc**: Different error format?
- **Question**: How do we handle fontc errors in the preview tool?

### 5. **Build Speed Comparison**
- **Current**: fontmake can take 5-30 seconds depending on font complexity
- **Fontc**: Should be faster, but needs testing
- **Question**: What's the actual speedup for Crispy font?

### 6. **Dependencies**
- **Current**: Requires Python venv with fontmake
- **Fontc**: Requires Rust binary (or Rust toolchain to build)
- **Question**: Is Rust installation acceptable for preview tool?

### 7. **Backward Compatibility**
- **Question**: Should we support both fontmake and fontc?
- **Question**: Add toggle/flag to choose compiler?

---

## Potential Limitations

### 1. **Fontc Maturity**
- **Risk**: Fontc is still in development
- **Impact**: May have bugs or produce different output than fontmake
- **Mitigation**: Test thoroughly, have fontmake as fallback

### 2. **Output Differences**
- **Risk**: Fontc may produce slightly different fonts than fontmake
- **Impact**: Preview may not match final build output
- **Mitigation**: Document differences, or use fontmake for preview too

### 3. **Installation Complexity**
- **Risk**: Rust toolchain may be harder to install than Python
- **Impact**: More complex setup for developers/users
- **Mitigation**: Provide pre-built binaries, clear installation docs

### 4. **Feature Parity**
- **Risk**: Fontc may not support all Glyphs features fontmake does
- **Impact**: Some fonts may fail to compile
- **Mitigation**: Test with Crispy font, have fallback

### 5. **Error Messages**
- **Risk**: Fontc error messages may be less helpful than fontmake
- **Impact**: Harder to debug build failures
- **Mitigation**: Wrap fontc calls with better error handling

---

## Implementation Strategy

### Option A: Replace fontmake with fontc
- Modify `build_variable_font()` to use fontc
- Remove fontmake dependency
- **Pros**: Simpler, faster
- **Cons**: Lose fontmake fallback, may have compatibility issues

### Option B: Support Both (with toggle)
- Add configuration to choose compiler
- Default to fontc, fallback to fontmake
- **Pros**: Flexibility, can compare outputs
- **Cons**: More complex code, need to maintain both

### Option C: Hybrid (fontc primary, fontmake fallback)
- Try fontc first, fallback to fontmake on error
- **Pros**: Best of both worlds
- **Cons**: More complex error handling

---

## Questions for Clarification

### 1. **Installation & Distribution**
- How should fontc be installed? (pre-built binary, build from source, Docker?)
- Should it be bundled with the preview tool or installed separately?
- What platforms need to be supported? (macOS, Linux, Windows?)

### 2. **Output Compatibility**
- Is it acceptable if fontc produces slightly different fonts than fontmake?
- Or must preview output match fontmake output exactly?
- Should we validate output matches fontmake?

### 3. **Error Handling**
- How should fontc errors be displayed to users?
- Should we show fontc-specific error messages or generic ones?
- Do we need to translate fontc errors to user-friendly messages?

### 4. **Fallback Strategy**
- Should we keep fontmake as fallback if fontc fails?
- Or is fontc-only acceptable?
- How do we handle fonts that fontc can't compile?

### 5. **Testing**
- Should we test fontc with Crispy font first?
- Do we need to test with other fonts too?
- How do we validate fontc output is correct?

### 6. **Performance Expectations**
- What build time improvement are we expecting?
- Is 2x faster acceptable, or do we need 10x?
- Should we benchmark before/after?

### 7. **User Experience**
- Should users know which compiler is being used?
- Or should it be transparent (just "Build Font" button)?
- Do we need to show build time/comparison?

---

## Recommended Next Steps

1. **Test fontc with Crispy font**
   - Install fontc (or build from source)
   - Try compiling `sources/Crispy.glyphs` with fontc
   - Compare output with fontmake output
   - Measure build time difference

2. **Evaluate output compatibility**
   - Check if fontc output works in browser
   - Verify axes are correct
   - Test font rendering

3. **Implement in preview tool**
   - Modify `build_variable_font()` function
   - Add fontc command execution
   - Handle fontc-specific errors
   - Test end-to-end

4. **Add fallback (optional)**
   - Keep fontmake as backup
   - Add configuration option
   - Test fallback works

---

## References

- Fontc repository: https://github.com/googlefonts/fontc
- Fontc CLI usage: See fontc README for command-line options
- Current preview server: `scripts/glyphs-preview-server.py`
