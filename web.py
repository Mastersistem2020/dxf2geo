import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from converter import convert

app = FastAPI(title="DXF2GEO Converter")

INPUT_DIR = Path(os.getenv("INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/output"))

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head>
            <title>DXF2GEO Converter</title>
        </head>
        <body style="font-family: Arial; max-width: 700px; margin: 40px auto;">
            <h1>DXF → GEO Converter</h1>
            <p>DXF-Datei hochladen und als GEO-Datei herunterladen.</p>

            <form action="/convert" enctype="multipart/form-data" method="post">
                <input name="file" type="file" accept=".dxf,.DXF" required>
                <button type="submit">Konvertieren</button>
            </form>
        </body>
    </html>
    """


@app.post("/convert")
async def convert_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="Bitte eine DXF-Datei hochladen.")

    job_id = uuid.uuid4().hex
    safe_name = Path(file.filename).name

    input_path = INPUT_DIR / f"{job_id}_{safe_name}"
    output_path = OUTPUT_DIR / f"{Path(safe_name).stem}_{job_id}.GEO"

    with open(input_path, "wb") as f:
        f.write(await file.read())

    try:
        convert(str(input_path), str(output_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        output_path,
        media_type="application/octet-stream",
        filename=f"{Path(safe_name).stem}.GEO"
    )