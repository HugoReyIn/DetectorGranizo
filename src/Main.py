from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import requests

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO
from models.User import User
from models.Field import Field
from models.Point import Point

# ----- APP -----
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ----- DAOs -----
userDAO = UserDAO()
fieldDAO = FieldDAO()
pointDAO = PointDAO()

# ----- SESIÓN SIMPLE -----
current_user = None

# ==============================
# LOGIN / REGISTER
# ==============================
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

# ==============================
# DASHBOARD
# ==============================
@app.get("/main", response_class=HTMLResponse)
def mainPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    fields = fieldDAO.getAllFieldsByUser(current_user.id)
    return templates.TemplateResponse(
        "main.html",
        {"request": request, "fields": fields, "user": current_user}
    )

# ==============================
# CREAR CAMPO
# ==============================
@app.get("/field/new", response_class=HTMLResponse)
def newFieldPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("createField.html", {"request": request, "user": current_user})

@app.post("/field/new")
def saveField(
    request: Request,
    name: str = Form(...),
    municipality: str = Form(...),
    area: str = Form(...),  # Recibimos como string para evitar 422
    points: str = Form(...),
    user_id: int = Form(...)
):
    # Validar usuario
    user = userDAO.getUser(user_id)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    # Convertir area a float
    try:
        area_float = float(area.replace(",", "."))
    except:
        area_float = 0.0

    # Guardar campo
    new_field = Field(name=name, municipality=municipality, area_m2=area_float)
    new_field.state = "open"
    field_id = fieldDAO.insertField(new_field, user.id)

    # Guardar puntos
    try:
        points_list = json.loads(points)
        for p in points_list:
            point = Point(latitude=p["lat"], longitude=p["lng"])
            pointDAO.insertPoint(point, field_id)
    except Exception as e:
        print("Error guardando puntos:", e)

    return RedirectResponse(url="/main", status_code=303)

# ==============================
# OBTENER MUNICIPIO (NOMINATIM)
# ==============================
@app.get("/get-municipio")
def get_municipio(lat: float, lon: float):
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
    except:
        return JSONResponse({"municipio": "Desconocido"})
