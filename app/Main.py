from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.models.Field import Campo
from app.models.Wheather import Clima

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Datos de ejemplo
campos = [Campo("Campo A", "Madrid"), Campo("Campo B", "Valencia")]

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/campos")
def ver_campos(request: Request):
    return templates.TemplateResponse("campo.html", {"request": request, "campo": campos[0]})

@app.post("/campos/{nombre}/techo")
def toggle_techo(nombre: str, accion: str = Form(...)):
    campo = next((c for c in campos if c.nombre == nombre), None)
    if campo:
        if accion == "activar":
            campo.activar_techo()
        else:
            campo.desactivar_techo()
    return {"status": "ok", "techo_activo": campo.techo_activo}
