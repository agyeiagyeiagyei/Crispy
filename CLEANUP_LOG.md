# Cleanup Log - Files to Review for Removal

Based on the work done for the Glyphs preview tool, here are files that may be candidates for cleanup:

## Files Created for Preview Tool (Keep)
- ✅ `scripts/glyphs-preview-server.py` - Main backend server (KEEP)
- ✅ `scripts/fix-brace-layer-names.py` - Brace layer name fixing utility (KEEP - may be useful)
- ✅ `scripts/README-preview-server.md` - Server documentation (KEEP)
- ✅ `REACT_FRONTEND_PLAN.md` - Frontend planning document (KEEP for now)
- ✅ `preview-fonts/` - Build output directory (in .gitignore, KEEP)

## Temporary/Test Files (Review for Removal)
- ⚠️ `sources/Crispy-fixed-brace-names.glyphs` (864KB) - Test file created during brace layer investigation
  - **Status**: Test file with standardized brace layer names
  - **Action**: Can be removed - original file is fixed, this was just for testing
  - **Created**: Jan 18, 2026 during brace layer duplicate investigation

- ⚠️ `sources/preview-fonts-test/` - Temporary test build directory
  - **Status**: Contains test build output from endpoint testing
  - **Action**: Can be removed - preview-fonts/ is the actual build directory

## Files Not Used by Preview Tool (Keep - Used by Other Workflows)
- ✅ `scripts/read-config.py` - Used by Makefile (KEEP)
- ✅ `scripts/set_axis_defaults.py` - Used by production build (KEEP)
- ✅ `scripts/ensure_regular_instance.py` - Used by production build (KEEP)
- ✅ `scripts/mapping.yaml` - Used by avar2-to-avar1 conversion (KEEP)
- ✅ `sources/update_config.py` - Used by production build (KEEP)
- ✅ `sources/gen_avar2.py` - May be used by production build (KEEP)
- ✅ `sources/gen_stat.py` - May be used by production build (KEEP)
- ✅ `sources/expand_contrast.py` - Used by update_config.py (KEEP)
- ✅ `sources/config.yaml` - Production build config (KEEP)
- ✅ `sources/avar2-mappings.csv` - Production build data (KEEP)
- ✅ `sources/axis_defaults.yaml` - Production build defaults (KEEP)

## Files That May Be Obsolete (Investigate)
- ❓ `sources/gen_instances.py` - **DELETED** (was mentioned in deleted_files)
  - **Status**: Already removed
  - **Action**: N/A

## Summary

### Files to Remove:
1. `sources/Crispy-fixed-brace-names.glyphs` (864KB) - Test file, not needed for production
2. `sources/preview-fonts-test/` - Temporary test build directory from endpoint testing

### Files to Keep:
- All scripts in `scripts/` - All are used by either preview tool or production build
- All source files in `sources/` except the test Glyphs file
- All configuration files

### Notes:
- The preview tool is completely separate from the production build workflow
- No conflicts between preview tool files and production build files
- The only cleanup needed is the test Glyphs file created during development
