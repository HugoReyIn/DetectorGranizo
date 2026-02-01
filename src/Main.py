from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from models.User import User
from models.Field import Field

# ----- APP -----
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ----- DAOs -----
userDAO = UserDAO()
fieldDAO = FieldDAO()

# ----- SESIÓN SIMPLE -----
current_user = None


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    global current_user
    user = userDAO.getUserByEmail(email)
    if user and user.password == password:
        current_user = user
        return RedirectResponse(url="/main", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Correo o contraseña incorrectos"}
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    existing_user = userDAO.getUserByEmail(email)
    if existing_user:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "El correo ya está registrado"}
        )
    new_user = User(email=email, password=password, name=name)
    userDAO.insertUser(new_user)
    return RedirectResponse(url="/", status_code=303)


@app.get("/main", response_class=HTMLResponse)
def main_page(request: Request):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    fields = fieldDAO.getAllFieldsByUser(current_user.id)
    
    # Si no hay campos, inicializar algunos por defecto
    if not fields:
        default_fields = [
            Field(name="Campo 1", municipality="Briñas, La Rioja", state="open"),
            Field(name="Campo 2", municipality="Haro, La Rioja", state="open"),
            Field(name="Campo 3", municipality="Casalarreina, La Rioja", state="closed"),
            Field(name="Campo 4", municipality="Haro, La Rioja", state="closed")
        ]
        for f in default_fields:
            fieldDAO.insertField(f, current_user.id)
        fields = fieldDAO.getAllFieldsByUser(current_user.id)

    return templates.TemplateResponse("main.html", {"request": request, "fields": fields, "user": current_user})
