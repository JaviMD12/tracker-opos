← [handover.md](../../handover.md)

# 1. Stack y arquitectura

## Backend
- Python 3.14, **FastAPI** sobre **Uvicorn** (`--reload` en dev; en producción corre **sin** `--reload`, como servicio systemd — ver Infraestructura).
- **SQLAlchemy 2.x** — SQLite en local, **PostgreSQL real en producción** (Hostinger VPS, no Render — ver Infraestructura), decidido automáticamente por `DATABASE_URL` (ver `backend/app/database.py`).
- **Pydantic 2.x** para validación (`backend/app/schemas.py`, un único archivo con todos los schemas).
- **JWT** (`python-jose`) + **bcrypt** (`passlib`, `bcrypt==4.0.1` fijado — ver [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md)).
- **Authlib** (Google OAuth2/OIDC), **itsdangerous** (tokens de reset de 15 min), **Stripe** (`>=15.0`, checkout + webhook reales, **modo test**, verificado de extremo a extremo con un pago real de prueba — ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md)).
- **LangChain 1.x** + `langchain-google-genai` + `google-genai` + `langchain-chroma` + `langchain-community` + `chromadb` + `pypdf` — motor RAG del Tutor IA (ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md)). **Ya no hay `langchain-openai`, `openai` ni `tiktoken`** — el proyecto migró de OpenAI a Gemini por completo (chat, embeddings, scraper), ver más abajo.
- **feedparser** + **requests** + **beautifulsoup4** — scraper de boletines oficiales (ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md)).
- **APScheduler** — cron del scraper.
- **Gemini** (Google AI Studio, `GOOGLE_API_KEY`): `gemini-2.5-flash` (chat/generación) + `models/gemini-embedding-001` (embeddings). **Ojo con el nombre exacto del modelo de embeddings**: `text-embedding-004` ya no existe para esta API/clave (404), y `gemini-embedding-1.0` a secas tampoco es el identificador correcto — es `models/gemini-embedding-001`.

## Frontend
- HTML + JavaScript vanilla (`frontend/js/main.js`, un único archivo sin build step, sin módulos ES).
- **Tailwind CSS** vía CDN + `frontend/css/style.css` para todo lo que Tailwind CDN no cubre.
- **Chart.js 4.4.4** (evolución de nota), **marked.js 12.0.2** + **DOMPurify 3.1.6** (Markdown del Tutor IA / plan de estudio, siempre sanitizado antes de `innerHTML`).
- Diseño dark mode, acento gradiente naranja→ámbar (`#F97316`/`#0F172A`/`#1E293B`).

## Infraestructura — **ya desplegado en producción real**, no es solo un plan
- **VPS de Hostinger** (`187.55.229.111`, hostname `srv1835603`), dominio público **`https://opotracker.tech`** (DNS ya apuntando ahí, verificado accesible). Código en `/var/www/tracker-opos`, venv en `/var/www/tracker-opos/venv`.
- Corre como **servicio systemd `tracker-opos.service`** (`uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers`, sin `--reload`), detrás de **nginx** como reverse proxy. **Cualquier cambio de código Python desplegado necesita `systemctl restart tracker-opos.service`** — los cambios de frontend (html/css/js) son estáticos y se sirven en caliente, no necesitan reinicio.
- `DATABASE_URL` **sí está configurada** en el `.env` del VPS → Postgres real en producción, confirmado (`engine.dialect.name == "postgresql"`). Local sigue en SQLite sin esa variable.
- Flujo de despliegue real, usado repetidamente: editar en local → `git push` a `https://github.com/JaviMD12/tracker-opos.git` (rama `main`) → por SSH en el VPS, `git pull` → reiniciar el servicio si hubo cambio de backend.
- **Acceso SSH al VPS no es persistente entre sesiones de Claude**: se genera un par de claves ed25519 dedicado en el scratchpad de cada sesión, y el usuario autoriza la clave pública en `~/.ssh/authorized_keys` desde su propia terminal. No hay contraseña de root guardada en ningún sitio.
- `backend/run.py`: wrapper que lee `PORT` y lanza uvicorn con reload (dev/local).
- `backend/Procfile`: sigue existiendo (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`) pero **no se usa** — el despliegue real es el VPS + systemd descrito arriba, no una plataforma tipo Render/Heroku que lea el Procfile.
- `.claude/launch.json`: preview tool de Claude Code en el puerto 5001 (`autoPort: true`). **Cuidado, esto sigue pasando**: el preview tool a veces resuelve el `launch.json` de *otro proyecto* (`inversiones web`, no relacionado) en el puerto 8000 en vez del de este proyecto. Si pasa, arrancar el backend manualmente: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port <puerto_libre>` y navegar ahí directamente.
- FastAPI sirve el frontend estático directamente vía `StaticFiles` montado en `/` (`backend/app/main.py`).
- **`DOMINIO_APP` ya NO está hardcodeado** — se lee de `os.environ.get("DOMINIO_APP", "https://opotracker.tech")` en `auth.py` y `pagos.py`, con ese mismo dominio real como fallback. Este pendiente del handover anterior ya está resuelto.

## Estructura de carpetas (backend, completa a fecha de este corte)

```
backend/
├── .env / .env.example
├── Procfile
├── requirements.txt
├── run.py
├── Internal Database URL.txt     # ⚠️ URL real de Postgres en texto plano, ver 07-deuda-tecnica-y-pendientes.md
├── chroma_db_data/                # índice de Chroma persistido (gitignored, ~120MB)
└── app/
    ├── main.py                    # crea la app, monta 10 routers, cron APScheduler, StaticFiles
    ├── database.py                # engine condicional SQLite/Postgres
    ├── schemas.py                 # todos los Pydantic, un solo archivo
    ├── models/                    # PAQUETE, no un models.py plano (ver 08-convenciones-de-codigo.md)
    │   ├── usuario.py             # Usuario (is_pro, relaciones a todo lo demás)
    │   ├── marca.py                # MarcaFisica
    │   ├── simulacro.py            # SimulacroTeorico (autoinforme manual, dashboard gratuito)
    │   ├── workout.py              # Workout (inactivo, ver 03-rendimiento-fisico-teorico.md)
    │   ├── sesion_estudio.py        # SesionEstudio (Pomodoro → heatmap)
    │   ├── convocatoria.py          # Convocatoria (Tablon Premium, scraper BOE/BOJA)
    │   ├── resultado_simulacro.py   # ResultadoSimulacro (notas de los examenes IA)
    │   └── pregunta_test.py         # PreguntaTest: banco precargado del Simulacro (ver 06-simulacros-ia.md), NO se genera en vivo por peticion
    ├── routers/
    │   ├── auth.py                  # registro, login, google, olvido/reset password
    │   ├── marcas.py                 # POST/GET /api/marcas
    │   ├── teorica.py                # POST/GET /api/teorica
    │   ├── dashboard.py               # /api/dashboard/global y /evolucion
    │   ├── pro.py                     # /api/pro/entrenamiento y /teorica (rutinas estaticas)
    │   ├── pagos.py                    # checkout + webhook real de Stripe (is_pro)
    │   ├── chat.py                      # /api/pro/chat (Tutor IA)
    │   ├── workouts.py                   # /api/workouts (inactivo desde frontend)
    │   ├── actividad.py                   # /api/actividad/heatmap y /sesion-estudio
    │   ├── convocatorias.py                # /api/convocatorias (Tablon Premium)
    │   ├── tutor.py                         # /api/tutor/analizar-plaza/{id} (plan de estudio IA)
    │   └── simulacros.py                     # /api/simulacros/generar y /guardar
    ├── services/
    │   ├── security.py                        # JWT, bcrypt, Authlib, tokens de reset
    │   ├── calculo.py                          # motor de puntuacion fisico/teorico
    │   ├── rutinas.py                           # RUTINAS_PRO y TECNICAS_ESTUDIO_PRO (estaticos)
    │   ├── ai_tutor.py                          # RAG: vectorstore, chat, plan de estudio, simulacros
    │   └── scraper_boletines.py                  # scraper BOE/BOJA + deep scraping + IA
    └── conocimiento/                              # ~20 PDFs/TXT de temario real + convocatorias
```

No listados arriba pero relevantes, en la raíz de `backend/`: **`generar_banco.py`** (genera preguntas del Simulacro con RAG, un tema a la vez, interactivo) y **`generar_banco_completo.py`** (idem pero los 6 temas de una sola vez, no interactivo — es el comando a correr tras ampliar `conocimiento/`, ver [06-simulacros-ia.md](06-simulacros-ia.md)) y **`purgar_preguntas.py`** (vacía la tabla `preguntas_test` antes de regenerar). Todos requieren `GOOGLE_API_KEY` en el `.env` del entorno donde se ejecuten (cargan su propio `load_dotenv()`, no dependen de que la app esté arrancada).

Ver [02](02-autenticacion-y-pagos.md) a [07](07-deuda-tecnica-y-pendientes.md) para el detalle de cada subsistema.
