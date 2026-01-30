from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ----- APP -----
app = FastAPI()

# Montar carpeta static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Plantillas
templates = Jinja2Templates(directory="templates")

# ----- DATOS EN MEMORIA -----
users = []
fields = []
current_user = None


# --- MODELOS SIMPLES ---
class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def login(self, username, password):
        return self.username == username and self.password == password


class Field:
    def __init__(self, name, location, state="open"):
        self.name = name
        self.location = location
        self.state = state


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
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Usuario o contraseña incorrectos"}
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    for u in users:
        if u.username == username:
            return templates.TemplateResponse(
                "register.html", {"request": request, "error": "Usuario ya existe"}
            )
    user = User(username, password)
    users.append(user)
    return RedirectResponse(url="/", status_code=303)


@app.get("/main", response_class=HTMLResponse)
def main_page(request: Request):
    if current_user is None:
        return RedirectResponse(url="/", status_code=303)
    # Inicializamos campos si está vacío
    if not fields:
        fields.extend([
            Field("Campo 1", "Briñas, La Rioja", "open"),
            Field("Campo 2", "Haro, La Rioja", "open"),
            Field("Campo 3", "Casalarreina, La Rioja", "closed"),
            Field("Campo 4", "Haro, La Rioja", "closed")
        ])
    return templates.TemplateResponse("main.html", {"request": request, "fields": fields, "user": current_user})
