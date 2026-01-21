#!/bin/bash
# Test script for gftools builder with --experimental-fontc flag
# Compares build output between fontmake (default) and fontc (experimental)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Paths
GLYPHS_FILE="sources/Crispy.glyphs"
CONFIG_FILE="sources/config.yaml"
FONTC_BINARY="$PROJECT_ROOT/bin/fontc"
FONTMAKE_OUTPUT="$PROJECT_ROOT/test-output/gftools-fontmake"
FONTC_OUTPUT="$PROJECT_ROOT/test-output/gftools-fontc"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== gftools builder: fontmake vs fontc Test ==="
echo ""
echo "This test compares:"
echo "  1. gftools builder (default - uses fontmake)"
echo "  2. gftools builder --experimental-fontc (uses fontc)"
echo ""

# Check prerequisites
if [ ! -f "$GLYPHS_FILE" ]; then
    echo -e "${RED}❌ Glyphs file not found: $GLYPHS_FILE${NC}"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

if [ ! -f "$FONTC_BINARY" ]; then
    echo -e "${RED}❌ fontc binary not found: $FONTC_BINARY${NC}"
    echo "   Please ensure fontc is installed in bin/fontc"
    exit 1
fi

if ! command -v gftools &> /dev/null; then
    echo -e "${RED}❌ gftools not found in PATH${NC}"
    echo "   Please activate venv: source venv/bin/activate"
    exit 1
fi

# Create output directories
mkdir -p "$FONTMAKE_OUTPUT" "$FONTC_OUTPUT"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "=== Test 1: gftools builder (default - fontmake) ==="
echo "Building with: gftools builder $CONFIG_FILE"
echo ""

# Clean fonts directory before test
rm -rf fonts

FONTMAKE_START=$(date +%s)
if gftools builder "$CONFIG_FILE" 2>&1 | tee /tmp/gftools-fontmake.log; then
    FONTMAKE_END=$(date +%s)
    FONTMAKE_TIME=$((FONTMAKE_END - FONTMAKE_START))
    echo -e "${GREEN}✅ gftools builder (fontmake) successful (${FONTMAKE_TIME}s)${NC}"
    # Find the output font (gftools builder outputs to fonts/variable/)
    FONTMAKE_FONT=$(find fonts/variable -name "*.ttf" | head -1)
    if [ -n "$FONTMAKE_FONT" ]; then
        cp "$FONTMAKE_FONT" "$FONTMAKE_OUTPUT/" 2>/dev/null || true
    fi
else
    echo -e "${RED}❌ gftools builder (fontmake) failed${NC}"
    exit 1
fi

echo ""
echo "=== Test 2: gftools builder --experimental-fontc ==="
echo "Building with: gftools builder --experimental-fontc $FONTC_BINARY $CONFIG_FILE"
echo ""

# Clean fonts directory for fontc test
rm -rf fonts

FONTC_START=$(date +%s)
if gftools builder --experimental-fontc "$FONTC_BINARY" "$CONFIG_FILE" 2>&1 | tee /tmp/gftools-fontc.log; then
    FONTC_END=$(date +%s)
    FONTC_TIME=$((FONTC_END - FONTC_START))
    echo -e "${GREEN}✅ gftools builder (fontc) successful (${FONTC_TIME}s)${NC}"
    # Find the output font (gftools builder outputs to fonts/variable/)
    FONTC_FONT=$(find fonts/variable -name "*.ttf" | head -1)
    if [ -n "$FONTC_FONT" ]; then
        cp "$FONTC_FONT" "$FONTC_OUTPUT/" 2>/dev/null || true
    fi
else
    echo -e "${RED}❌ gftools builder (fontc) failed${NC}"
    exit 1
fi

echo ""
echo "=== Comparison ==="
echo ""

# Find output fonts (check both locations)
if [ -z "$FONTMAKE_FONT" ]; then
    FONTMAKE_FONT=$(find "$FONTMAKE_OUTPUT" -name "*.ttf" | head -1)
fi
if [ -z "$FONTC_FONT" ]; then
    FONTC_FONT=$(find "$FONTC_OUTPUT" -name "*.ttf" | head -1)
fi
# Also check fonts/variable/ as fallback
if [ -z "$FONTMAKE_FONT" ]; then
    FONTMAKE_FONT=$(find fonts/variable -name "*.ttf" | head -1)
fi
if [ -z "$FONTC_FONT" ]; then
    FONTC_FONT=$(find fonts/variable -name "*.ttf" | head -1)
fi

if [ -z "$FONTMAKE_FONT" ]; then
    echo -e "${RED}❌ No fontmake output font found${NC}"
    exit 1
fi

if [ -z "$FONTC_FONT" ]; then
    echo -e "${RED}❌ No fontc output font found${NC}"
    exit 1
fi

echo "Build Times:"
echo "  fontmake: ${FONTMAKE_TIME}s"
echo "  fontc: ${FONTC_TIME}s"
if [ "$FONTC_TIME" -lt "$FONTMAKE_TIME" ]; then
    SPEEDUP=$(echo "scale=2; $FONTMAKE_TIME / $FONTC_TIME" | bc)
    echo -e "  ${GREEN}Speedup: ${SPEEDUP}x faster with fontc${NC}"
elif [ "$FONTC_TIME" -gt "$FONTMAKE_TIME" ]; then
    SLOWDOWN=$(echo "scale=2; $FONTC_TIME / $FONTMAKE_TIME" | bc)
    echo -e "  ${YELLOW}Slowdown: ${SLOWDOWN}x slower with fontc${NC}"
else
    echo "  Same build time"
fi

echo ""
echo "File Sizes:"
FONTMAKE_SIZE=$(stat -f%z "$FONTMAKE_FONT" 2>/dev/null || stat -c%s "$FONTMAKE_FONT" 2>/dev/null)
FONTC_SIZE=$(stat -f%z "$FONTC_FONT" 2>/dev/null || stat -c%s "$FONTC_FONT" 2>/dev/null)
echo "  fontmake: $(numfmt --to=iec-i --suffix=B $FONTMAKE_SIZE 2>/dev/null || echo "${FONTMAKE_SIZE} bytes")"
echo "  fontc: $(numfmt --to=iec-i --suffix=B $FONTC_SIZE 2>/dev/null || echo "${FONTC_SIZE} bytes")"
if [ "$FONTMAKE_SIZE" -eq "$FONTC_SIZE" ]; then
    echo -e "  ${GREEN}File sizes match${NC}"
else
    DIFF=$((FONTC_SIZE - FONTMAKE_SIZE))
    if [ "$DIFF" -gt 0 ]; then
        echo -e "  ${YELLOW}fontc output is $(numfmt --to=iec-i --suffix=B $DIFF 2>/dev/null || echo "${DIFF} bytes") larger${NC}"
    else
        echo -e "  ${GREEN}fontc output is $(numfmt --to=iec-i --suffix=B ${DIFF#-} 2>/dev/null || echo "${DIFF#-} bytes") smaller${NC}"
    fi
fi

echo ""
echo "=== Axes Comparison ==="
echo ""

# Extract axes using Python
python3 << EOF
from fontTools.ttLib import TTFont
import sys

fontmake_font = TTFont("$FONTMAKE_FONT")
fontc_font = TTFont("$FONTC_FONT")

fontmake_axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in fontmake_font['fvar'].axes]
fontc_axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in fontc_font['fvar'].axes]

print("fontmake axes:", fontmake_axes)
print("fontc axes:", fontc_axes)

if fontmake_axes == fontc_axes:
    print("✅ Axes match!")
else:
    print("❌ Axes differ")
    sys.exit(1)
EOF

echo ""
echo "=== Output Files ==="
echo "fontmake output: $FONTMAKE_FONT"
echo "fontc output: $FONTC_FONT"
echo ""
echo "=== Test Complete ==="
