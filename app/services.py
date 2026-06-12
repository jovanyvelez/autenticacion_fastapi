"""
Capa de lógica de negocio.

Las operaciones de auth (registrar, autenticar) viven acá. Orquestan
`app.db` (storage) y `app.security` (crypto). No conocen HTTP, cookies
ni templates — eso es responsabilidad de la capa de presentación
(`app.routes`).

Convenciones de error:
  - Duplicado al registrar → excepción `EmailAlreadyRegistered`. Es una
    condición excepcional, no flujo normal, por eso lanza.
  - Credenciales inválidas al autenticar → `None`. Es un lookup que
    puede "no encontrar"; idiomático en Python devolver None.
"""

from app import db, security


class EmailAlreadyRegistered(Exception):
    """Se intentó registrar un email que ya existe en el store."""


def register_user(email: str, password: str) -> None:
    """
    Hashea la contraseña y persiste un usuario nuevo.

    Lanza `EmailAlreadyRegistered` si el email ya estaba registrado — la
    capa de presentación decide cómo traducir eso a una respuesta HTTP.
    """
    if db.user_exists(email):
        raise EmailAlreadyRegistered(email)
    db.add_user(email, security.hash_password(password))


def authenticate_user(email: str, password: str) -> str | None:
    """
    Verifica credenciales y devuelve el subject (email) si son válidas,
    o None si el email no existe o la contraseña no coincide.

    Devolver el mismo `None` en ambos casos es deliberado: la capa de
    presentación no debe poder distinguir "email no existe" de
    "contraseña mal" (no filtra información a un atacante).
    """
    user = db.get_user(email)
    if not user or not security.verify_password(password, user["hashed_password"]):
        return None
    return user["email"]
