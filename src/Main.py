from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Importar tus clases
from models.User import User
from models.Field import Field
from models.Point import Point

app = FastAPI()

# Montar carpeta estática
app.mount("/static", StaticFiles(directory="static"), name="static")

# Plantillas HTML
templates = Jinja2Templates(directory="templates")

# Base de datos temporal en memoria
users = []
fields = []
current_user = None


# --- RUTAS ---

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    global current_user
    for user in users:
        if user.login(username, password):
            current_user = user
            return RedirectResponse(url="/main", status_code=303)
    # Fallo de login
    return templates.TemplateResponse("login.html", {"request": request, "error": "Usuario o contraseña incorrectos"})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    global users
    # Comprobar si el usuario ya existe
    for u in users:
        if u.username == username:
            return templates.TemplateResponse("register.html", {"request": request, "error": "Usuario ya existe"})
    # Crear nuevo usuario
    user = User(username, password)
    users.append(user)
    return RedirectResponse(url="/", status_code=303)


@app.get("/main", response_class=HTMLResponse)
def main_page(request: Request):
    if current_user is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("main.html", {"request": request, "fields": fields, "user": current_user})