# Preview App Setup Guide

## Quick Start

### 1. Install Dependencies
```bash
cd preview-app
npm install
```

### 2. Start Backend Server
In a separate terminal:
```bash
cd /Users/agyei/Documents/Crispy
. venv/bin/activate
python3 scripts/glyphs-preview-server.py
```

The server will run on http://localhost:5000

### 3. Start React App
```bash
cd preview-app
npm start
```

The app will open at http://localhost:3000 and proxy API requests to the backend.

## Features Implemented

✅ **Instance Preview Rows**
- Vertical stack of rows (one per instance)
- Each row horizontally scrollable for overflow
- Per-row editable sample text
- Default text: "the quick brown fox jumps over the lazy dog 0123456789 &!"

✅ **Axis Sidebar**
- Left sidebar with sliders for XTRA, XOPQ, YOPQ
- Shows axis name, tag, min/max/default values
- Disabled until instance is selected

✅ **Row Selection**
- Click row to select (single selection only)
- Selected row highlighted with blue border
- Sliders update to show selected instance's coordinates

✅ **Real-time Preview**
- Preview updates as sliders change
- Uses CSS `font-variation-settings`
- Only selected row shows editing coordinates, others show instance coordinates

✅ **Instance Updates**
- "Update Instance" button appears when row is selected
- Confirmation dialog before saving
- Auto-rebuilds font after update
- Updates persisted to Glyphs file

✅ **Font Building**
- "Build Font" button if font not built
- Shows loading state during build
- Font loaded via FontFace API

## Component Structure

```
App
├── Header (Build Font, Refresh buttons)
├── Sidebar (Axis sliders)
├── InstanceRows (Container)
│   └── InstanceRow[] (One per instance)
│       ├── Instance name & coordinates
│       ├── Sample text input
│       └── Preview text (with font-variation-settings)
└── UpdateButton (Conditional, when instance selected)
```

## API Integration

All API calls go through `src/api.js`:
- `GET /api/health` - Check server status
- `GET /api/instances` - Get all instances
- `GET /api/axes` - Get axes
- `POST /api/build` - Build variable font
- `GET /api/font` - Download font file
- `PUT /api/instance/<name>` - Update instance

## Next Steps

1. Test the app with the backend server
2. Verify font loading works correctly
3. Test instance updates and font rebuilding
4. Clean up temporary test files (see CLEANUP_LOG.md)
