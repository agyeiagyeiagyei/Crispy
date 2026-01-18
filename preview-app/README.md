# Glyphs Preview Tool

A web-based preview tool for examining and editing variable font instances from Glyphs files.

## How It Works

The tool consists of two parts:

1. **Backend Server** (Flask): Reads the Glyphs file, builds variable fonts using `fontmake`, and provides a REST API for instance data and font building.

2. **Frontend App** (React): Displays all instances in scrollable rows, allows real-time axis adjustment via sliders, and provides controls for editing instance coordinates.

### Workflow

1. **Load Glyphs File**: The backend reads instances and axes directly from the `.glyphs` file
2. **Build Font**: Click "Build Font" to generate a variable font using `fontmake` (builds to `preview-fonts/` directory)
3. **Preview Instances**: All instances are displayed in rows with their sample text
4. **Edit Coordinates**: Select a row, adjust axes with sliders, and see real-time preview updates
5. **Update Glyphs File**: Click "Update Instance" to save coordinate changes back to the Glyphs file
6. **Auto-rebuild**: Font is automatically rebuilt after updating an instance

### Error Handling

If `fontmake` fails during font building:
- The error message is printed to the server console (stderr)
- The API returns a 500 error with the error message
- The frontend displays the error in an error banner
- Check `/tmp/preview-server.log` for detailed error output

Common `fontmake` errors:
- **Duplicate locations**: Multiple masters/brace layers with identical coordinates
- **Missing dependencies**: Ensure `fontmake` and required Python packages are installed
- **Invalid Glyphs file**: Check for syntax errors or missing masters

## Setup

```bash
cd preview-app
npm install
```

## Development

```bash
npm start
```

The app will run on http://localhost:3000 and proxy API requests to the backend server at http://localhost:5001.

Make sure the backend server is running:
```bash
python3 scripts/glyphs-preview-server.py
```

Or use the launch script:
```bash
./scripts/launch-preview.sh [path/to/font.glyphs]
```

## Features

- **Instance Preview**: View all instances simultaneously in horizontally scrollable rows
- **Variable Font Axes**: Adjust font axes with sliders in the sidebar
- **Real-time Preview**: See changes instantly as you adjust axes
- **Instance Editing**: Update instance coordinates in the Glyphs file
- **Drag-and-Drop Reordering**: Reorder instance rows by dragging
- **Move Instance**: Move instances before/after other instances with dropdown controls
- **Font Size Control**: Adjust preview font size (0.5rem to 7rem)
- **Sample Text**: Customizable sample text with title case (shared across all rows)
- **Instance Removal**: Remove instances from preview (restore by refreshing)
- **Reset Coordinates**: Reset edited coordinates to original values

## API Endpoints

- `GET /api/health` - Health check and font status
- `GET /api/instances` - Get all instances from Glyphs file
- `GET /api/axes` - Get axes from built font
- `POST /api/build` - Build variable font
- `GET /api/font` - Serve variable font file
- `PUT /api/instance/<name>` - Update instance coordinates
