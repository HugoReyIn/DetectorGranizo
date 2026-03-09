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
from ia.HailPredictor import predict_hail

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

    # Añadir centroide lat/lon a cada campo para las alertas
    for field in fields:
        points = pointDAO.getPointsByField(field.id)
        if points:
            field.lat = sum(p.latitude for p in points) / len(points)
            field.lon = sum(p.longitude for p in points) / len(points)
        else:
            field.lat = None
            field.lon = None

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
# WEATHER (ICON-EU)
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

@app.get("/weather", response_class=HTMLResponse)
def weatherPage(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "weather.html",
        {"request": request}
    )

@app.get("/get-hourly-weather")
def get_hourly_weather(lat: float, lon: float):
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            "&hourly=temperature_2m,"
            "precipitation,"
            "precipitation_probability,"
            "relativehumidity_2m,"
            "windspeed_10m,"
            "winddirection_10m,"
            "weathercode"
            "&forecast_days=5"
            "&timezone=auto"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})

        result = []

        for i in range(len(hourly["time"])):
            code = hourly["weathercode"][i]

            hail = 0
            if code == 77:
                hail = 50
            elif code == 96:
                hail = 70
            elif code == 99:
                hail = 100

            result.append({
                "time": hourly["time"][i],
                "temp": hourly["temperature_2m"][i],
                "rain": hourly["precipitation"][i],
                "prob_rain": hourly["precipitation_probability"][i],
                "humidity": hourly["relativehumidity_2m"][i],
                "wind_speed": hourly["windspeed_10m"][i],
                "wind_dir": hourly["winddirection_10m"][i],
                "hail": hail
            })

        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    

# --------------------
# AEMET ALERTAS
# --------------------

AEMET_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbHZhcm9ndWlqYXJyb21hcnRpbmV6QGdtYWlsLmNvbSIsImp0aSI6ImE5NGNmZTFkLWQwMWYtNGEwOS04ZmEwLTA4OTA2OGRkYTNhZSIsImlzcyI6IkFFTUVUIiwiaWF0IjoxNzQ1OTQwMjYxLCJ1c2VySWQiOiJhOTRjZmUxZC1kMDFmLTRhMDktOGZhMC0wODkwNjhkZGEzYWUiLCJyb2xlIjoiIn0.eVr2czlOHVEpBn3IFG4c8W0SoRxqwCzHCOKSbBFU0KA"

# Mapa CAP event → tipo interno
CAP_EVENT_MAP = {
    # Calor / temperaturas altas
    "calor": "calor", "heat": "calor",
    "temperatura máxima": "calor", "temperatura minima": "calor",
    "bochorno": "calor",
    # Lluvia / tormenta
    "lluvia": "lluvia", "rain": "lluvia",
    "precipitaciones": "lluvia",
    "tormenta": "lluvia", "storm": "lluvia",
    "thunderstorm": "lluvia",
    # Nieve
    "nieve": "nieve", "snow": "nieve",
    "nevada": "nieve",
    # Granizo
    "granizo": "granizo", "hail": "granizo",
    "piedra": "granizo",
}

# CAP severity → nivel interno
CAP_SEVERITY_MAP = {
    "minor":    "amarillo",
    "moderate": "naranja",
    "severe":   "rojo",
    "extreme":  "rojo",
    # AEMET también usa estos en español
    "amarillo": "amarillo",
    "naranja":  "naranja",
    "rojo":     "rojo",
}

LEVEL_ORDER = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}

_aemet_cache: dict = {}
AEMET_TTL = 3600


def _default_result():
    return {
        "calor":   {"nivel": "verde", "valor": None},
        "lluvia":  {"nivel": "verde", "valor": None},
        "nieve":   {"nivel": "verde", "valor": None},
        "granizo": {"nivel": "verde", "valor": None},
        "ticker":  ["No hay alertas activas"]
    }


@app.get("/get-aemet-alerts")
def get_aemet_alerts(lat: float, lon: float):
    """
    Consulta AEMET OpenData (avisos CAP) y devuelve niveles de alerta
    para calor, lluvia, nieve y granizo según las coordenadas dadas.
    
    Los avisos CAP de AEMET están en formato XML con campos:
    <event> → tipo de fenómeno
    <severity> → Minor/Moderate/Severe/Extreme
    <areaDesc> → nombre de la zona
    <parameter><valueName>awareness_type</valueName>...</parameter>
    """
    cache_key = f"aemet_{round(lat, 2)}_{round(lon, 2)}"
    now = datetime.now()

    if cache_key in _aemet_cache:
        cached = _aemet_cache[cache_key]
        if (now - cached["ts"]).total_seconds() < AEMET_TTL:
            return JSONResponse(cached["data"])

    result = _default_result()

    try:
        import xml.etree.ElementTree as ET

        headers = {"api_key": AEMET_KEY, "Accept": "application/json"}

        # 1) Obtener URL de datos
        r1 = requests.get(
            "https://opendata.aemet.es/opendata/api/avisos_cap/ultimoelaborado/todasAreas",
            headers=headers, timeout=10
        )
        r1.raise_for_status()
        meta = r1.json()
        data_url = meta.get("datos")
        if not data_url:
            raise ValueError("Sin URL de datos AEMET")

        # 2) Descargar datos CAP
        r2 = requests.get(data_url, headers=headers, timeout=15)
        r2.raise_for_status()
        content_type = r2.headers.get("Content-Type", "")

        # 3) Obtener provincia para filtrar zonas
        prov_res = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            headers={"User-Agent": "GranizoApp/1.0"},
            params={"lat": lat, "lon": lon, "format": "json"},
            timeout=8
        )
        addr = prov_res.json().get("address", {})
        province = (addr.get("province") or addr.get("state") or "").lower()
        # Normalizar: "Álava/Araba" → "alava"
        province_words = set(
            w.strip("/()")
            for w in province.replace("á","a").replace("é","e").replace("í","i")
                             .replace("ó","o").replace("ú","u").lower().split()
        )

        # 4) Parsear XML CAP (AEMET usa formato CAP 1.2, un <alert> por aviso,
        #    o bien un fichero multi-alert)
        ns = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}

        def parse_cap_xml(xml_text):
            """Extrae alertas relevantes del XML CAP."""
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                return

            # El fichero puede ser un <alert> o un wrapper con múltiples <alert>
            alerts = root.findall(".//cap:alert", ns) or ([root] if root.tag.endswith("alert") else [])

            for alert in alerts:
                for info in alert.findall("cap:info", ns):
                    # Solo español
                    lang = info.findtext("cap:language", default="es", namespaces=ns)
                    if lang and lang.lower() not in ("es", "es-es", ""):
                        continue

                    event = (info.findtext("cap:event", default="", namespaces=ns) or "").lower()
                    severity_raw = (info.findtext("cap:severity", default="", namespaces=ns) or "").lower()
                    area_desc = ""

                    for area in info.findall("cap:area", ns):
                        area_desc += (area.findtext("cap:areaDesc", default="", namespaces=ns) or "").lower() + " "

                    # También mirar parámetros awareness_type / awareness_level
                    awareness_type = ""
                    awareness_level = ""
                    for param in info.findall("cap:parameter", ns):
                        pname = (param.findtext("cap:valueName", default="", namespaces=ns) or "").lower()
                        pval  = (param.findtext("cap:value", default="", namespaces=ns) or "").lower()
                        if "awareness_type" in pname:
                            awareness_type = pval
                        if "awareness_level" in pname:
                            awareness_level = pval

                    # Filtrar por zona geográfica
                    zona_text = area_desc + " " + event
                    if province_words and not any(w in zona_text for w in province_words):
                        continue

                    # Determinar tipo de fenómeno
                    tipo = None
                    search_text = event + " " + awareness_type
                    for keyword, category in CAP_EVENT_MAP.items():
                        if keyword in search_text:
                            tipo = category
                            break

                    if not tipo:
                        continue

                    # Determinar nivel
                    nivel = CAP_SEVERITY_MAP.get(severity_raw) or CAP_SEVERITY_MAP.get(awareness_level, "amarillo")

                    # Umbral / valor
                    valor = None
                    for param in info.findall("cap:parameter", ns):
                        pname = (param.findtext("cap:valueName", default="", namespaces=ns) or "").lower()
                        pval  = (param.findtext("cap:value", default="", namespaces=ns) or "")
                        if any(k in pname for k in ("umbral", "threshold", "valor", "value")):
                            valor = pval
                            break

                    # Actualizar si este nivel es peor
                    if LEVEL_ORDER[nivel] > LEVEL_ORDER[result[tipo]["nivel"]]:
                        result[tipo]["nivel"] = nivel
                        result[tipo]["valor"] = valor

        # Intentar parsear como XML
        if "xml" in content_type or r2.text.strip().startswith("<"):
            parse_cap_xml(r2.text)
        elif "json" in content_type:
            # Algunos endpoints devuelven JSON con lista de avisos
            try:
                avisos = r2.json()
                if isinstance(avisos, list):
                    for aviso in avisos:
                        event = (aviso.get("evento") or aviso.get("event") or "").lower()
                        severity = (aviso.get("nivel") or aviso.get("severity") or "").lower()
                        zona = (aviso.get("zona") or aviso.get("area") or "").lower()
                        if province_words and not any(w in zona for w in province_words):
                            continue
                        tipo = next((cat for kw, cat in CAP_EVENT_MAP.items() if kw in event), None)
                        if not tipo: continue
                        nivel = CAP_SEVERITY_MAP.get(severity, "amarillo")
                        if LEVEL_ORDER[nivel] > LEVEL_ORDER[result[tipo]["nivel"]]:
                            result[tipo]["nivel"] = nivel
                            result[tipo]["valor"] = aviso.get("umbral")
            except Exception:
                pass

    except Exception as e:
        print(f"[AEMET] Error: {e} — usando valores por defecto")
        # Sin datos AEMET: dejar todo verde, no mostrar error al usuario

    # Construir ticker
    LABEL = {"calor": "calor", "lluvia": "lluvia/tormentas", "nieve": "nieve", "granizo": "granizo"}
    UNIT  = {"calor": "ºC", "lluvia": " mm", "nieve": " cm", "granizo": ""}
    mensajes = []
    for tipo, info in result.items():
        if tipo == "ticker": continue
        if info["nivel"] != "verde":
            nivel_txt = info["nivel"].capitalize()
            valor_txt = f": temperatura > {info['valor']}{UNIT[tipo]}" if (tipo == "calor" and info["valor"]) \
                        else (f": {info['valor']}{UNIT[tipo]}" if info["valor"] else "")
            mensajes.append(f"Alerta {nivel_txt} por {LABEL[tipo]}{valor_txt}")

    result["ticker"] = mensajes if mensajes else ["No hay alertas activas"]

    _aemet_cache[cache_key] = {"ts": now, "data": result}
    return JSONResponse(result)


_hail_cache: dict = {}
CACHE_TTL_SECONDS = 3600


@app.get("/get-hail-prediction")
def get_hail_prediction(lat: float, lon: float):
    cache_key = f"{round(lat, 3)}_{round(lon, 3)}"
    now = datetime.now()

    if cache_key in _hail_cache:
        cached = _hail_cache[cache_key]
        age = (now - cached["timestamp"]).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return JSONResponse(cached["data"])

    try:
        prediction = predict_hail(lat, lon)
        _hail_cache[cache_key] = {"timestamp": now, "data": prediction}
        return JSONResponse(prediction)
    except Exception as e:
        print(f"[HailPrediction] Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)