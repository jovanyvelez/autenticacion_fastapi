"""
Capa de acceso a datos.

Para mantener la app simple, los usuarios viven en un dict en memoria.
Este módulo encapsula el contenedor detrás de funciones — las capas
superiores (servicios, rutas) no tocan el dict directamente.

REINICIA el servidor y pierdes los datos. Esto es INTENCIONAL: el objetivo
es aprender el flujo de auth, no persistencia.
"""

# email -> {"email": str, "hashed_password": str}
# Privado al módulo: el resto de la app solo accede vía las funciones de abajo.
_users: dict[str, dict] = {}


def get_user(email: str) -> dict | None:
    """Devuelve el usuario (dict con 'email' y 'hashed_password') o None si no existe."""
    return _users.get(email)


def add_user(email: str, hashed_password: str) -> None:
    """Persiste un usuario nuevo. Asume que el caller ya validó que no existía."""
    _users[email] = {"email": email, "hashed_password": hashed_password}


def user_exists(email: str) -> bool:
    """True si ya hay un usuario registrado con ese email."""
    return email in _users
