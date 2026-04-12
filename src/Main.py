"""
Main.py
Punto de entrada de la aplicación FastAPI.
"""

import os
import logging

from settings.LoggingConfig import setup_logging
setup_logging()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO

from facades.OpenMeteoFacade import OpenMeteoFacade
from facades.NominatimFacade import NominatimFacade

from services.UserService import UserService
from services.FieldService import FieldService
from services.WeatherService import WeatherService
from services.EmailService import EmailService
from settings.AlertMonitor import AlertMonitor

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# INYECCIÓN DE DEPENDENCIAS
# ──────────────────────────────────────────────
_user_dao  = UserDAO()
_field_dao = FieldDAO()
_point_dao = PointDAO()

_meteo_facade     = OpenMeteoFacade()
_nominatim_facade = NominatimFacade()

user_service    = UserService(_user_dao)
field_service   = FieldService(_field_dao, _point_dao)
weather_service = WeatherService(_meteo_facade, _nominatim_facade)
email_service   = EmailService()

alert_monitor = AlertMonitor(
    user_dao        = _user_dao,
    field_dao       = _field_dao,
    point_dao       = _point_dao,
    weather_service = weather_service,
    email_service   = email_service,
)


# ──────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    alert_monitor.start()
    yield
    alert_monitor.stop()


# ──────────────────────────────────────────────
# APP + MIDDLEWARE DE SESIÓN
# ──────────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET_KEY", "dev-secret-cambia-en-produccion"),
    max_age=86400,
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ──────────────────────────────────────────────
# HELPERS DE SESIÓN
# ──────────────────────────────────────────────
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return user_service.get_by_id(user_id)


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=403, detail="No autorizado")
    return user


def redirect_if_not_logged(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/", status_code=303)
    return user, None


# ──────────────────────────────────────────────
# LOGIN / REGISTER / LOGOUT
# ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = user_service.authenticate(email, password)
    if user:
        request.session["user_id"] = user.id
        return RedirectResponse(url="/main", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    _, error = user_service.register(name, email, password)
    if error:
        return templates.TemplateResponse("register.html", {"request": request, "error": error})
    return RedirectResponse(url="/", status_code=303)


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────
@app.get("/main", response_class=HTMLResponse)
def main_page(request: Request):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    fields = field_service.get_fields_for_user(current_user.id)
    return templates.TemplateResponse(
        "main.html",
        {"request": request, "fields": fields, "current_user": current_user, "active_page": "main"},
    )


# ──────────────────────────────────────────────
# PERFIL
# ──────────────────────────────────────────────
@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "current_user": current_user, "active_page": "profile", "msg": None, "msg_type": ""},
    )


@app.post("/profile")
def update_profile(
    request: Request,
    name:             str = Form(...),
    email:            str = Form(...),
    current_password: str = Form(default=""),
    new_password:     str = Form(default=""),
    confirm_password: str = Form(default=""),
):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    updated_user, msg, msg_type = user_service.update_profile(
        current_user, name, email, current_password, new_password, confirm_password
    )
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "current_user": updated_user, "active_page": "profile", "msg": msg, "msg_type": msg_type},
    )


# ──────────────────────────────────────────────
# FIELD CRUD
# ──────────────────────────────────────────────
@app.get("/field/new", response_class=HTMLResponse)
def new_field_page(request: Request):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "field.html",
        {"request": request, "field": None, "points_json": "[]", "current_user": current_user, "active_page": "new_field"},
    )


@app.post("/field/new")
def save_field(
    request: Request,
    name:         str = Form(...),
    municipality: str = Form(...),
    area:         str = Form(...),
    points:       str = Form(...),
    crop_type:    str = Form(default=""),
):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    field_service.create_field(current_user.id, name, municipality, area, points, crop_type)
    return RedirectResponse(url="/main", status_code=303)


@app.get("/field/edit/{field_id}", response_class=HTMLResponse)
def edit_field_page(request: Request, field_id: int):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    field = field_service.get_field_if_owned(field_id, current_user.id)
    if not field:
        return RedirectResponse(url="/main", status_code=303)
    points_json = field_service.get_points_json(field_id)
    return templates.TemplateResponse(
        "field.html",
        {"request": request, "field": field, "points_json": points_json, "current_user": current_user, "active_page": "field"},
    )


@app.post("/field/edit/{field_id}")
def update_field(
    request: Request,
    field_id:     int,
    name:         str = Form(...),
    municipality: str = Form(...),
    area:         str = Form(...),
    points:       str = Form(...),
    crop_type:    str = Form(default=""),
):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    field = field_service.get_field_if_owned(field_id, current_user.id)
    if not field:
        return RedirectResponse(url="/main", status_code=303)
    field_service.update_field(field, name, municipality, area, points, crop_type)
    return RedirectResponse(url="/main", status_code=303)


@app.post("/field/delete/{field_id}")
def delete_field(request: Request, field_id: int):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    field = field_service.get_field_if_owned(field_id, current_user.id)
    if not field:
        return RedirectResponse(url="/main", status_code=303)
    field_service.delete_field(field_id)
    return RedirectResponse(url="/main", status_code=303)


@app.post("/field/update-status/{field_id}")
async def update_field_status(field_id: int, request: Request):
    current_user = require_user(request)
    data      = await request.json()
    new_state = data.get("state")
    field     = field_service.get_field_if_owned(field_id, current_user.id)
    if not field:
        return JSONResponse({"error": "Campo no encontrado o no autorizado"}, status_code=404)
    try:
        field_service.update_state(field, new_state)
    except ValueError:
        return JSONResponse({"error": "Estado inválido"}, status_code=400)
    return JSONResponse({"success": True, "new_state": new_state})


# ──────────────────────────────────────────────
# WEATHER PAGES
# ──────────────────────────────────────────────
@app.get("/weather/{field_id}", response_class=HTMLResponse)
def hourly_weather_page(request: Request, field_id: int):
    current_user, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    field = field_service.get_field_if_owned(field_id, current_user.id)
    if not field:
        return RedirectResponse(url="/main", status_code=303)
    return templates.TemplateResponse("weather.html", {"request": request, "field": field})


@app.get("/weather", response_class=HTMLResponse)
def weather_page(request: Request):
    _, redirect = redirect_if_not_logged(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("weather.html", {"request": request})


# ──────────────────────────────────────────────
# API ENDPOINTS — WEATHER DATA
# ──────────────────────────────────────────────
@app.get("/get-municipio")
def get_municipio(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        municipio = weather_service.get_municipality(lat, lon)
        return JSONResponse({"municipio": municipio})
    except Exception as e:
        return JSONResponse({"municipio": "Desconocido", "error": str(e)})


@app.get("/get-weather")
def get_weather(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_current_weather(lat, lon))
    except Exception as e:
        logger.error("Error WEATHER: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/get-hourly-weather")
def get_hourly_weather(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_hourly_weather(lat, lon))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/get-agronomic-data")
def get_agronomic_data(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_agronomic_data(lat, lon))
    except Exception as e:
        logger.error("[AgronomicData] Error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/get-field-summary")
def get_field_summary(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_field_summary(lat, lon))
    except Exception as e:
        logger.error("[FieldSummary] Error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/get-aemet-alerts")
def get_aemet_alerts(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_aemet_alerts(lat, lon))
    except Exception as e:
        logger.error("[AEMET] Error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/get-hail-prediction")
def get_hail_prediction(request: Request, lat: float, lon: float):
    require_user(request)
    try:
        return JSONResponse(weather_service.get_hail_prediction(lat, lon))
    except Exception as e:
        logger.error("[HailPrediction] Error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/get-card-insights")
async def get_card_insights_endpoint(request: Request):
    require_user(request)
    try:
        payload   = await request.json()
        insights  = weather_service.get_agro_insights(
            data      = payload.get("data", {}),
            crop_type = payload.get("crop_type", ""),
        )
        return JSONResponse(insights)
    except Exception as e:
        logger.error("[AgroAgent] Error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)