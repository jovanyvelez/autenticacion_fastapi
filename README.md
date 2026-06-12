# Auth con FastAPI + JWT + Jinja2

App mínima para aprender el flujo de autenticación: email + contraseña,
hashing con Argon2, JWT firmado y plantillas Jinja2.

Los usuarios viven en un `dict` en memoria: **al reiniciar el servidor se
pierden**. Es deliberado: el objetivo es entender el flujo, no persistir.

## Cómo arrancarla

```bash
uv sync                  # instala dependencias (ya está hecho)
uv run uvicorn main:app --reload
# Alternativa equivalente, leyendo el entrypoint de pyproject.toml:
uv run fastapi dev
```

Abrí <http://127.0.0.1:8000> y probá:

1. **Registro** en `/register` → email + contraseña.
2. **Login** en `/login` → te redirige a `/dashboard`.
3. **Logout** desde el nav → borra la cookie.

Probá también ir directo a `/dashboard` sin loguearte: te redirige a `/login`.

## Estructura

```
.
├── main.py              # Bootstrap: crea FastAPI() e incluye el router
├── app/
│   ├── __init__.py
│   ├── routes.py        # Capa 1 — Presentación: rutas, dependencias, templates
│   ├── services.py      # Capa 2 — Lógica de negocio (registro, autenticación)
│   ├── db.py            # Capa 3 — Acceso a datos (dict en memoria detrás de funciones)
│   └── security.py      # Infra — Hashing + JWT + cookies (httponly/max_age)
└── templates/
    ├── base.html    # Layout común + nav dinámico (¿hay user?)
    ├── register.html
    ├── login.html
    └── dashboard.html
```

La cadena de dependencias va `routes → services → (db, security)` y es
estricta: cada capa solo conoce las que están "debajo". `security` es
infraestructura (la usan tanto `routes` para las cookies como `services`
para hashear), no una capa del refactor de tres capas.

## Cómo funciona, pieza por pieza

### 1. Hashing de contraseñas — `auth.py`

```python
password_hash = PasswordHash.recommended()       # Argon2 por defecto
hash_password("secreto123")  # → "$argon2id$v=19$m=...$..."
```

`pwdlib` se encarga del sal y del coste. **Nunca guardes la contraseña en
plano** y nunca compares con `==` (vulnerable a *timing attacks*): siempre
usá `verify_password`.

### 2. JWT — `auth.py`

Un JWT son tres partes en base64: `header.payload.signature`.

```python
create_access_token("juan@example.com")
# → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIi..." 
```

- `sub` (subject) → a quién identifica el token.
- `exp` (expiration) → cuándo expira. PyJWT lo valida al decodificar y lanza
  `ExpiredSignatureError` si pasó la fecha.
- La **firma** se calcula con `HMAC-SHA256(secret, header.payload)`. Si
  alguien modifica el payload, la firma ya no coincide → token inválido.

`decode_access_token` devuelve el `sub` (email) o `None` si el token
expiró, está mal formado o la firma no verifica.

### 3. La "base de datos" — `db.py`

```python
users_db: dict[str, dict] = {}
# users_db["juan@example.com"] = {"email": "...", "hashed_password": "..."}
```

Clave = email (único). Para producción acá iría SQLAlchemy + una DB real.

### 4. Rutas — `main.py`

| Ruta          | Método | Qué hace                                                      |
| ------------- | ------ | ------------------------------------------------------------- |
| `/`           | GET    | Muestra el login                                              |
| `/register`   | GET    | Formulario de registro                                        |
| `/register`   | POST   | Hashea y guarda; redirige a `/login`                          |
| `/login`      | GET    | Formulario de login                                           |
| `/login`      | POST   | Verifica; crea JWT; lo mete en cookie HttpOnly; redirige      |
| `/dashboard`  | GET    | **Protegida**: lee cookie → decodifica JWT → muestra saludo   |
| `/logout`     | GET    | Borra la cookie                                               |

La dependencia `get_current_user` se inyecta con `Depends` y devuelve el
email o `None`. Las rutas protegidas hacen `if not user: redirect /login`.

### 5. La cookie HttpOnly

```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,    # JS no puede leerla (mitiga XSS)
    max_age=60 * 30,  # 30 min, alineado con ACCESS_TOKEN_EXPIRE_MINUTES
)
```

Va como cookie y no en `Authorization: Bearer` porque estamos con
formularios HTML en el navegador. Si después querés una API, agregás un
endpoint `/token` con `OAuth2PasswordBearer` y devolvés el JWT en el body.

## Cosas que NO están (y que para producción sí)

- Persistencia (SQLite, Postgres, lo que sea).
- HTTPS obligatorio.
- Refresh tokens (hoy, al expirar hay que volver a loguearse).
- `SECRET_KEY` desde variable de entorno, no hardcodeada.
- CSRF protection para los POST de formularios.
- Validación de fuerza de la contraseña.
- Rate limiting en `/login` (anti fuerza bruta).

Cualquiera de estos se puede ir sumando cuando los necesites. Avisame
cuál querés abordar primero.

---

# 🎓 Curso de autoestudio

Un recorrido progresivo por la app. Cada lección mezcla lectura, un
ejercicio práctico y preguntas para que te quede claro el **por qué**,
no solo el **cómo**.

**Cómo usarlo:** andá en orden. Cada lección asume que hiciste las
anteriores. Tiempo total estimado: 2-3 horas, pero podés ir a tu ritmo.

## Mapa mental del proyecto

Antes de empezar, mirá el flujo completo de un usuario que se loguea:

```
Navegador                         Servidor (FastAPI)
   │                                      │
   │  GET /login                          │
   │ ─────────────────────────────────►   │  → render(login.html)
   │ ◄──────────────────────────────────  │
   │  (form HTML)                         │
   │                                      │
   │  POST /login  email + password       │
   │ ─────────────────────────────────►   │  → verify_password()
   │                                      │  → create_access_token()
   │                                      │  → Set-Cookie: access_token=...
   │ ◄──────────────────────────────────  │  ← 303 /dashboard
   │  GET /dashboard  (con cookie)        │
   │ ─────────────────────────────────►   │  → get_current_user()
   │                                      │  → decode_access_token()
   │ ◄──────────────────────────────────  │  ← 200 dashboard.html
```

Las piezas concretas que vas a tocar en cada lección:

| Lección | Archivos                | Conceptos nuevos                      |
| ------- | ----------------------- | ------------------------------------- |
| 1       | (solo la app corriendo) | HTTP, cookies, request/response       |
| 2       | `auth.py`               | Hashing, sal, Argon2, timing attacks  |
| 3       | `auth.py`, `main.py`    | Estructura de un JWT, firma, expiración |
| 4       | `main.py`               | Cookies HttpOnly, SameSite, XSS/CSRF  |
| 5       | `main.py`               | `Depends`, inyección de dependencias  |
| 6       | todos                   | Consolidar modificando la app         |

---

## Lección 1 · Trazá vos mismo el flujo completo (15 min)

**Objetivo:** entender qué pasa entre que abrís el navegador y ves tu
email en el dashboard.

1. Levantá la app: `uv run uvicorn main:app --reload`.
2. Abrí DevTools del navegador (F12) → pestaña **Network**.
3. Hacé un registro y un login. Anotá:
   - ¿Qué método HTTP usa cada request?
   - ¿Qué códigos de status devuelve el servidor?
   - ¿En qué momento aparece la cookie `access_token`?
   - ¿Se manda automáticamente en cada request siguiente?
4. Repetí lo mismo con `curl`:

   ```bash
   curl -i -X POST http://127.0.0.1:8000/login \
     -d "email=juan@example.com" -d "password=secreto123"
   ```

   La opción `-i` muestra los headers de respuesta, donde vas a ver
   `Set-Cookie: access_token=...` y `Location: /dashboard`.

**Pregunta para reflexionar:** ¿por qué el navegador manda la cookie
sola en cada request, pero `curl` necesita `-b cookies.txt`?

**Lo que aprendiste:** el ciclo request/response de HTTP, y que las
cookies son el mecanismo estándar del navegador para mantener estado
entre requests.

---

## Lección 2 · Hashing: por qué Argon2 y no "guardar la contraseña" (20 min)

**Objetivo:** entender qué hace `hash_password` y por qué el hash no
se puede "revertir".

1. Abrí `auth.py`. La línea clave es:

   ```python
   password_hash = PasswordHash.recommended()
   ```

   `recommended()` elige Argon2id con parámetros por defecto seguros.
   Hay alternativas (bcrypt, scrypt) — todas son "funciones de derivación
   de clave con coste de memoria": el cálculo es intencionalmente caro
   para que los ataques con rainbow tables o GPU no sirvan.

2. **Ejercicio:** en una consola de Python con el venv activado:

   ```python
   from auth import hash_password, verify_password
   h1 = hash_password("secreto123")
   h2 = hash_password("secreto123")
   print(h1 == h2)                  # False — la sal es aleatoria
   print(h1[:30])                   # Mirá el prefijo $argon2id$...
   verify_password("secreto123", h1)  # True
   verify_password("otra",     h1)    # False
   ```

   Que `h1 != h2` te debería llamar la atención. Dos hashes distintos
   para la misma contraseña es **deseable**: significa que cada usuario
   tiene su propia sal, y un atacante no puede precalcular hashes en
   bloque.

3. **Por qué `verify` y no `==`:** una comparación con `==` corta en
   cuanto encuentra una diferencia. Eso filtra información sobre
   cuántos caracteres coinciden. `verify` hace la comparación en
   tiempo constante.

**Pregunta para reflexionar:** si un atacante roba la base de datos
y tiene los hashes, ¿puede saber qué usuarios comparten contraseña?
Mirá los prefijos de los hashes — ¿qué cambia entre uno y otro?

**Lo que aprendiste:** Argon2 es lento a propósito, la sal es aleatoria
por usuario, y la verificación debe ser en tiempo constante.

---

## Lección 3 · Anatomía de un JWT (25 min)

**Objetivo:** entender las 3 partes de un JWT y poder decodificar uno
a mano.

1. Logueate en la app y copiá el valor de la cookie `access_token`
   desde DevTools (Application → Cookies).

2. Pegalo en [jwt.io](https://jwt.io) y mirá:
   - **Header:** `{"alg":"HS256","typ":"JWT"}` — qué algoritmo se usó.
   - **Payload:** `{"sub":"tu@email.com","exp":1234567890}` — los datos
     (claims).
   - **Signature:** una firma HMAC. Probá cambiar un carácter del
     payload en jwt.io y mirá qué pasa con la signature.

3. **Ejercicio:** decodificá el payload a mano desde la terminal:

   ```bash
   TOKEN="pegar_acá_el_jwt"
   echo "$TOKEN" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null
   ```

   Esto es exactamente lo que hace `jwt.decode` por dentro (más la
   verificación de la firma y la expiración).

4. **¿Por qué la firma es importante?** En `auth.py`:

   ```python
   jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
   ```

   La firma es `HMAC-SHA256(SECRET_KEY, header + "." + payload)`. Si
   alguien edita el payload (por ejemplo cambia el `sub` para
   impersonar a otro usuario), la firma ya no coincide y `jwt.decode`
   rechaza el token.

5. **El `exp`:** PyJWT chequea la fecha de expiración automáticamente.
   Para verlo:
   - Cambiá `ACCESS_TOKEN_EXPIRE_MINUTES = 1` en `auth.py`.
   - Reiniciá la app, logueate, esperá 1 min, intentá ir a `/dashboard`.
   - Te redirige a `/login`.

**Pregunta para reflexionar:** JWT no está "cifrado" — está **firmado**.
Eso significa que cualquiera puede leer el payload. ¿Por qué no es un
problema que el email viaje en texto claro dentro del token?

**Lo que aprendiste:** JWT = tres partes en base64 (header.payload.
signature). La firma HMAC garantiza integridad; el `exp` garantiza
validez temporal.

---

## Lección 4 · Cookies y seguridad (15 min)

**Objetivo:** entender por qué la cookie es `HttpOnly` y no
`localStorage`.

1. En `main.py`:

   ```python
   response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, max_age=...)
   ```

2. **Ejercicio:** en DevTools → Application → Cookies, mirá la cookie
   `access_token`. Fijate en:
   - **HttpOnly** ✓ — JS no puede leerla. Probá en la consola:
     `document.cookie` → la cookie no aparece.
   - **SameSite=Lax** — el navegador no la manda en requests cross-site
     (mitiga CSRF).
   - **Path=/** — se manda a todas las rutas.

3. **¿Por qué no `localStorage`?** Porque cualquier script inyectado
   (XSS) puede hacer `localStorage.getItem("token")` y robarlo. Con
   HttpOnly el atacante necesita otra vía.

4. **¿Qué falta para producción?**
   - `secure=True`: que la cookie solo viaje por HTTPS.
   - `samesite="strict"` (más agresivo que `lax`).
   - **CSRF tokens** en formularios POST — porque la cookie se manda
     sola, un sitio malicioso podría hacer submit a `/login` o
     `/logout` desde otro origen.

**Pregunta para reflexionar:** ¿qué pasa si copiás la cookie de tu
navegador a otro navegador (con DevTools)? ¿Sirve como ataque? ¿Por
qué funciona o por qué no?

**Lo que aprendiste:** la cookie es el "boleto" de sesión del navegador.
Sus flags controlan quién puede verla y cuándo se manda.

---

## Lección 5 · La dependencia `get_current_user` (20 min)

**Objetivo:** entender el patrón de inyección de dependencias de
FastAPI.

1. En `main.py`:

   ```python
   def get_current_user(request: Request) -> str | None:
       token = request.cookies.get(COOKIE_NAME)
       if not token:
           return None
       return decode_access_token(token)
   ```

2. Y en la ruta protegida:

   ```python
   # Arriba en el archivo, junto a la dependencia:
   CurrentUserDep = Annotated[str | None, Depends(get_current_user)]

   @app.get("/dashboard", response_model=None)
   def dashboard(request: Request, user: CurrentUserDep) -> HTMLResponse | RedirectResponse:
       if not user:
           return RedirectResponse("/login", status_code=303)
       return render(request, "dashboard.html")
   ```

   El alias `CurrentUserDep` agrupa el tipo y la dependencia en un solo
   símbolo reutilizable, así no repetís el `Depends(...)` cada vez.

3. **Lo que hace FastAPI por debajo:**
   - Antes de llamar a `dashboard`, ejecuta `get_current_user(request)`.
   - El valor retornado se inyecta como el parámetro `user`.
   - Podés reutilizar la misma dependencia (o su alias) en cualquier ruta.

4. **Ejercicio:** agregá una nueva ruta `/api/me` que devuelva el
   email en JSON:

   ```python
   from fastapi.responses import JSONResponse

   @app.get("/api/me", response_model=None)
   def me(user: CurrentUserDep) -> JSONResponse | dict:
       if not user:
           return JSONResponse({"error": "unauthorized"}, status_code=401)
       return {"email": user}
   ```

   Probala con y sin cookie:

   ```bash
   curl -i http://127.0.0.1:8000/api/me                       # 401
   curl -i -b cookies.txt http://127.0.0.1:8000/api/me        # 200
   ```

5. **Variante "obligatoria":** si querés que una ruta *siempre* tenga
   user, hacé que la dependencia lance `HTTPException(401)` en vez de
   devolver `None`. Eso evita repetir el `if not user: ...` en cada
   ruta protegida.

**Pregunta para reflexionar:** ¿por qué `get_current_user` recibe
`request` explícitamente? ¿No podría tomar la cookie de otro lado
(por ejemplo, de un parámetro de la dependencia)?

**Lo que aprendiste:** `Depends` es el mecanismo de FastAPI para
extraer lógica repetible (auth, DB, etc.) fuera de las rutas.

---

## Lección 6 · Modificaciones guiadas (30 min)

Pequeños cambios para consolidar lo que viste. Hacé uno por día o de
una sola vez, lo que prefieras.

### 6.1 · Cambiar la duración del token

- En `auth.py`, bajá `ACCESS_TOKEN_EXPIRE_MINUTES` a 1.
- Reiniciá la app, logueate, esperá 1 min, intentá ir a `/dashboard`.
- Mirá qué pasa exactamente. Pista: `decode_access_token` devuelve
  `None` porque PyJWT lanza `ExpiredSignatureError` y nosotros la
  capturamos como `PyJWTError`.

### 6.2 · Agregar un campo al usuario

- En `db.py`, agregale un campo `name` al dict del usuario.
- En `register.html`, pedilo en el formulario.
- En el `POST /register`, validá que no esté vacío.
- En `dashboard.html`, mostrale `{{ name }}` con el nombre (no el email).
- Vas a tener que cambiar la firma del helper `render` y/o pasar el
  `name` además del email al `dashboard.html`.

### 6.3 · Hash de la contraseña antes de hashear (no lo hagas en serio)

Para entender *por qué* hay funciones de hashing dedicadas, probá:

```python
import hashlib
hashlib.sha256("secreto123".encode()).hexdigest()
```

- ¿Qué pasa si dos usuarios eligen la misma contraseña? Mismo hash.
- ¿Qué pasa si un atacante precalcula hashes de contraseñas comunes?
  Las encuentra al instante.
- Argon2 resuelve los dos: sal aleatoria + algoritmo caro.

### 6.4 · Endpoint "register" sin formulario (JSON)

Para entender la diferencia entre formularios y APIs:

```python
from pydantic import BaseModel

class UserIn(BaseModel):
    email: str
    password: str

@app.post("/api/register")
def api_register(user: UserIn):
    if user.email in users_db:
        return {"error": "exists"}
    users_db[user.email] = {
        "email": user.email,
        "hashed_password": hash_password(user.password),
    }
    return {"ok": True}
```

Probá con `curl`:

```bash
curl -X POST http://127.0.0.1:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@example.com","password":"clave"}'
```

Mirá cómo cambia el `Content-Type` y la ausencia/presencia de redirect
(303) en la respuesta.

**Pregunta para reflexionar:** la versión formulario redirige a
`/login` con 303. La versión API devuelve JSON con 200. ¿Por qué esa
asimetría? (Pista: ¿quién es el "cliente" en cada caso?)

---

## Recursos para profundizar

- **HTTP y cookies:**
  - [MDN: HTTP cookies](https://developer.mozilla.org/es/docs/Web/HTTP/Cookies)
  - [MDN: Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- **Hashing:**
  - [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
  - [Argon2 RFC 9106](https://datatracker.ietf.org/doc/html/rfc9106) — la intro es accesible
- **JWT:**
  - [jwt.io](https://jwt.io) — para decodificar tokens visualmente
  - [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519) — más legible de lo que parece
- **FastAPI:**
  - [Tutorial oficial: Security](https://fastapi.tiangolo.com/es/tutorial/security/) — cubre OAuth2 con JWT
  - [Tutorial oficial: Dependencies](https://fastapi.tiangolo.com/es/tutorial/dependencies/)

## Próximos pasos sugeridos

Cuando termines este curso, los siguientes pasos lógicos son:

1. **Persistencia:** cambiar `db.py` para usar SQLite (o SQLAlchemy). El resto del código casi no cambia.
2. **Refresh tokens:** hoy, al expirar, hay que volver a loguearse. Un refresh token largo permite renovar el access token sin pedir contraseña.
3. **CSRF:** proteger los POST de los formularios con un token anti-CSRF.
4. **OAuth2PasswordBearer:** agregar un endpoint `/token` estándar para que clientes no-navegador (apps móviles, otros servicios) puedan autenticarse.
5. **Tests:** escribir tests con `pytest` y `httpx` que cubran registro, login, dashboard protegido, expiración.

Avisame cuál te tienta y lo armamos.
