# Avar2 Preview Mode Implementation Plan

## Overview
Add an "avar2 mode" to the preview tool that displays relationships between traditional axes (WGHT, WDTH, OPSZ) and parametric axes (XTRA, XOPQ, YOPQ, SPAC) from the CSV mappings.

## Current System Understanding

### Glyphs Mode (Current)
- Reads instances directly from Glyphs file
- Shows axes: XTRA, XOPQ, YOPQ, SPAC (parametric axes)
- Builds with `fontmake` directly from Glyphs file
- No avar2 mappings involved

### Avar2 Mode (New)
- Reads instances from Glyphs file (source of truth)
- Matches instances to CSV mappings by exact name
- Shows traditional axes (WGHT, WDTH, OPSZ) and their parametric mappings
- Builds with `gftools builder` using `config.yaml` (includes avar2 table)
- Displays relationships: traditional → parametric

## Implementation Phases

### Phase 1: Instance Matching & Data Structure ✅ (Current Focus)
**Goal:** Create script to match Glyphs instances to CSV mappings and display relationships

**Deliverables:**
1. `scripts/match-instances-to-avar2.py`
   - Read instances from Glyphs file
   - Read CSV mappings
   - Match by exact instance name
   - Return structured data showing relationships

**Data Structure:**
```python
{
  "instance_name": "Regular",
  "glyphs_coordinates": {
    "XTRA": 627.0,
    "XOPQ": 187.672,
    "YOPQ": 160.0,
    "SPAC": 25
  },
  "avar2_mapping": {
    "in": {
      "wght": 400,
      "wdth": 100,
      "opsz": 48
    },
    "out": {
      "XTRA": 627.0,
      "XOPQ": 187.672,
      "YOPQ": 160.0,
      "SPAC": 25
    }
  },
  "match_status": "matched" | "missing_in_csv" | "missing_in_glyphs",
  "coordinate_mismatch": {
    "axis": "XTRA",
    "glyphs_value": 627.0,
    "csv_value": 627.0,
    "differs": false
  }
}
```

**Validation:**
- CSV parametric values should match Glyphs file values for axes present in Glyphs
- Flag instances in CSV but not in Glyphs (for future import)
- Detect coordinate mismatches

### Phase 2: Backend API Endpoints
**Goal:** Add API endpoints to serve avar2 data to frontend

**New Endpoints:**
- `GET /api/avar2/instances` - Returns matched instances with avar2 relationships
- `GET /api/avar2/mappings` - Returns all CSV mappings
- `GET /api/avar2/axes` - Returns traditional axes (in:) and parametric axes (out:)
- `POST /api/avar2/sync-csv` - Updates CSV values to match Glyphs file

**Modifications:**
- Update `scripts/glyphs-preview-server.py`
- Add CSV reading functions
- Add instance matching logic
- Add coordinate comparison logic

### Phase 3: Frontend Display (Read-Only)
**Goal:** Display avar2 relationships in the UI

**UI Components:**
- Mode toggle: "Glyphs Mode" vs "Avar2 Mode"
- Instance list showing:
  - Instance name
  - Traditional axes (WGHT, WDTH, OPSZ) with values
  - Parametric axes (XTRA, XOPQ, YOPQ, SPAC) with values
  - Visual indicator showing relationship (traditional → parametric)
- Warning indicators for:
  - Instances in CSV but not in Glyphs
  - Coordinate mismatches

**Modifications:**
- Update `preview-app/src/App.js` - Add mode state
- Create `preview-app/src/components/Avar2InstanceRow.js` - Display avar2 instance
- Update `preview-app/src/components/Sidebar.js` - Show traditional axes in avar2 mode
- Update `preview-app/src/api.js` - Add avar2 API calls

### Phase 4: Build Integration (Future)
**Goal:** Build font using `gftools builder` with `config.yaml`

**Requirements:**
- Generate `config.yaml` from CSV (using `update_config.py`)
- Call `gftools builder` instead of `fontmake`
- Handle build output from `fonts/variable/` directory
- Support OPSZ expansion, SPAC axis, etc. via config

### Phase 5: Visualization Tools (Future)
**Goal:** Toggleable features to preview axis additions

**Tools:**
- "Add SPAC Axis" - Show how SPAC would be added
- "Add OPSZ Expansion" - Show MinOPSZ/MaxOPSZ instances
- "Add Contrast Axis" - Show contrast variations

## Testing Plan

### Unit Tests

#### Test 1: Instance Matching
```python
def test_match_instances_exact_name():
    """Test matching instances by exact name"""
    glyphs_instances = {"Regular": {...}, "Bold": {...}}
    csv_rows = [{"Instance Name": "Regular", ...}, {"Instance Name": "Bold", ...}]
    matches = match_instances(glyphs_instances, csv_rows)
    assert matches["Regular"]["match_status"] == "matched"
    assert matches["Bold"]["match_status"] == "matched"
```

#### Test 2: Coordinate Comparison
```python
def test_coordinate_mismatch_detection():
    """Test detection of coordinate mismatches"""
    glyphs_coords = {"XTRA": 627.0, "XOPQ": 187.672}
    csv_coords = {"XTRA": 630.0, "XOPQ": 187.672}
    mismatches = compare_coordinates(glyphs_coords, csv_coords)
    assert mismatches["XTRA"]["differs"] == True
    assert mismatches["XOPQ"]["differs"] == False
```

#### Test 3: Missing Instance Detection
```python
def test_missing_instance_detection():
    """Test detection of instances in CSV but not in Glyphs"""
    glyphs_instances = {"Regular": {...}}
    csv_rows = [{"Instance Name": "Regular", ...}, {"Instance Name": "ExtraBold", ...}]
    matches = match_instances(glyphs_instances, csv_rows)
    assert matches["ExtraBold"]["match_status"] == "missing_in_glyphs"
```

### Integration Tests

#### Test 1: API Endpoint - Get Instances
```bash
curl http://localhost:5001/api/avar2/instances
# Should return JSON with matched instances
```

#### Test 2: API Endpoint - Get Mappings
```bash
curl http://localhost:5001/api/avar2/mappings
# Should return all CSV mappings
```

#### Test 3: API Endpoint - Sync CSV
```bash
curl -X POST http://localhost:5001/api/avar2/sync-csv
# Should update CSV values to match Glyphs file
```

### Manual Testing Checklist

#### Phase 1 Testing
- [ ] Script reads Glyphs file correctly
- [ ] Script reads CSV file correctly
- [ ] Matching by exact name works
- [ ] Coordinate comparison works
- [ ] Missing instance detection works
- [ ] Output format is correct JSON

#### Phase 2 Testing
- [ ] API endpoints return correct data
- [ ] Error handling works (missing files, invalid data)
- [ ] CSV sync updates values correctly
- [ ] API responses are properly formatted

#### Phase 3 Testing
- [ ] Mode toggle switches between Glyphs and Avar2 modes
- [ ] Instance list displays correctly in Avar2 mode
- [ ] Traditional axes are shown correctly
- [ ] Parametric axes are shown correctly
- [ ] Warning indicators appear for mismatches
- [ ] UI is responsive and works on different screen sizes

## Critical Steps

### Step 1: Create Matching Script ✅
**File:** `scripts/match-instances-to-avar2.py`
- Read Glyphs instances
- Read CSV mappings
- Match by exact name
- Compare coordinates
- Return structured data

**Dependencies:**
- `glyphsLib` (already in requirements)
- `csv` (standard library)
- `pathlib` (standard library)

### Step 2: Add Backend Endpoints
**File:** `scripts/glyphs-preview-server.py`
- Import matching script functions
- Add `/api/avar2/instances` endpoint
- Add `/api/avar2/mappings` endpoint
- Add `/api/avar2/axes` endpoint
- Add `/api/avar2/sync-csv` endpoint

**Dependencies:**
- Flask (already in use)
- CSV reading functions

### Step 3: Update Frontend
**Files:**
- `preview-app/src/App.js` - Add mode state
- `preview-app/src/components/Avar2InstanceRow.js` - New component
- `preview-app/src/components/Sidebar.js` - Update for avar2 mode
- `preview-app/src/api.js` - Add API calls

**Dependencies:**
- React (already in use)
- Existing API client structure

## File Structure

```
scripts/
  match-instances-to-avar2.py  # NEW: Instance matching logic
  glyphs-preview-server.py      # MODIFY: Add avar2 endpoints

preview-app/src/
  components/
    Avar2InstanceRow.js        # NEW: Display avar2 instance
    InstanceRow.js             # MODIFY: Support avar2 mode
    Sidebar.js                 # MODIFY: Show traditional axes in avar2 mode
  App.js                       # MODIFY: Add mode toggle
  api.js                       # MODIFY: Add avar2 API calls
```

## Questions & Clarifications

### Resolved ✅
1. ✅ Instance matching: Exact name match from Glyphs file
2. ✅ Missing instances: Flag CSV instances not in Glyphs (future import)
3. ✅ Display format: Show CSV coords, list traditional → parametric relationship
4. ✅ Coordinate updates: Update CSV to match Glyphs (like `make build` does)
5. ✅ Config file: Work with CSV directly for now
6. ✅ Build process: Use `gftools builder` with `config.yaml` (Phase 4)
7. ✅ Automation functions: Toggleable visualization tools (Phase 5)

### Open Questions
1. **CSV Update Behavior:** When updating CSV to match Glyphs, should we:
   - Update only parametric axes (XTRA, XOPQ, YOPQ, SPAC)?
   - Keep traditional axes (WGHT, WDTH, OPSZ) unchanged?
   - **Assumption:** Update only parametric axes that exist in Glyphs file

2. **Instance Display Order:** Should instances be:
   - Sorted by traditional axis values (WGHT, WDTH, OPSZ)?
   - In the same order as Glyphs file?
   - **Assumption:** Same order as Glyphs file (source of truth)

3. **Error Handling:** If CSV is malformed or missing:
   - Show error message?
   - Fall back to Glyphs mode?
   - **Assumption:** Show error message, allow fallback to Glyphs mode

## Next Steps

1. ✅ Create branch: `avar2-preview-mode` (DONE)
2. ⏳ Implement Phase 1: Instance matching script
3. ⏳ Test Phase 1: Unit tests and manual testing
4. ⏳ Implement Phase 2: Backend API endpoints
5. ⏳ Test Phase 2: Integration tests
6. ⏳ Implement Phase 3: Frontend display
7. ⏳ Test Phase 3: Manual UI testing
8. ⏳ Phase 4 & 5: Future work
