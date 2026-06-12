"""
Bootstrap de la app.

La estructura real vive en el paquete `app/`:
  - app.routes    → presentación (rutas, dependencias, templates)
  - app.services  → lógica de negocio
  - app.db        → acceso a datos
  - app.security  → infra (crypto + cookies)

Acá solo se crea la instancia de FastAPI y se monta el router.
"""

from fastapi import FastAPI

from app.routes import router

app = FastAPI()
app.include_router(router)
