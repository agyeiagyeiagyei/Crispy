# Glyphs Preview Server

Backend server for the Glyphs file preview tool.

## Overview

The preview server provides a REST API to:
- Read instances and their coordinates from `config.yaml`
- Build variable fonts using `gftools builder`
- Extract axes from built variable fonts (excluding SPAC and -e axes)
- Update instance coordinates in `config.yaml`
- Serve variable font files for the React frontend

## API Endpoints

### `GET /api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "glyphs_path": "/path/to/Crispy.glyphs",
  "config_path": "/path/to/config.yaml",
  "font_built": false
}
```

### `GET /api/instances`
Get all instances from `config.yaml`.

**Response:**
```json
{
  "instances": [
    {
      "name": "Regular",
      "coordinates": {
        "opsz": 12,
        "wdth": 100,
        "wght": 400
      }
    },
    ...
  ]
}
```

### `GET /api/axes`
Get axes from the built variable font (excludes SPAC and axes ending in -e).

**Response:**
```json
{
  "axes": [
    {
      "tag": "wght",
      "name": "Weight",
      "min": 200.0,
      "max": 900.0,
      "default": 400.0
    },
    ...
  ]
}
```

**Note:** Returns 404 if font hasn't been built yet.

### `POST /api/build`
Build the variable font from `config.yaml` using `gftools builder`.

**Response:**
```json
{
  "success": true,
  "font_path": "/path/to/font.ttf",
  "axes": [...]
}
```

### `GET /api/font`
Serve the variable font file.

**Response:** Binary TTF file with `Content-Type: font/ttf`

### `PUT /api/instance/<instance_name>`
Update instance coordinates in `config.yaml`.

**Request Body:**
```json
{
  "coordinates": {
    "wght": 500,
    "wdth": 100,
    "opsz": 12
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Updated instance 'Regular' in config.yaml"
}
```

## Usage

```bash
# Activate virtual environment
. venv/bin/activate

# Run server
python3 scripts/glyphs-preview-server.py

# With custom options
python3 scripts/glyphs-preview-server.py \
  --glyphs sources/Crispy.glyphs \
  --config sources/config.yaml \
  --build-dir preview-app/preview-fonts \
  --port 5000 \
  --host 127.0.0.1
```

## Dependencies

- Flask
- flask-cors
- fontTools
- glyphsLib
- PyYAML (or ruamel.yaml for better YAML formatting preservation)
- gftools (for building fonts)

## Notes

- The server reads instances from `config.yaml` (not directly from the Glyphs file) because that's where the actual axis coordinates are stored.
- Building uses `gftools builder` (not `fontmake`) to match the production build process.
- Instance updates modify `config.yaml` directly. The Glyphs file is not modified (this may be added later if needed).
- Axes are filtered to exclude `SPAC` and any axes ending in `-e` as per requirements.
