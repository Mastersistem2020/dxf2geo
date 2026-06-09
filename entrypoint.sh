#!/bin/bash
# Watch /input for DXF files, convert to /output as GEO

INPUT_DIR="${INPUT_DIR:-/input}"
OUTPUT_DIR="${OUTPUT_DIR:-/output}"
WATCH_MODE="${WATCH_MODE:-false}"

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"

convert_file() {
    local dxf_file="$1"
    local basename=$(basename "$dxf_file" .dxf)
    local out_file="$OUTPUT_DIR/${basename}.GEO"
    python3 /app/converter.py "$dxf_file" -o "$out_file"
}

if [ "$WATCH_MODE" = "true" ]; then
    echo "Watch mode: monitoring $INPUT_DIR for DXF files..."
    # Convert existing files first
    for f in "$INPUT_DIR"/*.dxf "$INPUT_DIR"/*.DXF; do
        [ -f "$f" ] && convert_file "$f"
    done
    # Watch for new files
    inotifywait -m -e close_write -e moved_to --format '%w%f' "$INPUT_DIR" 2>/dev/null | \
    while read filepath; do
        case "${filepath,,}" in
            *.dxf) convert_file "$filepath" ;;
        esac
    done
else
    # One-shot: convert all DXF in input dir
    shopt -s nullglob
    files=("$INPUT_DIR"/*.dxf "$INPUT_DIR"/*.DXF)
    if [ ${#files[@]} -eq 0 ]; then
        echo "No DXF files found in $INPUT_DIR"
        exit 0
    fi
    for f in "${files[@]}"; do
        convert_file "$f"
    done
fi
