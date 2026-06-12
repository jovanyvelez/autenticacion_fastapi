"""
Infraestructura de autenticación.

Reúne las primitivas crypto (hashing + JWT) y la lógica de presentación
del token al cliente (cookie HttpOnly). El módulo no conoce `Request` ni
la app — solo recibe un `Response` cuando necesita escribir la cookie.

Es usado por dos capas:
  - `app.routes`  → presentación: lee la cookie y la borra.
  - `app.services` → dominio: hashea contraseñas y las verifica.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response
from pwdlib import PasswordHash

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------
# En producción esto debería venir de una variable de entorno.
SECRET_KEY = "supersecreto-de-pruebas-cambiar-en-produccion"
ALGORITHM = "HS256"            # HMAC + SHA-256, simétrico (misma clave firma/verifica)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
COOKIE_NAME = "access_token"

# Motor de hashing recomendado por pwdlib (Argon2 por defecto).
password_hash = PasswordHash.recommended()


# -----------------------------------------------------------------------------
# Contraseñas
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Devuelve el hash Argon2 de la contraseña. NO guardar nunca la plana."""
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Compara una contraseña plana contra un hash guardado."""
    return password_hash.verify(plain, hashed)


# -----------------------------------------------------------------------------
# Tokens JWT
# -----------------------------------------------------------------------------
def create_access_token(subject: str) -> str:
    """
    Crea un JWT firmado.
    El "subject" (sub) es a quién identifica el token: aquí, el email.
    También añadimos la fecha de expiración (exp) — PyJWT la valida al decodificar.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Decodifica y valida un JWT. Devuelve el subject (email) si es válido,
    o None si expiró, está mal formado o la firma no coincide.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# -----------------------------------------------------------------------------
# Cookie
# -----------------------------------------------------------------------------
def set_token_cookie(response: Response, subject: str) -> None:
    """
    Crea un JWT para `subject` y lo deposita en una cookie HttpOnly.

    Centraliza los flags de la cookie (httponly, max_age) en un solo lugar
    para que un cambio de política (p. ej. agregar `secure=True` o
    `samesite="strict"`) toque un único punto.
    """
    token = create_access_token(subject=subject)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,    # JS no puede leer la cookie (mitiga XSS).
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def clear_token_cookie(response: Response) -> None:
    """Borra la cookie del token en el cliente."""
    response.delete_cookie(COOKIE_NAME)
