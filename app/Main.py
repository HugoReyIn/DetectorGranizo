from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.models.Field import Campo
from app.models.Wheather import Clima

app = FastAPI()

# Ruta segura a templates usando Path
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Archivos estáticos (CSS, JS, imágenes)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Datos de ejemplo
campos = [Campo("Campo A", "Madrid"), Campo("Campo B", "Valencia")]

# Endpoint principal
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Endpoint para ver un campo
@app.get("/campos")
def ver_campos(request: Request):
    campo = campos[0]  # por ahora mostramos solo el primero
    return templates.TemplateResponse("field.html", {"request": request, "campo": campo})

# Endpoint para activar/desactivar techo
@app.post("/campos/{nombre}/techo")
def toggle_techo(nombre: str, accion: str = Form(...)):
    campo = next((c for c in campos if c.nombre == nombre), None)
    if campo:
        if accion == "activar":
            campo.activar_techo()
        else:
            campo.desactivar_techo()
    return {"status": "ok", "techo_activo": campo.techo_activo}
