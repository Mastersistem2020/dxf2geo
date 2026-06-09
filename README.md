# DXF → TRUMPF GEO Converter (Docker)

Konvertiert AutoCAD DXF-Dateien in das TRUMPF GEO v1.03 Format (für TruLaser-Maschinen).

## Unterstützte DXF-Elemente
- LINE
- ARC
- CIRCLE (als zwei 180°-Bögen)
- LWPOLYLINE / POLYLINE
- SPLINE (als approximierte Liniensegmente)
- ELLIPSE (als approximierte Liniensegmente)

## Schnellstart

### Build
```bash
docker build -t dxf2geo .
```

### Einmalige Konvertierung
DXF-Dateien in `./input/` ablegen, GEO-Dateien erscheinen in `./output/`:
```bash
mkdir -p input output
cp meine_datei.dxf input/
docker run --rm -v ./input:/input -v ./output:/output dxf2geo
```

### Mit Docker Compose
```bash
docker compose up
```

### Watch-Modus (dauerhaft laufend)
```bash
docker run -d \
  -e WATCH_MODE=true \
  -v /pfad/zu/dxf:/input \
  -v /pfad/zu/geo:/output \
  --restart unless-stopped \
  --name dxf2geo \
  dxf2geo
```

### Direkt (ohne Docker)
```bash
pip install ezdxf
python3 converter.py datei.dxf
python3 converter.py *.dxf          # Mehrere Dateien
python3 converter.py a.dxf -o b.GEO  # Ausgabepfad angeben
```

## GEO-Format
Das erzeugte GEO-Format entspricht TRUMPF GEO v1.03 mit:
- `#~1`  — Datei-Header (Version, Datum, Bounding Box, Fläche)
- `#~11` — Material/Technologie (leer, in TruTops befüllen)
- `#~3`  — Teilinfo (LASER-Typ, Transformationsmatrix)
- `#~30` — Metadaten (Quelldatei, Codepage)
- `#~31` — Punktliste
- `#~33` + `#~331` — Konturen (LIN / ARC)

## Hinweise
- Technologieparameter (Schneidgeschwindigkeit, Leistung, Gas) müssen in TruTops
  manuell zugewiesen werden — sie sind nicht im DXF enthalten.
- SPLINE-Kurven werden mit 0.1mm Toleranz in Liniensegmente approximiert.
- Die Datei wird mit Windows-1252 Codepage und CRLF Zeilenenden geschrieben
  (wie vom Original erwartet).
