from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Smart Irrigation API")

# Habilitar CORS para pruebas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    # Devuelve tu API JSON
    return {"status": "API funcionando 🚀"}

# Ruta para servir tu index.html
@app.get("/index")
def get_index():
    return FileResponse(os.path.join("static", "index.html"))
