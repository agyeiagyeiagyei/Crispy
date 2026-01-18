# Glyphs Preview App

React frontend for the Glyphs preview tool.

## Setup

```bash
cd preview-app
npm install
```

## Development

```bash
npm start
```

The app will run on http://localhost:3000 and proxy API requests to the backend server at http://localhost:5000.

Make sure the backend server is running:
```bash
python3 scripts/glyphs-preview-server.py
```

## Features

- Preview all instances from Glyphs file
- Adjust axis values with sliders
- Update instance coordinates in Glyphs file
- Real-time preview updates
- Per-row editable sample text
