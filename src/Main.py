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

from config import AEMET_API_KEY, AEMET_BASE_URL

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

userDAO = UserDAO()
fieldDAO = FieldDAO()
pointDAO = PointDAO()

current_user = None

# --------------------
# LOGIN / REGISTER
# --------------------
@app.get("/", response_class=HTMLResponse)
def loginPage(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    global current_user
    user = userDAO.getUserByEmail(email)
    if user and user.password == password:
        current_user = user
        return RedirectResponse(url="/main", status_code=303)
    return RedirectResponse(url="/", status_code=303)

@app.get("/register", response_class=HTMLResponse)
def registerPage(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    existing_user = userDAO.getUserByEmail(email)
    if existing_user:
        return RedirectResponse(url="/register", status_code=303)
    new_user = User(name=name, email=email, password=password)
    userDAO.insertUser(new_user)
    return RedirectResponse(url="/", status_code=303)

# --------------------
# DASHBOARD
# --------------------
@app.get("/main", response_class=HTMLResponse)
def mainPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    fields = fieldDAO.getAllFieldsByUser(current_user.id)
    return templates.TemplateResponse(
        "main.html",
        {"request": request, "fields": fields}
    )

# --------------------
# FIELD CRUD
# --------------------
@app.get("/field/new", response_class=HTMLResponse)
def newFieldPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "field.html",
        {"request": request, "field": None, "points_json": "[]"}
    )

@app.post("/field/new")
def saveField(
    name: str = Form(...),
    municipality: str = Form(...),
    area: str = Form(...),
    points: str = Form(...)
):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    area_float = float(area.replace(",", "."))
    new_field = Field(name=name, municipality=municipality, area_m2=area_float)
    new_field.state = "open"
    field_id = fieldDAO.insertField(new_field, current_user.id)

    points_list = json.loads(points)
    for p in points_list:
        point = Point(latitude=p["lat"], longitude=p["lng"])
        pointDAO.insertPoint(point, field_id)

    return RedirectResponse(url="/main", status_code=303)

@app.get("/field/edit/{field_id}", response_class=HTMLResponse)
def editFieldPage(request: Request, field_id: int):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    field = fieldDAO.getField(field_id)
    if not field or field.user_id != current_user.id:
        return RedirectResponse(url="/main", status_code=303)

    points = pointDAO.getPointsByField(field.id)
    points_json = json.dumps([{"lat": p.latitude, "lng": p.longitude} for p in points])

    return templates.TemplateResponse(
        "field.html",
        {
            "request": request,
            "field": field,
            "points_json": points_json
        }
    )

@app.post("/field/edit/{field_id}")
def updateField(
    field_id: int,
    name: str = Form(...),
    municipality: str = Form(...),
    area: str = Form(...),
    points: str = Form(...)
):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    field = fieldDAO.getField(field_id)
    if not field or field.user_id != current_user.id:
        return RedirectResponse(url="/main", status_code=303)

    field.name = name
    field.municipality = municipality
    field.area_m2 = float(area.replace(",", "."))
    fieldDAO.updateField(field)

    pointDAO.deletePointsByField(field.id)
    points_list = json.loads(points)
    for p in points_list:
        point = Point(latitude=p["lat"], longitude=p["lng"])
        pointDAO.insertPoint(point, field.id)

    return RedirectResponse(url="/main", status_code=303)

@app.post("/field/delete/{field_id}")
def deleteField(field_id: int):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    field = fieldDAO.getField(field_id)
    if not field or field.user_id != current_user.id:
        return RedirectResponse(url="/main", status_code=303)

    fieldDAO.eliminateField(field_id)
    return RedirectResponse(url="/main", status_code=303)

# --------------------
# UPDATE FIELD STATUS
# --------------------
@app.post("/field/update-status/{field_id}")
async def update_field_status(field_id: int, request: Request):
    if not current_user:
        return JSONResponse({"error": "No autorizado"}, status_code=403)

    data = await request.json()
    new_state = data.get("state")
    if new_state not in ["open", "closed"]:
        return JSONResponse({"error": "Estado inválido"}, status_code=400)

    field = fieldDAO.getField(field_id)
    if not field or field.user_id != current_user.id:
        return JSONResponse({"error": "Campo no encontrado o no autorizado"}, status_code=404)

    field.state = new_state
    fieldDAO.updateField(field)

    return JSONResponse({"success": True, "new_state": new_state})

# --------------------
# MUNICIPIO
# --------------------
@app.get("/get-municipio")
def get_municipio(lat: float, lon: float):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        headers = {"User-Agent": "MiApp/1.0"}
        params = {"lat": lat, "lon": lon, "format": "json"}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()

        address = data.get("address", {})
        municipio = (
            address.get("municipality")
            or address.get("city")
            or address.get("town")
            or address.get("village")
            or "Desconocido"
        )

        return JSONResponse({"municipio": municipio})
    except:
        return JSONResponse({"municipio": "Desconocido"})

# --------------------
# WEATHER / AEMET
# --------------------
@app.get("/get-weather")
def get_weather():
    try:
        # Solicitar datos del API
        url = f"{AEMET_BASE_URL}/observacion/convencional/todas?api_key={AEMET_API_KEY}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        # Extraer link de los datos reales
        datos_url = data.get("datos")
        if not datos_url:
            return JSONResponse({"weather": "No disponible"})

        r2 = requests.get(datos_url, timeout=10)
        r2.raise_for_status()
        datos = r2.json()

        # Ejemplo: coger la primera estación
        if len(datos) > 0:
            obs = datos[0]
            temperatura = obs.get("ta")
            viento = obs.get("vv")
            weather_text = f"{temperatura}°C, Viento {viento} km/h"
        else:
            weather_text = "No disponible"

        return JSONResponse({"weather": weather_text})
    except Exception as e:
        return JSONResponse({"weather": "Error"})
