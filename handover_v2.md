# Handover v2 — Tracker Analítico de Oposiciones

**Fecha del corte:** 2026-07-10
**Propósito:** documento de traspaso para retomar el proyecto en una sesión nueva sin contexto previo. Todo lo descrito aquí ha sido verificado contra el código real en disco (no es un resumen de memoria) justo antes de escribir este documento.

**Nota sobre el encargo original de esta sesión:** se pidió documentar un modelo `WorkoutLog` en un `models.py` para rendimiento físico, supuestamente actualizado "hace un momento". **Ese modelo no existe en el proyecto** — se confirmó con el usuario que fue una confusión suya (probablemente con otra sesión/proyecto). Este documento refleja el estado **real** verificado en disco: el módulo de rendimiento físico sigue siendo `MarcaFisica` (ver sección 6). Si en la sesión anterior a esta llegaste a ver hablar de `WorkoutLog`, ignóralo — no se implementó.

---

## 1. Resumen del proyecto

SaaS para opositores a **bombero / cuerpos de emergencias** (con foco en la convocatoria de Huelva, a juzgar por los PDFs de la base de conocimiento). Combina:

- Un **dashboard gratuito**: registro de marcas físicas (dominadas, sprint, carrera, natación) y simulacros teóricos, con una "Nota Global Oposición" combinada (50% física / 50% teórica) y gráfica de evolución.
- Una **Guía del Opositor** estática (requisitos, permisos de conducir, fuentes del temario).
- Un **Plan Pro de pago** (Stripe Checkout, modo test): rutinas de entrenamiento específicas según el punto débil detectado, técnicas de estudio, y un **Tutor IA con RAG** (LangChain + Chroma + OpenAI) que responde sobre las rutinas, técnicas y cualquier PDF/TXT que el usuario cargue.
- Un **Modo Enfoque** (Pomodoro a pantalla completa, negro absoluto) con ciclos trabajo/descanso configurables y alarma sonora.
- **Autenticación multi-tenant completa**: registro/login con JWT, login con Google (OAuth2/OIDC), recuperación de contraseña vía webhook. Todos los datos (marcas, simulacros) están aislados por `usuario_id`.

El proyecto está en fase de **preparación para desplegar en Render** (Postgres + gunicorn/uvicorn ya configurados, pendiente el despliegue real — ver sección 9).

---

## 2. Stack tecnológico actual

**Backend:**
- Python 3.14, **FastAPI** sobre **Uvicorn** (`--reload` en dev; `gunicorn`/`uvicorn` listos para producción vía `Procfile`)
- **SQLAlchemy 2.x** — **SQLite en local**, **PostgreSQL en producción** (Render), decidido automáticamente por la variable de entorno `DATABASE_URL` (ver sección 6.4)
- **Pydantic 2.x** para validación
- **JWT** (`python-jose`) + **bcrypt** (`passlib`, con `bcrypt==4.0.1` fijado — ver sección 9) para auth clásica
- **Authlib** para login con Google (OAuth2/OIDC)
- **itsdangerous** para tokens firmados de recuperación de contraseña (15 min de validez)
- **httpx** para el webhook de recuperación de contraseña
- **Stripe** (`>=15.0`) — Checkout en modo test
- **LangChain 1.x** + **langchain-openai** + **langchain-chroma** + **langchain-community** + **chromadb** + **tiktoken** + **pypdf** — motor RAG del Tutor IA
- **OpenAI**: `gpt-4o-mini` (chat) + `text-embedding-3-small` (embeddings) — **migrado desde Google Gemini** en esta misma sesión (ver sección 9, historial de migraciones)

**Frontend:**
- HTML + JavaScript vanilla (un único `main.js`, ~924 líneas, sin build step, sin framework, sin módulos ES)
- **Tailwind CSS** vía CDN + CSS custom en `style.css` (~535 líneas) para todo lo que Tailwind CDN no cubre (preflight resetea listas/párrafos, necesario para el Markdown del chat)
- **Chart.js 4.4.4** (gráfica de evolución)
- **marked.js 12.0.2** + **DOMPurify 3.1.6** (vía CDN, versión fijada) — el Tutor IA responde en Markdown; se convierte a HTML y se sanea antes de insertarlo
- Diseño dark mode, acento gradiente naranja→ámbar

**Infraestructura:**
- `backend/run.py`: wrapper que lee `PORT` del entorno y lanza uvicorn con reload
- `backend/Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` (para Render)
- `.claude/launch.json`: config del preview tool de Claude Code — **cuidado**, en este entorno de desarrollo el preview tool a veces resuelve el `launch.json` de un proyecto no relacionado (`inversiones web`) en el puerto 8000; si pasa, arrancar el backend manualmente en otro puerto y redirigir la pestaña del navegador por JS, o liberar el puerto 8000 matando el proceso huérfano (verificar con `Get-CimInstance Win32_Process` antes de matar nada)
- FastAPI sirve el frontend estático directamente vía `StaticFiles` montado en `/`

---

## 3. Estructura de carpetas y archivos clave

```
tracker-oposiciones/
├── oposiciones.db                          # BD SQLite activa (dev local)
├── oposiciones.db.pre-auth-migration.bak   # backup pre-multitenant (con datos antiguos sin usuario_id)
├── oposiciones backup copia.db             # backup manual del usuario
├── handover_v2.md                          # este documento
├── .gitignore                              # .env, *.db, *.db.bak, __pycache__/, *.pyc
├── backend/
│   ├── .env                                # secretos reales (NO subir a git). Ver seccion 7
│   ├── .env.example                        # plantilla sin secretos
│   ├── Procfile                            # arranque en Render
│   ├── requirements.txt
│   ├── run.py
│   ├── Internal Database URL.txt           # ⚠️ contiene la URL real de Postgres de Render CON credenciales, en texto plano, SIN .gitignore. Ver seccion 9.
│   └── app/
│       ├── main.py                 # crea la app, SessionMiddleware (Authlib), middleware no-cache, monta 7 routers + frontend estatico
│       ├── database.py             # engine condicional SQLite/Postgres segun DATABASE_URL
│       ├── schemas.py              # todos los Pydantic: Usuario*, Token, MarcaFisica*, SimulacroTeorico*, DashboardGlobal
│       ├── models/
│       │   ├── usuario.py          # Usuario (id, email, hashed_password, is_pro, fecha_registro) + relationships
│       │   ├── marca.py            # MarcaFisica (+ usuario_id FK)
│       │   └── simulacro.py        # SimulacroTeorico (+ usuario_id FK)
│       ├── routers/
│       │   ├── auth.py             # registro, login, google/login, google/callback, olvido-password, reset-password
│       │   ├── marcas.py           # POST/GET /api/marcas (filtrado por usuario)
│       │   ├── teorica.py          # POST/GET /api/teorica (filtrado por usuario)
│       │   ├── dashboard.py        # GET /api/dashboard/global y /evolucion (filtrado por usuario)
│       │   ├── pro.py              # GET /api/pro/entrenamiento y /teorica (filtrado por usuario)
│       │   ├── pagos.py            # POST /api/pagos/checkout (Stripe, requiere login)
│       │   └── chat.py             # POST /api/pro/chat (Tutor IA, requiere login)
│       ├── services/
│       │   ├── security.py         # JWT, bcrypt, Authlib OAuth google, tokens de reset
│       │   ├── calculo.py          # motor de puntuacion fisico/teorico
│       │   ├── rutinas.py          # RUTINAS_PRO y TECNICAS_ESTUDIO_PRO (diccionarios estaticos)
│       │   └── ai_tutor.py         # motor RAG: Chroma + OpenAIEmbeddings + ChatOpenAI
│       └── conocimiento/           # PDFs/TXT que el usuario carga para ampliar el Tutor IA (ya tiene 1 PDF de convocatoria + 2 TXT)
└── frontend/
    ├── index.html                  # ~637 lineas: auth-gate, app-shell, pantalla-enfoque (Pomodoro)
    ├── css/style.css               # ~535 lineas
    └── js/main.js                  # ~924 lineas, sin modulos, todo en un archivo
```

**No es un repositorio git** (verificar con `git status` antes de asumir lo contrario).

---

## 4. Funcionalidades terminadas y verificadas

Todo lo siguiente está implementado y **verificado con pruebas reales** (TestClient, curl, y/o navegador) durante esta y sesiones anteriores:

### 4.1 Autenticación multi-tenant (JWT + Google + recuperación)
- `POST /api/auth/registro`, `POST /api/auth/login` (OAuth2 password flow estándar de FastAPI).
- `GET /api/auth/google/login` / `GET /api/auth/google/callback`: login con Google vía Authlib. Si el email no existe, crea el usuario con una contraseña aleatoria inaccesible. Redirige al frontend con `?token=<jwt>`.
- `POST /api/auth/olvido-password`: siempre responde con mensaje genérico (anti-enumeración); si el email existe y `WEBHOOK_RECUPERACION_URL` está configurado, dispara un webhook con `{email, link}` donde el link lleva `?reset_token=<token_15min>`.
- `POST /api/auth/reset-password`: verifica el token firmado (itsdangerous, 15 min) y actualiza la contraseña.
- **Todos** los routers de datos (`marcas`, `teorica`, `dashboard`, `pro`, `pagos`, `chat`) exigen `Depends(get_current_user)` y filtran por `usuario_id`.
- Frontend: pantalla de login/registro/olvido/reset, botón "Continuar con Google", `fetchAutenticado()` centraliza el header `Authorization: Bearer` en las 8 llamadas protegidas y desloguea automáticamente en 401.
- **Verificado:** aislamiento real entre dos usuarios (usuario B no ve datos de usuario A), rechazo de tokens manipulados/caducados, ciclo completo de recuperación de contraseña cambiando la credencial real.
- **No verificado en navegador real:** el flujo completo de Google OAuth (solo se probó estructuralmente con `client_id` vacío vía TestClient; el usuario ya puso credenciales reales de Google en `.env` pero nunca se hizo login real haciendo clic en el botón).

### 4.2 Cálculo de marcas físicas y simulacro teórico
- Interpolación lineal por prueba (mínimo=5, máximo=10 puntos), nota global = promedio de 4 pruebas.
- Simulacro teórico: `(aciertos - fallos/3) / total * 10`, clampeado [0,10].
- Dashboard combinado 50/50 con "veredicto del entrenador" y gráfica de evolución (Chart.js).

### 4.3 Plan Pro — muro de pago con Stripe (modo test)
- `POST /api/pagos/checkout`, requiere login. Clave de Stripe en `.env` (ya no hardcodeada).
- Frontend: botón "Desbloquear" + botón "Simular pago" (dev). El desbloqueo se guarda en `localStorage`, **namespacado por `usuario_id`** (decodificado del JWT) para que dos cuentas en el mismo navegador no compartan el estado.
- **Nunca se ha completado un checkout real en navegador** (ver sección 9 — sigue siendo cierto desde la primera sesión).
- **`is_pro` en el modelo `Usuario` existe pero nada lo actualiza todavía** — el desbloqueo de Plan Pro es 100% client-side (localStorage), no hay webhook de Stripe que confirme el pago y marque `is_pro=True` en la base de datos.

### 4.4 Tutor IA (RAG) — con OpenAI
- `_construir_documentos_diccionarios()` (RUTINAS_PRO + TECNICAS_ESTUDIO_PRO) + `_cargar_documentos_conocimiento()` (PDFs/TXT de `app/conocimiento/`, vía `PyPDFDirectoryLoader`/`DirectoryLoader`).
- Troceado con `RecursiveCharacterTextSplitter` (1000 chars, overlap 200), indexado en Chroma (en memoria, singleton lazy) con `OpenAIEmbeddings(model="text-embedding-3-small")`.
- Chat con `ChatOpenAI(model="gpt-4o-mini")`.
- **System prompt con regla de longitud estricta:** preguntas cerradas (plazos, fechas, requisitos puntuales) → una sola frase directa; respuestas largas **solo** si el usuario las pide explícitamente ("explícame", "resume"...), y en ese caso Markdown obligatorio (párrafos cortos, viñetas, negrita).
- Frontend renderiza la respuesta con `marked.parse()` + `DOMPurify.sanitize()` (nunca `innerHTML` sin sanear — verificado que neutraliza `<script>`/`onerror` de un intento de XSS).
- **Migración de proveedor:** el proyecto pasó por Gemini (`langchain-google-genai`) y **volvió a OpenAI** en esta misma sesión, a petición del usuario. `langchain-google-genai` fue desinstalado, cero referencias a Gemini quedan en el código.
- **Verificado end-to-end con clave real de OpenAI**, incluyendo el comportamiento de respuesta corta para preguntas cerradas.

### 4.5 Modo Enfoque (Pomodoro a pantalla completa)
- Botón "Activar Modo Enfoque" en el sidebar → pantalla negro absoluto (`#pantalla-enfoque`, hijo directo de `<body>`, oculta todo lo demás vía `body.modo-enfoque-activo > *:not(#pantalla-enfoque)`).
- Temporizador: "Iniciar", "Pausar", "Trabajo (25 min)", "Descanso (5 min)" — cambia `tiempoRestante` entre 1500s/300s.
- Alarma sonora (`Audio` con URL de Pixabay) + toast al llegar a cero (ya no usa `alert()`, se cambió a `mostrarToast()` para no bloquear el hilo).
- **Sin persistencia**: no hay ningún endpoint de backend para el Pomodoro. El comentario `// Aqui en el futuro avisaremos al backend para guardar la racha` sigue ahí, sin implementar.
- **Verificado en navegador real**: ciclo completo trabajo→descanso→trabajo, cuenta atrás real (no simulada), alarma reproduciéndose (`ended:true` confirmado), pausa/reinicio funcionando.

### 4.6 Despliegue (preparación, no ejecutado)
- `requirements.txt` con `gunicorn`, `psycopg2-binary`.
- `database.py` lee `DATABASE_URL`; si existe, usa Postgres (reescribe `postgres://`→`postgresql://`, `pool_pre_ping=True`); si no, SQLite local sin cambios.
- `backend/Procfile` listo.
- **El usuario ya tiene una instancia Postgres real en Render** (la URL vive en `backend/Internal Database URL.txt`, ver alerta de seguridad en sección 9) pero **`DATABASE_URL` no está puesto en el `.env` local** (es intencional: local sigue en SQLite) y **la app nunca se ha desplegado de verdad ni se ha probado contra ese Postgres real** — solo se verificó la lógica de `database.py` a nivel de motor (dialecto, reescritura de URL), sin conexión real, porque no hay Docker/Postgres local en este entorno de desarrollo.

---

## 5. Endpoints de la API (completo)

| Método | Ruta | Auth | Notas |
|---|---|---|---|
| POST | `/api/auth/registro` | No | Crea usuario, hashea password |
| POST | `/api/auth/login` | No | OAuth2 form (`username`=email), devuelve JWT (7 días) |
| GET | `/api/auth/google/login` | No | Redirige a Google |
| GET | `/api/auth/google/callback` | No | Redirige a `/?token=<jwt>` |
| POST | `/api/auth/olvido-password` | No | Mensaje genérico siempre; dispara webhook si procede |
| POST | `/api/auth/reset-password` | No (token propio) | Token de 15 min vía `?reset_token=` |
| POST | `/api/marcas` | Sí | Crea marca física del usuario actual |
| GET | `/api/marcas/historial` | Sí | **No consumido por el frontend** (ver sección 8) |
| POST | `/api/teorica` | Sí | Crea simulacro del usuario actual |
| GET | `/api/teorica/historial` | Sí | **No consumido por el frontend** |
| GET | `/api/dashboard/global` | Sí | Nota combinada + veredicto |
| GET | `/api/dashboard/evolucion` | Sí | Serie temporal para Chart.js |
| GET | `/api/pro/entrenamiento` | Sí | Rutina para el punto débil detectado |
| GET | `/api/pro/teorica` | Sí | Catálogo de técnicas de estudio |
| POST | `/api/pagos/checkout` | Sí | Sesión de Stripe Checkout |
| POST | `/api/pro/chat` | Sí | Tutor IA (RAG + OpenAI) |

---

## 6. Estado exacto de modelos y esquemas

### 6.1 Modelos SQLAlchemy (`app/models/`)

```python
# usuario.py
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_pro = Column(Boolean, nullable=False, default=False)          # nunca se pone a True desde ningun endpoint
    fecha_registro = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    marcas_fisicas = relationship("MarcaFisica", back_populates="usuario", cascade="all, delete-orphan")
    simulacros_teoricos = relationship("SimulacroTeorico", back_populates="usuario", cascade="all, delete-orphan")

# marca.py
class MarcaFisica(Base):
    __tablename__ = "marcas_fisicas"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    dominadas = Column(Integer, nullable=False)          # repeticiones
    sprint_100m = Column(Float, nullable=False)          # segundos
    carrera_1500m = Column(Integer, nullable=False)      # segundos totales
    natacion_100m = Column(Integer, nullable=False)      # segundos totales
    usuario = relationship("Usuario", back_populates="marcas_fisicas")

# simulacro.py
class SimulacroTeorico(Base):
    __tablename__ = "simulacros_teoricos"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    aciertos = Column(Integer, nullable=False)
    fallos = Column(Integer, nullable=False)
    blancos = Column(Integer, nullable=False)
    nota_calculada = Column(Float, nullable=False)       # se persiste ya calculada (a diferencia de MarcaFisica)
    usuario = relationship("Usuario", back_populates="simulacros_teoricos")
```

**No existe ningún modelo `WorkoutLog` ni archivo `models.py` plano.** `app/models/` es un paquete (con `__init__.py` vacío), no un módulo único — así se decidió deliberadamente en la sesión donde se añadió multi-tenancy, para no romper la convención ya existente.

### 6.2 Esquemas Pydantic (`app/schemas.py`, completo)

```python
class UsuarioCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)      # NO usa EmailStr (evita dependencia extra email-validator)
    password: str = Field(min_length=8, max_length=128)

class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    is_pro: bool
    fecha_registro: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MarcaFisicaCreate(BaseModel):
    fecha: date | None = Field(default=None)
    dominadas: int = Field(ge=0)
    sprint_100m: float = Field(gt=0)
    carrera_1500m: int = Field(gt=0)
    natacion_100m: int = Field(gt=0)

class MarcaFisicaOut(BaseModel):          # from_attributes=True
    id: int; fecha: date; dominadas: int; sprint_100m: float; carrera_1500m: int; natacion_100m: int

class MarcaFisicaCalculada(BaseModel):
    marca: MarcaFisicaOut; detalle: dict; nota_global: float; recomendacion: dict | None

class SimulacroTeoricoCreate(BaseModel):
    fecha: date | None = Field(default=None)
    aciertos: int = Field(ge=0); fallos: int = Field(ge=0); blancos: int = Field(ge=0)

class SimulacroTeoricoOut(BaseModel):      # from_attributes=True
    id: int; fecha: date; aciertos: int; fallos: int; blancos: int; nota_calculada: float

class SimulacroTeoricoCalculado(BaseModel):
    simulacro: SimulacroTeoricoOut; nota_calculada: float

class DashboardGlobal(BaseModel):
    nota_fisica: dict | None; nota_teorica: dict | None; nota_global_combinada: float | None; veredicto: str
```

Nota: `OlvidoPasswordIn` y `ResetPasswordIn` **no** viven en `schemas.py` — están definidos directamente dentro de `routers/auth.py` (inconsistencia menor de estilo, no es un bug).

### 6.3 Migraciones de esquema
No hay Alembic ni ninguna herramienta de migraciones. Cuando se añadió `usuario_id` (FK NOT NULL) a `MarcaFisica`/`SimulacroTeorico`, la BD SQLite existente con datos antiguos (7 marcas, 5 simulacros sin usuario_id) se **renombró a backup** (`oposiciones.db.pre-auth-migration.bak`) y se dejó que `Base.metadata.create_all()` regenerara una BD vacía con el esquema nuevo. **Si se necesita otro cambio de esquema en el futuro (incluida la migración a Postgres en Render), el mismo problema se repetirá**: no hay migraciones incrementales, solo creación de tablas si no existen. Considerar introducir Alembic antes de que la BD de producción tenga datos reales de usuarios.

### 6.4 `database.py` — SQLite vs Postgres
Decidido por la presencia de `DATABASE_URL` en el entorno (ver sección 2). En local (sin esa variable) sigue usando `oposiciones.db` en la raíz del proyecto, con ruta absoluta calculada desde `__file__` (inmune al cwd de arranque).

---

## 7. Variables de entorno (`backend/.env`)

Todas están **rellenas con valores reales** ahora mismo (no se reproducen aquí por seguridad, ya están en el `.env` real):

| Variable | Estado | Notas |
|---|---|---|
| `STRIPE_SECRET_KEY` | ✅ rellena (test) | |
| `OPENAI_API_KEY` | ✅ rellena (real) | Migrado desde `GEMINI_API_KEY`, que ya no existe |
| `SECRET_KEY` | ✅ generada | Firma JWT y tokens de reset; también usada como `secret_key` de `SessionMiddleware` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | ✅ rellenas (reales) | Nunca se ha probado el login de Google de extremo a extremo en navegador |
| `WEBHOOK_RECUPERACION_URL` | ✅ rellena | Apunta a `webhook.site` (herramienta de test) — **no es un servicio real de envío de emails**, hay que sustituirlo antes de producción |
| `DATABASE_URL` | ❌ no está en `.env` | Intencional: local sigue en SQLite. La URL real de Render vive en `backend/Internal Database URL.txt` (ver alerta de seguridad abajo) |

---

## 8. Huecos conocidos de producto (no son bugs, son features a medio construir)

1. Los endpoints `/api/marcas/historial` y `/api/teorica/historial` existen y funcionan, pero **el frontend nunca los consume** — solo se ve el último registro. Esto es así desde la primera versión del proyecto (documentado ya en el HANDOVER original).
2. El Modo Enfoque no persiste nada: ni la racha de sesiones completadas, ni el estado si recargas la página a mitad de una sesión.
3. `Usuario.is_pro` existe en el modelo pero **ningún endpoint lo actualiza nunca** — el desbloqueo de Plan Pro es puramente client-side (localStorage), no está atado a un pago real confirmado por Stripe.

---

## 9. Deuda técnica y pendientes conocidos (leer antes de desplegar)

1. **🔴 CRÍTICO — `DOMINIO_APP = "http://localhost:8000"` hardcodeado** en `routers/auth.py` y `routers/pagos.py`. Se usa para construir el redirect de Google OAuth, el link de recuperación de contraseña, y las `success_url`/`cancel_url` de Stripe. **Tal cual está, todo esto se romperá en cuanto se despliegue en Render** (los redirects seguirán apuntando a localhost). Hay que leerlo de una variable de entorno (p.ej. `DOMINIO_APP` o `FRONTEND_URL`) antes de desplegar.

2. **🔴 Archivo `backend/Internal Database URL.txt` con la URL real de Postgres de Render (con usuario y contraseña) en texto plano.** No está cubierto por `.gitignore` (solo cubre `.env`, `*.db*`, no `*.txt`). Si en algún momento se hace `git init` y se añade sin querer, la credencial de la BD de producción queda expuesta. Recomendación: mover ese valor a `DATABASE_URL` en Render (como variable de entorno del servicio, no en un archivo), y borrar el `.txt`.

3. **🟠 Nunca se ha desplegado realmente en Render ni probado contra el Postgres real.** Todo lo relacionado con la rama Postgres de `database.py` está verificado solo a nivel de motor SQLAlchemy (dialecto, reescritura de `postgres://`), sin una conexión real, porque este entorno de desarrollo no tiene Docker ni un Postgres accesible.

4. **🟠 Login con Google nunca completado en navegador real** — solo verificado estructuralmente (redirect a `accounts.google.com` se genera bien, pero con `client_id` vacío en el momento de la prueba). El usuario ya puso credenciales reales después.

5. **🟠 Checkout de Stripe nunca completado en navegador real** (arrastrado desde la primera sesión del proyecto).

6. **🟠 `WEBHOOK_RECUPERACION_URL` apunta a webhook.site**, una herramienta de testing que solo muestra las peticiones que le llegan — no envía ningún email de verdad. Hay que sustituirlo por un servicio real (Zapier, Make, n8n, o un backend propio de envío de correo) antes de que la recuperación de contraseña funcione de cara al usuario final.

7. **🟡 Sin Alembic / migraciones incrementales** — ver sección 6.3. Cada cambio de esquema no trivial implica borrar/recrear la BD. Aceptable en desarrollo, peligroso en cuanto haya usuarios reales en producción.

8. **🟡 `bcrypt==4.0.1` fijado explícitamente** en `requirements.txt` porque `passlib` 1.7.4 (sin mantenimiento desde 2020) rompe con `bcrypt>=4.1` (le falta el atributo `__about__` que passlib espera). Si en el futuro se actualiza `bcrypt` sin querer, el hashing de contraseñas empezará a fallar con un error confuso (`AttributeError: module 'bcrypt' has no attribute '__about__'`) — si pasa, es esto.

9. **🟡 Historial de migraciones del motor de IA dentro de esta misma sesión:** el proyecto pasó de "sin Tutor IA" → OpenAI (versión original) → Gemini (una sesión completa migrando todo) → OpenAI de nuevo (esta sesión, a petición explícita del usuario). El código actual es 100% OpenAI, sin rastro de Gemini, pero si ves referencias a Gemini en documentos viejos o en la memoria de otra sesión, ya no aplican.

10. **🟢 Menor:** contenido de `RUTINAS_PRO` con marcadores `[cite: 1135]` sin resolver (heredado de la sesión original, nunca limpiado).

11. **🟢 Menor — quirk del entorno de desarrollo:** el preview tool de Claude Code en esta máquina a veces resuelve el `launch.json` de otro proyecto (`inversiones web`) en el puerto 8000, y quedan procesos `python run.py` huérfanos ocupando puertos entre sesiones. Si el arranque falla por puerto ocupado, verificar con PowerShell (`Get-CimInstance Win32_Process`) que el PID es realmente un proceso huérfano de esta sesión antes de matarlo.

---

## 10. Tareas pendientes inmediatas (recomendadas, en orden de impacto)

El encargo original de esta sesión pedía "conectar el frontend para enviar los entrenamientos al backend" — **eso ya está hecho** para `MarcaFisica` (el formulario de la pestaña "Físico" ya hace `POST /api/marcas` correctamente, verificado muchas veces en esta sesión). Las tareas realmente pendientes, verificadas contra el código real, son:

1. **Sacar `DOMINIO_APP` a una variable de entorno** en `auth.py` y `pagos.py` antes de desplegar (bloqueante para producción, ver deuda técnica #1).
2. **Desplegar de verdad en Render** y probar contra el Postgres real (nunca hecho).
3. **Sustituir el webhook de recuperación de contraseña** por un servicio real de envío de emails (ahora mismo es webhook.site).
4. **Probar el login de Google de extremo a extremo** en un navegador real con las credenciales ya puestas.
5. **Decidir si merece la pena** conectar `Usuario.is_pro` a un webhook real de Stripe (`checkout.session.completed`) en vez de depender de `localStorage`, si el negocio requiere que el Plan Pro sea robusto ante manipulación del cliente.
6. Si se quiere la función de "guardar racha" del Pomodoro que ya está comentada en el código (`main.js`, dentro de `iniciarTimer()`), hace falta: un modelo nuevo (p.ej. `SesionEnfoque` con `usuario_id`, `fecha`, `duracion_minutos`), un endpoint `POST /api/pomodoro/sesion`, y la llamada correspondiente desde el frontend en el punto donde ya está el comentario.

---

## 11. Convenciones de código a seguir

- Sin acentos en identificadores/nombres de tabla/variables (Python); el contenido de texto (strings, docstrings) sí lleva tildes correctamente en UTF-8 — si se ven rotas en una consola de Windows, es el codepage de la terminal, no un bug real.
- Manejo de errores de SDKs externos: capturar la excepción base (`stripe.error.StripeError`, `openai.OpenAIError`, `authlib...OAuthError`, `httpx.HTTPError`), envolver en `HTTPException(502, ...)`. Nunca dejar que una excepción de un SDK externo tumbe el proceso.
- Inicialización perezosa para todo lo que dependa de una API key externa (Stripe, OpenAI) — nunca llamadas de red al importar un módulo.
- Todos los routers de datos filtran explícitamente por `usuario_id == current_user.id`; si se añade un router nuevo con datos por usuario, seguir el mismo patrón (`Depends(get_current_user)` + `.filter(Modelo.usuario_id == current_user.id)`).
- Nunca renderizar `innerHTML` con contenido generado por el LLM sin pasar por `DOMPurify.sanitize()` primero.
- `app/models/` es un paquete, no lo aplanes a un `models.py` único sin coordinarlo explícitamente — rompería todos los imports existentes (`from app.models.marca import MarcaFisica`, etc.).

---

## 12. Resumen para retomar en una frase

Tracker Analítico de Oposiciones es una app FastAPI + SQLite/Postgres + frontend vanilla con autenticación multi-tenant completa (JWT + Google + recuperación de contraseña), un dashboard gratuito de rendimiento físico/teórico, un Plan Pro de pago con Stripe (checkout nunca probado en real) que incluye un Tutor IA con RAG sobre OpenAI (`gpt-4o-mini` + `text-embedding-3-small`, ya migrado de vuelta desde Gemini) y un Modo Enfoque Pomodoro sin persistencia — **preparada mecánicamente para desplegar en Render (Postgres + gunicorn) pero nunca desplegada de verdad**, y con `DOMINIO_APP` hardcodeado a `localhost` como el bloqueante más urgente antes de poder hacerlo.
