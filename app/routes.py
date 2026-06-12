"""
Capa de presentación.

Rutas HTTP, dependencias FastAPI, templates, cookies. Es un adaptador
HTTP↔dominio:
  - Parsea formularios.
  - Llama a `app.services` (operaciones de dominio).
  - Traduce resultados a `HTMLResponse` o `RedirectResponse`.
  - Maneja cookies vía `app.security` (que encapsula httponly, max_age, etc).

No conoce storage ni hashing — solo HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import services
from app import security

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# -----------------------------------------------------------------------------
# Dependencias
# -----------------------------------------------------------------------------
def get_current_user(request: Request) -> str | None:
    """
    Lee la cookie, decodifica el JWT y devuelve el email (subject).
    Devuelve None si no hay cookie o el token es inválido/expirado.

    Es el adaptador entre HTTP (la cookie) y el dominio (el subject). La
    capa `security` no necesita conocer `Request`.
    """
    token = request.cookies.get(security.COOKIE_NAME)
    if not token:
        return None
    return security.decode_access_token(token)


# Alias de tipo para reusar la dependencia en las rutas que necesiten
# el usuario actual inyectado en el handler.
CurrentUserDep = Annotated[str | None, Depends(get_current_user)]


def render(request: Request, template: str, **ctx) -> HTMLResponse:
    """
    Helper para no repetir la lógica de "siempre paso `user` a la plantilla"
    y así el nav de base.html sabe si mostrar Login/Logout.
    """
    user = get_current_user(request)
    return templates.TemplateResponse(
        request=request, name=template, context={"user": user, **ctx}
    )


# -----------------------------------------------------------------------------
# Rutas
# -----------------------------------------------------------------------------
@router.get("/")
def home(request: Request) -> HTMLResponse:
    return render(request, "login.html")  # o una página de inicio, da igual


@router.get("/register")
def register_form(request: Request) -> HTMLResponse:
    return render(request, "register.html")


@router.post("/register", response_model=None)
def register(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    try:
        services.register_user(email, password)
    except services.EmailAlreadyRegistered:
        return render(request, "register.html", error="Ese email ya está registrado")
    return RedirectResponse("/login", status_code=303)


@router.get("/login")
def login_form(request: Request) -> HTMLResponse:
    return render(request, "login.html")


@router.post("/login", response_model=None)
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    subject = services.authenticate_user(email, password)
    # Mensaje genérico a propósito: no le digas al atacante si el email existe.
    if not subject:
        return render(request, "login.html", error="Credenciales inválidas")

    response: RedirectResponse = RedirectResponse("/dashboard", status_code=303)
    security.set_token_cookie(response, subject=subject)
    return response


@router.get("/dashboard", response_model=None)
def dashboard(
    request: Request, user: CurrentUserDep
) -> HTMLResponse | RedirectResponse:
    if not user:
        return RedirectResponse("/login", status_code=303)
    return render(request, "dashboard.html")


@router.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    security.clear_token_cookie(response)
    return response
