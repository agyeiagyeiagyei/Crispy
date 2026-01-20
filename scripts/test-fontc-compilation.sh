#!/bin/bash
# Test script to compare fontc vs fontmake compilation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GLYPHS_FILE="$PROJECT_ROOT/sources/Crispy.glyphs"
FONTC_OUTPUT="$PROJECT_ROOT/test-output/fontc"
FONTMAKE_OUTPUT="$PROJECT_ROOT/test-output/fontmake"

echo "=== Fontc vs Fontmake Compilation Test ==="
echo ""

# Check if Glyphs file exists
if [ ! -f "$GLYPHS_FILE" ]; then
    echo "Error: Glyphs file not found: $GLYPHS_FILE"
    exit 1
fi

# Create output directories
mkdir -p "$FONTC_OUTPUT" "$FONTMAKE_OUTPUT"

# Test fontc compilation
echo "1. Testing fontc compilation..."
FONTC_START=$(date +%s)
mkdir -p "$FONTC_OUTPUT"
FONTC_OUTPUT_FILE="$FONTC_OUTPUT/Crispy-VF.ttf"
if "$PROJECT_ROOT/bin/fontc" --output-file "$FONTC_OUTPUT_FILE" "$GLYPHS_FILE" 2>&1; then
    FONTC_END=$(date +%s)
    FONTC_TIME=$((FONTC_END - FONTC_START))
    echo "✅ fontc compilation successful (${FONTC_TIME}s)"
else
    echo "❌ fontc compilation failed"
    exit 1
fi

# Test fontmake compilation
echo ""
echo "2. Testing fontmake compilation..."
FONTMAKE_START=$(date +%s)
if fontmake -o variable -g "$GLYPHS_FILE" --output-dir "$FONTMAKE_OUTPUT" 2>&1; then
    FONTMAKE_END=$(date +%s)
    FONTMAKE_TIME=$((FONTMAKE_END - FONTMAKE_START))
    echo "✅ fontmake compilation successful (${FONTMAKE_TIME}s)"
else
    echo "❌ fontmake compilation failed"
    exit 1
fi

# Find output fonts
FONTC_FONT="$FONTC_OUTPUT_FILE"
if [ ! -f "$FONTC_FONT" ]; then
    FONTC_FONT=$(find "$FONTC_OUTPUT" -name "*.ttf" | head -1)
fi
FONTMAKE_FONT=$(find "$FONTMAKE_OUTPUT" -name "*.ttf" | head -1)

if [ -z "$FONTC_FONT" ]; then
    echo "❌ No fontc output font found"
    exit 1
fi

if [ -z "$FONTMAKE_FONT" ]; then
    echo "❌ No fontmake output font found"
    exit 1
fi

echo ""
echo "=== Results ==="
echo "fontc output:   $FONTC_FONT"
echo "fontmake output: $FONTMAKE_FONT"
echo ""
echo "Build times:"
echo "  fontc:    ${FONTC_TIME}s"
echo "  fontmake: ${FONTMAKE_TIME}s"
if [ "$FONTC_TIME" -lt "$FONTMAKE_TIME" ]; then
    SPEEDUP=$(echo "scale=2; $FONTMAKE_TIME / $FONTC_TIME" | bc)
    echo "  Speedup: ${SPEEDUP}x faster with fontc"
else
    SLOWDOWN=$(echo "scale=2; $FONTC_TIME / $FONTMAKE_TIME" | bc)
    echo "  Slowdown: ${SLOWDOWN}x slower with fontc"
fi

echo ""
echo "File sizes:"
FONTC_SIZE=$(stat -f%z "$FONTC_FONT" 2>/dev/null || stat -c%s "$FONTC_FONT" 2>/dev/null)
FONTMAKE_SIZE=$(stat -f%z "$FONTMAKE_FONT" 2>/dev/null || stat -c%s "$FONTMAKE_FONT" 2>/dev/null)
echo "  fontc:    $(numfmt --to=iec-i --suffix=B $FONTC_SIZE 2>/dev/null || echo "${FONTC_SIZE} bytes")"
echo "  fontmake: $(numfmt --to=iec-i --suffix=B $FONTMAKE_SIZE 2>/dev/null || echo "${FONTMAKE_SIZE} bytes")"

echo ""
echo "=== Next Steps ==="
echo "1. Compare font axes:"
echo "   python3 -c \"from fontTools.ttLib import TTFont; f=TTFont('$FONTC_FONT'); print([a.axisTag for a in f['fvar'].axes])\""
echo ""
echo "2. Test in browser/preview tool"
echo ""
echo "3. Visual comparison of rendered fonts"
