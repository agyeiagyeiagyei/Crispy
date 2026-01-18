# React Frontend Plan for Glyphs Preview Tool

## Overview

A React-based web interface for previewing and fine-tuning variable font instances from a Glyphs file. The frontend connects to the backend server (`glyphs-preview-server.py`) running on port 5000.

## Core Functionality

### 1. Instance Preview Rows
- **Horizontal scrollable rows** showing sample text for each instance
- Each row represents one instance from the Glyphs file (e.g., "ExtraLight Condensed", "Light Condensed", "Regular Condensed", etc.)
- Default sample text: "the quick brown fox jumps over the lazy dog 0123456789 &!"
- Sample text is **user-editable** (can be changed per row or globally)
- Text rendered using the variable font with instance-specific coordinates

### 2. Axis Sidebar
- **Left sidebar** displaying all axes from the Glyphs file
- Only shows axes that exist in the variable font (XTRA, XOPQ, YOPQ - no SPAC or -e axes)
- Each axis has:
  - Name (e.g., "X-Transparency")
  - Tag (e.g., "XTRA")
  - Slider with min/max/default values
  - Current value display
- Sliders update in real-time as user adjusts them

### 3. Row Selection & Editing
- **Click a row** to select it
- Selected row is highlighted
- When a row is selected:
  - Sidebar sliders update to show that instance's coordinates
  - User can adjust sliders to modify that instance
  - Changes are reflected immediately in the preview (using CSS `font-variation-settings`)
  - "Update Instance" button appears to save changes to Glyphs file

### 4. Font Loading & Building
- On page load:
  - Fetch instances from `/api/instances`
  - Fetch axes from `/api/axes` (or from Glyphs file if font not built)
  - Check if font is built via `/api/health`
  - If not built, show "Build Font" button
- "Build Font" button:
  - Calls `POST /api/build`
  - Shows loading state during build
  - On success, loads font from `/api/font` and enables previews

### 5. Instance Updates
- "Update Instance" button (only shown when row is selected):
  - Sends `PUT /api/instance/<name>` with current slider values
  - Shows success/error feedback
  - Optionally rebuilds font after update

### 6. Manual Refresh
- "Refresh" button to reload data from server
- Useful if Glyphs file is modified externally

## Technical Implementation

### Component Structure
```
App
├── Header
│   ├── Build Font button
│   ├── Refresh button
│   └── Sample text input (global)
├── Sidebar
│   └── AxisControls (one per axis)
│       ├── Axis name/tag
│       ├── Slider (min/max/default)
│       └── Value display
├── Main Content
│   └── InstanceRow[] (scrollable)
│       ├── Instance name
│       ├── Sample text input (per-row)
│       ├── Preview text (with font-variation-settings)
│       └── Selection indicator
└── Footer
    └── Update Instance button (conditional)
```

### State Management
- **Selected instance**: Currently selected row
- **Instance data**: Array of instances with coordinates
- **Axis data**: Array of axes with min/max/default
- **Font loaded**: Boolean, font file URL
- **Editing coordinates**: Current slider values (may differ from instance until saved)
- **Sample text**: Global and per-instance

### CSS Font Loading
- Use `@font-face` with variable font
- Apply `font-variation-settings` CSS property:
  ```css
  font-variation-settings: "XTRA" 290, "XOPQ" 147, "YOPQ" 130;
  ```
- Update dynamically as sliders change

### API Integration
- Base URL: `http://localhost:5000/api`
- Endpoints:
  - `GET /api/health` - Check server status
  - `GET /api/instances` - Get all instances
  - `GET /api/axes` - Get axes (from Glyphs or built font)
  - `POST /api/build` - Build variable font
  - `GET /api/font` - Download font file
  - `PUT /api/instance/<name>` - Update instance coordinates

## User Flow

1. **Initial Load**
   - Page loads, fetches instances and axes
   - If font not built, shows "Build Font" button
   - User clicks "Build Font" → font builds → previews enabled

2. **Preview Instances**
   - All instances shown in scrollable rows
   - Each row shows sample text in that instance's style
   - User can edit sample text per row

3. **Select & Edit Instance**
   - User clicks a row → row highlights, sliders update
   - User adjusts sliders → preview updates in real-time
   - User clicks "Update Instance" → saves to Glyphs file

4. **Fine-tune Multiple Instances**
   - User can select different rows and adjust each
   - Changes saved individually per instance

## Questions for Clarification

1. **Sample Text Scope**
   - Should sample text be editable per-row only, or also globally?
   - Should there be a "default text" that can be applied to all rows?

2. **Font Rebuild After Update**
   - Should the font automatically rebuild after updating an instance?
   - Or should there be a separate "Rebuild Font" button?

3. **Row Layout**
   - Should rows be vertically stacked (scrollable)?
   - Or horizontally arranged (side-by-side)?

4. **Update Confirmation**
   - Should there be a confirmation dialog before saving to Glyphs file?
   - Or just a success/error notification?

5. **Multiple Selection**
   - Can multiple instances be selected at once?
   - Or single selection only?

6. **Styling/Theme**
   - Any specific design requirements?
   - Dark/light theme preference?
