# Fontc Migration Analysis

## Current Build Process

### Tools Used
1. **gftools builder** - Orchestrates build pipeline
   - Internally uses **fontmake** for `buildVariable` step
   - Performs multiple post-processing steps:
     - `fix` - Font fixes and optimizations
     - `BuildSTAT` - Builds STAT table from config.yaml
     - `AddSpacingAxis` - Adds SPAC axis programmatically
     - `BuildAvar2` - Builds avar2 table from config.yaml
     - `BuildFvarInstances` - Creates named instances from config.yaml

2. **gftools avar2-to-avar1** - Converts avar2 table to avar1

3. **Custom Python scripts** - Update config.yaml with STAT and avar2 sections

### Critical Features Required
- ✅ Glyphs file compilation (`.glyphs` → variable TTF)
- ✅ config.yaml support (fvarInstances, stat, avar2 sections)
- ✅ STAT table generation with style linking
- ✅ avar2 table generation (192 mappings: traditional → parametric axes)
- ✅ SPAC axis addition (programmatic, not from Glyphs file)
- ✅ fvarInstances creation (8 named instances)
- ✅ avar2-to-avar1 conversion (backward compatibility)

### Current Build Flow
```
sources/Crispy.glyphs
         ↓
gftools builder (uses fontmake)
         ↓
fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf
         ↓
gftools avar2-to-avar1
         ↓
fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf
```

---

## Fontc Overview

**Fontc** ([github.com/googlefonts/fontc](https://github.com/googlefonts/fontc)) is a Rust-based font compiler that aims to replace fontmake. It's part of Google Fonts' "oxidize" strategy to move away from Python/C++ to Rust.

### Key Characteristics
- **Language**: Rust (fast, memory-safe)
- **Architecture**: Source → IR (Intermediate Representation) → Font Binary
- **Status**: Actively developed, tracking compatibility via [fontc_crater](https://googlefonts.github.io/fontc_crater/)
- **Source Support**: Glyphs files (via `glyphs2fontir`), designspace files (via `ufo2fontir`)

---

## Compatibility Analysis

### ✅ What Fontc Supports

1. **Glyphs File Compilation**
   - ✅ Supports `.glyphs` files via `glyphs2fontir` crate
   - ✅ Can compile to variable TTF
   - ✅ Handles variable font axes from Glyphs file

2. **Basic Variable Font Building**
   - ✅ Creates fvar table
   - ✅ Handles multiple axes
   - ✅ Creates variable font from masters

3. **Designspace Support**
   - ✅ Can work with `.designspace` files (if converted from Glyphs)

### ❓ Unknown / Needs Investigation

1. **config.yaml Format Support**
   - ❓ **CRITICAL**: Does fontc support `gftools builder`'s config.yaml format?
   - ❓ Can fontc read `fvarInstances`, `stat`, `avar2` sections from config.yaml?
   - ❓ Or does it require different configuration format?

2. **gftools builder Integration**
   - ❓ Can `gftools builder` use fontc instead of fontmake?
   - ❓ Or would we need to replace `gftools builder` entirely?
   - ❓ What happens to post-processing steps (BuildSTAT, AddSpacingAxis, BuildAvar2)?

3. **STAT Table Generation**
   - ❓ Does fontc generate STAT tables?
   - ❓ Can it read STAT configuration from config.yaml?
   - ❓ Does it support style linking (Regular→Bold)?

4. **Avar2 Table Support**
   - ❓ **CRITICAL**: Does fontc support avar2 table generation?
   - ❓ Can it read avar2 mappings from config.yaml?
   - ❓ Does it support parametric axes (XTRA, XOPQ, YOPQ, SPAC)?

5. **SPAC Axis Addition**
   - ❓ **CRITICAL**: Can fontc add SPAC axis programmatically (not from Glyphs file)?
   - ❓ Or would we need to add SPAC to the Glyphs file first?

6. **fvarInstances**
   - ❓ Can fontc create named instances from config.yaml?
   - ❓ Does it support the same fvarInstances format?

7. **Post-Processing Tools**
   - ❓ Can `gftools avar2-to-avar1` work with fontc-built fonts?
   - ❓ Are there fontc-native alternatives?

---

## Potential Limitations

### 1. **config.yaml Compatibility**
- **Risk**: Fontc may not support `gftools builder`'s config.yaml format
- **Impact**: Would require rewriting configuration or using different format
- **Mitigation**: May need to keep using gftools builder for post-processing

### 2. **gftools builder Dependency**
- **Risk**: `gftools builder` may still require fontmake internally
- **Impact**: Cannot fully replace fontmake if builder depends on it
- **Mitigation**: May need to use fontc only for initial compilation, keep builder for post-processing

### 3. **Avar2 Table Support**
- **Risk**: Fontc may not support avar2 table generation yet
- **Impact**: Would need to use gftools builder for avar2 step anyway
- **Mitigation**: Check fontc documentation/issue tracker for avar2 support

### 4. **SPAC Axis Addition**
- **Risk**: Fontc may not support programmatic axis addition
- **Impact**: Would need to add SPAC axis to Glyphs file manually
- **Mitigation**: Could use gftools builder's AddSpacingAxis step after fontc compilation

### 5. **STAT Table Generation**
- **Risk**: Fontc may not support STAT table generation from config
- **Impact**: Would need gftools builder for STAT step
- **Mitigation**: Use fontc for compilation, builder for STAT

### 6. **Maturity / Stability**
- **Risk**: Fontc is still in active development
- **Impact**: May have bugs or missing features
- **Mitigation**: Check fontc_crater for compatibility tracking

### 7. **Build Pipeline Complexity**
- **Risk**: Hybrid approach (fontc + gftools builder) adds complexity
- **Impact**: More moving parts, harder to debug
- **Mitigation**: Clear documentation of which tool does what

---

## Migration Strategy Options

### Option A: Full Replacement
**Replace fontmake entirely with fontc**
- Use fontc for all compilation
- Replace gftools builder with fontc-native tools
- **Pros**: Clean, single toolchain
- **Cons**: Requires fontc to support all features (unlikely currently)

### Option B: Hybrid Approach
**Use fontc for compilation, keep gftools builder for post-processing**
- Fontc: Compile Glyphs → variable TTF (basic)
- gftools builder: Add STAT, avar2, SPAC axis, fvarInstances
- **Pros**: Can migrate incrementally, use fontc speed benefits
- **Cons**: Still depends on Python toolchain, more complex

### Option C: Wait and See
**Monitor fontc development until feature parity**
- Continue with fontmake
- Track fontc progress via fontc_crater
- **Pros**: Lower risk, wait for maturity
- **Cons**: Miss out on speed benefits, longer Python dependency

---

## Questions for Clarification

### 1. **Build Process Priorities**
- **Speed**: Is build speed a current pain point? (fontc is faster)
- **Python dependency**: Is removing Python dependency a goal?
- **Feature completeness**: Is feature parity more important than speed?

### 2. **config.yaml Format**
- Can we modify config.yaml format if needed?
- Or must we maintain compatibility with gftools builder format?

### 3. **SPAC Axis**
- Is it acceptable to add SPAC axis to Glyphs file instead of programmatically?
- Or must SPAC remain programmatic (added during build)?

### 4. **Migration Timeline**
- Is this an immediate need or future consideration?
- Are we willing to accept a hybrid approach temporarily?

### 5. **Testing Strategy**
- How do we validate fontc output matches fontmake output?
- Do we need bit-identical fonts or functionally equivalent?

### 6. **gftools builder Future**
- Is gftools builder planning to support fontc as backend?
- Or should we plan to replace builder entirely?

---

## Recommended Next Steps

1. **Investigate fontc capabilities**
   - Check fontc documentation for config.yaml support
   - Test fontc with a simple Glyphs file
   - Check fontc issue tracker for avar2/STAT support

2. **Test compatibility**
   - Try compiling Crispy.glyphs with fontc
   - Compare output with fontmake output
   - Identify missing features

3. **Evaluate hybrid approach**
   - Test fontc compilation + gftools builder post-processing
   - Measure speed improvements
   - Assess complexity

4. **Decision point**
   - Based on findings, choose migration strategy
   - Plan implementation if proceeding

---

## References

- Fontc repository: https://github.com/googlefonts/fontc
- Fontc crater (compatibility tracking): https://googlefonts.github.io/fontc_crater/
- Google Fonts oxidize strategy: https://github.com/googlefonts/oxidize
- Current build flow: See `BUILD_FLOW.md`
