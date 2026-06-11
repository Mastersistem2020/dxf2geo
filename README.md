# dxf2geo — DXF to TRUMPF GEO Converter

Converts AutoCAD DXF files to **TRUMPF GEO v1.03** format for use with TRUMPF TruLaser machines (tested on TruLaser 2530).

The original TRUMPF TruTops software that handled this conversion is no longer available. This tool replaces it — runs as a self-hosted Docker container, no Windows required, no license fees.

## How it works

DXF files go in → GEO files come out.

```
./input/part.dxf  →  ./output/part.GEO
```

## Quick start

### Using Docker Hub (recommended)

```bash
mkdir -p input output
cp your_part.dxf input/

docker run --rm \
  -v ./input:/input \
  -v ./output:/output \
  djnord/dxf2geo
```

### Using Docker Compose

```yaml
services:
  dxf2geo:
    image: djnord/dxf2geo
    volumes:
      - ./input:/input
      - ./output:/output
```

```bash
docker compose up
```

### Watch mode — monitor folder for new files

```bash
docker run -d \
  -e WATCH_MODE=true \
  -v /path/to/dxf:/input \
  -v /path/to/geo:/output \
  --restart unless-stopped \
  --name dxf2geo \
  djnord/dxf2geo
```

### Without Docker

```bash
pip install ezdxf
python3 converter.py part.dxf
python3 converter.py *.dxf
python3 converter.py part.dxf -o output/part.GEO
```

## Supported DXF entities

| Entity | Notes |
|---|---|
| `LINE` | Full support |
| `ARC` | Full support |
| `CIRCLE` | Native `CIR` element in GEO |
| `LWPOLYLINE` | Full support including bulge arcs |
| `POLYLINE` | Full support |
| `SPLINE` | Approximated as line segments (0.1mm tolerance) |
| `ELLIPSE` | Approximated as line segments |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `INPUT_DIR` | `/input` | Directory to read DXF files from |
| `OUTPUT_DIR` | `/output` | Directory to write GEO files to |
| `WATCH_MODE` | `false` | Set to `true` to keep running and watch for new files |

## Notes

- Technology parameters (cutting speed, laser power, gas type) are not stored in DXF files. They must be assigned manually in TruTops after import — same as with the original software.
- Output files use Windows-1252 encoding and CRLF line endings as required by the TRUMPF format.
- Coordinates are normalized to origin (min x/y = 0) to match TruTops behavior.

## GEO format internals

The TRUMPF GEO v1.03 format was fully reverse-engineered from real machine files. Key findings:

- `ARC` elements use the format `ARC(center, endpoint1, endpoint2, direction)` — the first point is the **arc center**, not a point on the curve.
- `CIR` elements use `CIR(center_point_index, radius)` for full circles/holes.
- Contour headers use a fixed attribute code `24` and a hole-count field linking outer contours to their inner cutouts.
- Files must use Windows-1252 codepage with CRLF line endings — Python's `newline='\r\n'` mode causes double line endings and silent parse failures in the viewer.

## Tested on

- TRUMPF TruLaser 2530
- TRUMPF GEO Viewer (geoViewer)

## License

MIT
