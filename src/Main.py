from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import requests
from datetime import datetime

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO
from models.User import User
from models.Field import Field
from models.Point import Point
from config import AEMET_API_KEY

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
    except Exception as e:
        return JSONResponse({"municipio": "Desconocido", "error": str(e)})

# --------------------
# AEMET OBSERVACIÓN ACTUAL
# --------------------
def get_aemet_observation(lat: float, lon: float):
    try:
        # 1️⃣ Obtener todas las estaciones
        stations_url = f"https://opendata.aemet.es/opendata/api/valores/climatologicos/inventarioestaciones/todasestaciones?api_key={AEMET_API_KEY}"
        r = requests.get(stations_url, timeout=10)
        data = r.json()

        if "datos" not in data:
            return None

        stations_data = requests.get(data["datos"], timeout=10).json()

        # 2️⃣ Buscar estación más cercana
        from math import radians, cos, sin, sqrt, atan2

        def distance(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c

        nearest = None
        min_dist = 999999

        for s in stations_data:
            if not s.get("latitud") or not s.get("longitud"):
                continue

            # Formato lat/lon AEMET viene tipo "432147N"
            def parse_coord(coord):
                deg = float(coord[:2])
                min_ = float(coord[2:4])
                sec = float(coord[4:6])
                hemi = coord[-1]
                value = deg + min_/60 + sec/3600
                if hemi in ["S", "W"]:
                    value *= -1
                return value

            s_lat = parse_coord(s["latitud"])
            s_lon = parse_coord(s["longitud"])

            d = distance(lat, lon, s_lat, s_lon)

            if d < min_dist:
                min_dist = d
                nearest = s

        if not nearest:
            return None

        # 3️⃣ Obtener observación actual de esa estación
        station_id = nearest["indicativo"]
        obs_url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/{station_id}?api_key={AEMET_API_KEY}"
        r2 = requests.get(obs_url, timeout=10)
        obs_data = r2.json()

        if "datos" not in obs_data:
            return None

        observations = requests.get(obs_data["datos"], timeout=10).json()

        if not observations:
            return None

        latest = observations[-1]

        return {
            "temperature": latest.get("ta"),
            "humidity": latest.get("hr"),
            "wind_speed": latest.get("vv"),
            "precipitation": latest.get("prec")
        }

    except Exception as e:
        print("Error AEMET:", e)
        return None

# --------------------
# WEATHER (ICON-EU + AEMET)
# --------------------
@app.get("/get-weather")
def get_weather(lat: float, lon: float):
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            "&current=temperature_2m,weathercode,windspeed_10m,winddirection_10m"
            "&hourly=relativehumidity_2m,"
            "dewpoint_2m,"
            "precipitation,"
            "snowfall,"
            "precipitation_probability,"
            "soil_moisture_0_1cm"
            "&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min,weathercode"
            "&forecast_days=5"
            "&models=icon_eu"
            "&timezone=auto"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        weathercode = current.get("weathercode", 0)

        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        times = hourly.get("time", [])

        current_index = 0
        for i, t in enumerate(times):
            dt = datetime.fromisoformat(t)
            if dt == now:
                current_index = i
                break

        precipitation = hourly.get("precipitation", [0])[current_index] or 0
        snowfall = hourly.get("snowfall", [0])[current_index] or 0
        precipitation_probability = hourly.get("precipitation_probability", [0])[current_index] or 0
        soil_moisture = hourly.get("soil_moisture_0_1cm", [None])[current_index]

        aemet_data = get_aemet_observation(lat, lon)

        if aemet_data:
            if aemet_data["temperature"] is not None:
                current["temperature_2m"] = float(aemet_data["temperature"])

            if aemet_data["humidity"] is not None:
                hourly["relativehumidity_2m"][current_index] = int(aemet_data["humidity"])

            if aemet_data["wind_speed"] is not None:
                current["windspeed_10m"] = float(aemet_data["wind_speed"])

            if aemet_data["precipitation"] is not None:
                precipitation = float(aemet_data["precipitation"])

        hail_probability = 0
        if weathercode in [96, 99]:
            hail_probability = precipitation_probability

        weather = {
            "temp_actual": current.get("temperature_2m"),
            "humidity": hourly.get("relativehumidity_2m", [None])[current_index],
            "dew_point": hourly.get("dewpoint_2m", [None])[current_index],
            "wind_speed": current.get("windspeed_10m"),
            "wind_deg": current.get("winddirection_10m"),
            "rain": round(float(precipitation), 1),
            "snow": round(float(snowfall), 1),
            "hail": int(hail_probability),
            "soil_moisture": round(soil_moisture, 3) if soil_moisture is not None else None,
            "weathercode": weathercode,

            "temp_max": daily.get("temperature_2m_max", [None])[0],
            "temp_min": daily.get("temperature_2m_min", [None])[0],
            "sunrise": daily.get("sunrise", [None])[0],
            "sunset": daily.get("sunset", [None])[0],

            "daily": {
                "time": daily.get("time"),
                "weathercode": daily.get("weathercode"),
                "temperature_2m_max": daily.get("temperature_2m_max"),
                "temperature_2m_min": daily.get("temperature_2m_min"),
                "sunrise": daily.get("sunrise"),
                "sunset": daily.get("sunset")
            }
        }

        return JSONResponse(weather)

    except Exception as e:
        print("Error WEATHER:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/weather/{field_id}", response_class=HTMLResponse)
def hourlyWeatherPage(request: Request, field_id: int):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    field = fieldDAO.getField(field_id)
    if not field or field.user_id != current_user.id:
        return RedirectResponse(url="/main", status_code=303)

    return templates.TemplateResponse(
        "weather.html",
        {
            "request": request,
            "field": field
        }
    )
