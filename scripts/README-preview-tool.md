# Glyphs Preview Tool

A web-based preview tool for examining and editing variable font instances from a Glyphs file.

## Features

- **Instance Preview**: View all instances simultaneously in horizontally scrollable rows
- **Variable Font Axes**: Adjust font axes with sliders in the sidebar
- **Real-time Preview**: See changes instantly as you adjust axes
- **Instance Editing**: Update instance coordinates in the Glyphs file
- **Drag-and-Drop Reordering**: Reorder instance rows by dragging
- **Font Size Control**: Adjust preview font size (0.5rem to 7rem)
- **Sample Text**: Customizable sample text with title case
- **Instance Removal**: Remove instances from preview (restore by refreshing)

## Requirements

- Python 3.7+ with virtual environment
- Node.js and npm
- Required Python packages:
  - `flask`
  - `flask-cors`
  - `fonttools`
  - `glyphsLib`
  - `fontmake`
- React app dependencies (installed automatically)

## Quick Start

### Option 1: Using the Launch Script (Recommended)

```bash
# With default Glyphs file (sources/Crispy.glyphs)
./scripts/launch-preview.sh

# With a specific Glyphs file
./scripts/launch-preview.sh sources/Crispy.glyphs

# With an absolute path
./scripts/launch-preview.sh /path/to/other-font.glyphs
```

This will:
- Start the backend server on port 5001
- Start the React frontend on port 3000
- Open the app in your browser

Press `Ctrl+C` to stop both servers.

### Option 2: Manual Launch

#### 1. Start Backend Server

```bash
# Activate virtual environment
source venv/bin/activate

# Start server with default Glyphs file
python3 scripts/glyphs-preview-server.py

# Or specify a Glyphs file
python3 scripts/glyphs-preview-server.py --glyphs sources/Crispy.glyphs
python3 scripts/glyphs-preview-server.py --glyphs /path/to/other-font.glyphs
```

The server will run on `http://localhost:5001`

#### 2. Start React Frontend

In a new terminal:

```bash
cd preview-app
npm start
```

The app will open at `http://localhost:3000`

## Usage

1. **Build Font**: Click "Build Font" to generate the variable font from the Glyphs file
2. **Select Instance**: Click on an instance row to select it
3. **Adjust Axes**: Use the sliders in the sidebar to adjust font axes
4. **Edit Sample Text**: Change the sample text in the sidebar
5. **Adjust Font Size**: Use the font size slider below the axes
6. **Update Instance**: Click "Update Instance" to save changes to the Glyphs file
7. **Reset Changes**: Click "Reset to Original" to restore original coordinates
8. **Reorder Rows**: Drag and drop rows to reorder them
9. **Remove Instance**: Click the trash icon (🗑️) next to coordinates to remove from preview

## Configuration

### Server Options

The backend server accepts the following command-line arguments:

```bash
python3 scripts/glyphs-preview-server.py [OPTIONS]

Options:
  --glyphs PATH       Path to Glyphs file (default: sources/Crispy.glyphs)
  --build-dir PATH    Directory for built fonts (default: preview-fonts)
  --port PORT         Port to run server on (default: 5001)
  --host HOST         Host to bind to (default: 127.0.0.1)
```

### Default Settings

- **Glyphs file**: `sources/Crispy.glyphs`
- **Build directory**: `preview-fonts/` (separate from production `fonts/` directory)
- **Backend port**: 5001 (avoids macOS AirPlay on port 5000)
- **Frontend port**: 3000

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/instances` - Get all instances from Glyphs file
- `GET /api/axes` - Get axes from built font
- `POST /api/build` - Build variable font
- `GET /api/font` - Serve variable font file
- `PUT /api/instance/<name>` - Update instance coordinates

## File Structure

```
preview-app/
├── src/
│   ├── App.js              # Main app component
│   ├── api.js              # API client
│   └── components/
│       ├── Header.js       # Header with Build/Refresh buttons
│       ├── Sidebar.js      # Sidebar with axes and controls
│       ├── InstanceRows.js # Container for instance rows
│       ├── InstanceRow.js   # Individual instance row
│       └── ...
└── package.json

scripts/
├── glyphs-preview-server.py  # Backend Flask server
└── launch-preview.sh         # Launch script
```

## Notes

- The preview tool builds fonts directly from the Glyphs file using `fontmake`
- It does NOT use `config.yaml` or `gftools builder` - this is for testing the Glyphs file exclusively
- Instance removal is UI-only - refresh the page to restore removed instances
- Changes to instance coordinates are saved to the Glyphs file when you click "Update Instance"
- The font is automatically rebuilt after updating an instance

## Troubleshooting

### Port Already in Use

If port 5001 is in use:
```bash
python3 scripts/glyphs-preview-server.py --port 5002
```

If port 3000 is in use, React will prompt you to use a different port.

### Font Not Loading

- Check browser console for errors
- Verify the font was built successfully (click "Build Font")
- Check `/tmp/preview-server.log` for backend errors

### Dependencies Missing

Install Python dependencies:
```bash
source venv/bin/activate
pip install flask flask-cors fonttools glyphsLib fontmake
```

Install React dependencies:
```bash
cd preview-app
npm install
```

## Development

The React app uses:
- React 18.2.0
- react-scripts 5.0.1
- axios for API calls

The backend uses:
- Flask for the API server
- fontTools for font manipulation
- glyphsLib for Glyphs file reading
- fontmake for building fonts
