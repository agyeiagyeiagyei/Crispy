# Avar2 Frontend Integration Design

## Overview
Add a global avar2 toggle that, when enabled, displays traditional → parametric axis mappings for the selected instance below the axis sliders.

## Design Decisions

### 1. Global Toggle Location
- **Placement**: Header component (top-right, next to Build/Refresh buttons)
- **Type**: Checkbox or toggle switch
- **Label**: "Show Avar2 Mappings" or "Avar2 Mode"
- **State**: Global state in App.js

### 2. Display Location
- **When**: Avar2 mode enabled AND instance selected
- **Where**: Below the axis sliders in Sidebar component
- **Position**: After axis controls, before font size control

### 3. Mapping Display Format

#### Option A: Table Format (Recommended)
```
┌─────────────────────────────────────┐
│ Avar2 Mapping                        │
├─────────────────────────────────────┤
│ Traditional → Parametric            │
├─────────────────────────────────────┤
│ wght: 100.0  →  XTRA: 181.2        │
│ wdth: 52.0   →  XOPQ: 40.3         │
│ opsz: 48.0   →  YOPQ: 41.3         │
│              →  SPAC: 25.0         │
└─────────────────────────────────────┘
```

#### Option B: Two-Column Layout
```
┌─────────────────────────────────────┐
│ Avar2 Mapping                        │
├──────────────┬──────────────────────┤
│ Traditional  │ Parametric           │
├──────────────┼──────────────────────┤
│ wght: 100.0  │ XTRA: 181.2          │
│ wdth: 52.0   │ XOPQ: 40.3           │
│ opsz: 48.0   │ YOPQ: 41.3           │
│              │ SPAC: 25.0           │
└──────────────┴──────────────────────┘
```

#### Option C: Arrow Flow (Visual)
```
┌─────────────────────────────────────┐
│ Avar2 Mapping                        │
├─────────────────────────────────────┤
│ wght: 100.0  ──────→  XTRA: 181.2  │
│ wdth: 52.0   ──────→  XOPQ: 40.3  │
│ opsz: 48.0   ──────→  YOPQ: 41.3  │
│              ──────→  SPAC: 25.0   │
└─────────────────────────────────────┘
```

**Recommendation**: Option A (Table Format) - clean, readable, shows relationship clearly

## Implementation Plan

### Step 1: Add API Methods
Add to `preview-app/src/api.js`:
- `getAvar2Instances()` - Fetch avar2 instance mappings
- `getAvar2Axes()` - Get traditional/parametric axis info

### Step 2: Add Global State
In `App.js`:
- `avar2Mode` state (boolean)
- Load avar2 data when mode enabled
- Pass to Sidebar component

### Step 3: Add Toggle in Header
In `Header.js`:
- Add checkbox/toggle for avar2 mode
- Callback to App.js to toggle state

### Step 4: Create Avar2MappingDisplay Component
New component: `preview-app/src/components/Avar2MappingDisplay.js`
- Props: `selectedInstance`, `avar2Data`
- Display mapping table
- Show "No mapping available" if instance not in CSV

### Step 5: Integrate in Sidebar
In `Sidebar.js`:
- Conditionally render `Avar2MappingDisplay` when:
  - `avar2Mode === true`
  - `selectedInstance !== null`
  - `avar2Data` exists for selected instance

## Data Flow

```
App.js (avar2Mode state)
  ↓
Header (toggle control)
  ↓
App.js (load avar2 data when enabled)
  ↓
Sidebar (receive avar2Mode + avar2Data)
  ↓
Avar2MappingDisplay (render mapping)
```

## API Integration

### Fetch Avar2 Data
```javascript
// In App.js useEffect when avar2Mode changes
if (avar2Mode && selectedInstance) {
  const avar2Data = await api.getAvar2Instances();
  const instanceMapping = avar2Data.instances.find(
    inst => inst.instance_name === selectedInstance.name
  );
  setAvar2Mapping(instanceMapping);
}
```

### Data Structure
```javascript
{
  instance_name: "Thin Condensed",
  glyphs_coordinates: { XTRA: 181.2, XOPQ: 40.3, YOPQ: 41.3 },
  avar2_mapping: {
    in: { wght: 100.0, wdth: 52.0, opsz: 48.0 },
    out: { XTRA: 181.2, XOPQ: 40.3, YOPQ: 41.3, SPAC: 25.0 }
  },
  match_status: "matched"
}
```

## Visual Design Notes

### Styling
- Use subtle background color to distinguish from axis controls
- Match existing Sidebar styling
- Use monospace font for axis tags/values
- Add subtle border/separator above mapping section

### Empty States
- "No avar2 mapping available for this instance" when:
  - Instance not found in CSV
  - CSV not available
  - Avar2 mode disabled

### Loading State
- Show "Loading avar2 mappings..." while fetching

## Questions for User

1. **Display Format**: Which format do you prefer? (Table, Two-Column, Arrow Flow)
2. **Editable Values**: Should traditional axis values be editable, or read-only?
3. **Visual Connection**: Should we visually connect traditional → parametric with arrows/lines?
4. **Missing Mappings**: How should we handle instances without CSV mappings? (Hide section? Show message?)
