# dxf2geo — DXF to TRUMPF GEO Converter

A self-hosted Docker tool that converts AutoCAD DXF files into TRUMPF GEO v1.03 format for TRUMPF TruLaser machines.

The tool provides a simple web interface: upload a `.dxf` file in the browser and download the converted `.GEO` file directly.

Tested with TRUMPF TruLaser 2530 and TRUMPF GEO Viewer.

## Features

* Browser-based DXF upload
* Direct GEO file download
* Docker image available via Docker Hub
* No Windows installation required
* No TruTops installation required for conversion
* Supports common DXF geometry elements
* Optional batch/watch mode via input/output folders

## Docker Hub Image

```bash
docker pull djnord/dxf2geo:latest
```

## Quick Start with Docker

```bash
docker run -d \
  --name dxf2geo \
  -p 8090:8000 \
  -v ./input:/input \
  -v ./output:/output \
  --restart unless-stopped \
  djnord/dxf2geo:latest
```

Open the web interface:

```text
http://localhost:8090
```

Upload a DXF file and download the generated GEO file.

## Docker Compose

```yaml
services:
  dxf2geo:
    image: djnord/dxf2geo:latest
    container_name: dxf2geo
    ports:
      - "8090:8000"
    volumes:
      - ./input:/input
      - ./output:/output
    restart: unless-stopped
```

Start:

```bash
docker compose up -d
```

Open:

```text
http://localhost:8090
```

## Portainer / OMV Stack Example

For Portainer or OpenMediaVault, use absolute paths:

```yaml
services:
  dxf2geo:
    image: djnord/dxf2geo:latest
    container_name: dxf2geo
    ports:
      - "8090:8000"
    volumes:
      - /srv/dev-disk-by-uuid-DEINE-UUID/appdata/dxf2geo/input:/input
      - /srv/dev-disk-by-uuid-DEINE-UUID/appdata/dxf2geo/output:/output
    restart: unless-stopped
```

Then open:

```text
http://SERVER-IP:8090
```

## Batch / Watch Mode

The container also supports folder-based conversion.

### One-shot conversion

Place DXF files in the input folder and run:

```bash
docker run --rm \
  -v ./input:/input \
  -v ./output:/output \
  djnord/dxf2geo:latest \
  /app/entrypoint.sh
```

### Watch mode

```bash
docker run -d \
  --name dxf2geo-watch \
  -e WATCH_MODE=true \
  -v ./input:/input \
  -v ./output:/output \
  --restart unless-stopped \
  djnord/dxf2geo:latest \
  /app/entrypoint.sh
```

## Supported DXF Entities

| Entity     | Status                                |
| ---------- | ------------------------------------- |
| LINE       | Supported                             |
| ARC        | Supported                             |
| CIRCLE     | Supported as native GEO `CIR` element |
| LWPOLYLINE | Supported, including bulge arcs       |
| POLYLINE   | Supported                             |
| SPLINE     | Approximated as line segments         |
| ELLIPSE    | Approximated as line segments         |

## Environment Variables

| Variable   | Default   | Description                         |
| ---------- | --------- | ----------------------------------- |
| INPUT_DIR  | `/input`  | Directory for DXF input files       |
| OUTPUT_DIR | `/output` | Directory for generated GEO files   |
| WATCH_MODE | `false`   | Set to `true` for folder watch mode |

## Notes

* Technology parameters such as cutting speed, laser power and gas type are not stored in DXF files and must be assigned manually in TRUMPF software after import.
* Output files use Windows-1252 encoding and CRLF line endings.
* Coordinates are normalized to origin, so minimum X/Y starts at `0`.
* The converter was tested with real DXF/GEO files, but every machine workflow should be verified before production use.

## License

MIT
