from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from models.User import User
from models.Field import Field
import requests

# ----- APP -----
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ----- DAOs -----
userDAO = UserDAO()
fieldDAO = FieldDAO()

# ----- SESIÓN SIMPLE -----
current_user = None

# ---------- LOGIN ----------
@app.get("/", response_class=HTMLResponse)
def loginPage(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    global current_user
    user = userDAO.getUserByEmail(email)
    if user and user.password == password:
        current_user = user
        return RedirectResponse(url="/main", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Correo o contraseña incorrectos"}
    )

# ---------- REGISTER ----------
@app.get("/register", response_class=HTMLResponse)
def registerPage(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if userDAO.getUserByEmail(email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "El correo ya está registrado"}
        )
    new_user = User(email=email, password=password, name=name)
    userDAO.insertUser(new_user)
    return RedirectResponse(url="/", status_code=303)

# ---------- MAIN ----------
@app.get("/main", response_class=HTMLResponse)
def mainPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    fields = fieldDAO.getAllFieldsByUser(current_user.id)
    return templates.TemplateResponse(
        "main.html",
        {"request": request, "fields": fields, "user": current_user}
    )

# ---------- CREATE FIELD ----------
@app.get("/field/new", response_class=HTMLResponse)
def newField(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "createField.html",
        {"request": request}
    )

# ---------- GET MUNICIPIO (NOMINATIM) ----------
@app.get("/get-municipio")
def get_municipio(lat: float, lon: float):
    """
    Devuelve el municipio correspondiente a unas coordenadas.
    """
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        headers = {"User-Agent": "MiApp/1.0 (tuemail@ejemplo.com)"}
        params = {"lat": lat, "lon": lon, "format": "json"}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        address = data.get("address", {})
        municipio = (
            address.get("municipality")
            or address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("county")
            or "Desconocido"
        )

        return JSONResponse({"municipio": municipio})

    except Exception as e:
        return JSONResponse({"municipio": "Desconocido"})
