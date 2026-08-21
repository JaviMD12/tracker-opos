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
- **slowapi** (`app/services/rate_limit.py`, añadido 2026-08-02) — rate limiting en `POST /api/pro/chat` (60 peticiones/hora, clave por usuario vía claim `sub` del JWT con fallback a IP) para blindar la cuota de Gemini frente a abuso. **Ampliado (2026-08-10)** al resto de rutas sensibles: `POST /api/tutor/analizar-plaza/{id}` (60/hora, misma clave), `POST /api/auth/login` (10/min), `/registro` (10/hora), `/olvido-password` (5/hora) y `POST /api/waitlist` (5/hora) + `.../export.csv` (20/hora). Ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md) y [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md).
- **Gemini** (Google AI Studio, `GOOGLE_API_KEY`): `gemini-2.5-flash` (chat/generación) + `models/gemini-embedding-001` (embeddings). **Ojo con el nombre exacto del modelo de embeddings**: `text-embedding-004` ya no existe para esta API/clave (404), y `gemini-embedding-1.0` a secas tampoco es el identificador correcto — es `models/gemini-embedding-001`.
- **Auditoría de seguridad completa (2026-08-10, `app/main.py`)**: `CORSMiddleware` restringido a `DOMINIO_APP` (nunca `"*"`, con `.rstrip("/")` — bug real encontrado: `DOMINIO_APP` lleva barra final en su otro uso y un origen CORS nunca la lleva, sin el strip el navegador jamás recibía `Access-Control-Allow-Origin` ni para el dominio real); `SECRET_KEY` ahora falla al arrancar si no existe o mide menos de 32 caracteres (`services/security.py`); límite de payload de 2MB (`LimiteTamanoBody`, `Content-Length`, defensa en profundidad sobre el `client_max_body_size` de nginx); cabeceras `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`/`Permissions-Policy`/`Strict-Transport-Security` y una `Content-Security-Policy` calculada a mano revisando qué carga de verdad el frontend (no una plantilla genérica — encontró que la alarma del Pomodoro carga un MP3 de `cdn.pixabay.com`, que Plausible necesita `connect-src` además de `script-src`, y que Tailwind CDN obliga a `style-src 'unsafe-inline'` por inyectar su `<style>` compilado en el propio navegador).

## Frontend
- HTML + JavaScript vanilla (`frontend/js/main.js`, un único archivo sin build step, sin módulos ES).
- **Tailwind CSS** vía CDN + `frontend/css/style.css` para todo lo que Tailwind CDN no cubre. **Ojo (2026-08-10)**: el CDN "Play" de Tailwind **no garantiza** que una variante responsive (`lg:flex`) gane el cascade sobre una utilidad base (`hidden`) en el mismo elemento — a diferencia del build normal de Tailwind. Bug real: el menú móvil del sidebar (`hidden lg:flex`) dejaba el sidebar completo invisible en escritorio. Ver [08-convenciones-de-codigo.md](08-convenciones-de-codigo.md).
- **Chart.js 4.4.4** (evolución de nota), **marked.js 12.0.2** + **DOMPurify 3.1.6** (Markdown del Tutor IA / plan de estudio, siempre sanitizado antes de `innerHTML`).
- **Plausible** (`plausible.io/js/script.js`, añadido 2026-08-09) — analítica de visitas sin cookies. Requiere dar de alta `opotracker.tech` en el dashboard de Plausible; sin eso el script carga pero no hay ningún sitio registrado que reciba los datos.
- Diseño dark mode, acento gradiente naranja→ámbar (`#F97316`/`#0F172A`/`#1E293B`).

## Infraestructura — **ya desplegado en producción real**, no es solo un plan
- **VPS de Hostinger** (`187.55.229.111`, hostname `srv1835603`), dominio público **`https://opotracker.tech`** (DNS ya apuntando ahí, verificado accesible). Código en `/var/www/tracker-opos`, venv en `/var/www/tracker-opos/venv`.
- Corre como **servicio systemd `tracker-opos.service`** (`uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers`, sin `--reload`), detrás de **nginx** como reverse proxy. **Cualquier cambio de código Python desplegado necesita `systemctl restart tracker-opos.service`** — los cambios de frontend (html/css/js) son estáticos y se sirven en caliente, no necesitan reinicio.
- `DATABASE_URL` **sí está configurada** en el `.env` del VPS → Postgres real en producción, confirmado (`engine.dialect.name == "postgresql"`). Local sigue en SQLite sin esa variable.
- Flujo de despliegue real, usado repetidamente: editar en local → `git push` a `https://github.com/JaviMD12/tracker-opos.git` (rama `main`) → por SSH en el VPS, `git pull` → reiniciar el servicio si hubo cambio de backend.
- **Acceso SSH al VPS no es persistente entre sesiones de Claude**: se genera un par de claves ed25519 dedicado en el scratchpad de cada sesión, y el usuario autoriza la clave pública en `~/.ssh/authorized_keys` desde su propia terminal. No hay contraseña de root guardada en ningún sitio.
- **Swap añadido (2026-08-16): `/swapfile_claude_temp`, 4GB, activo de forma permanente (decisión del usuario).** El VPS solo tiene 3,8GB de RAM y no traía swap configurado de fábrica — un rebuild del índice de Chroma con el volumen de contenido actual (ver [04](04-tutor-ia-y-rag.md)) llega a picos de ~3,5GB+ y el kernel mató el proceso por OOM dos veces seguidas antes de añadir este swap (confirmado con `dmesg`, `Out of memory: Killed process`). El nombre `_claude_temp` es historico (se creó pensando en quitarlo después), pero el usuario decidió explícitamente dejarlo activo como red de seguridad permanente — no asumir que hay que borrarlo en sesiones futuras solo por el nombre.
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
    ├── main.py                    # crea la app, monta 16 routers, cron APScheduler, StaticFiles
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
    │   ├── pregunta_test.py         # PreguntaTest: banco precargado del Simulacro (ver 06-simulacros-ia.md), NO se genera en vivo por peticion
    │   ├── flashcard.py              # Flashcard: banco precargado de tarjetas Q/A (ver 10-flashcards-y-provincia.md)
    │   └── progreso_flashcard.py     # ProgresoFlashcard: intervalo_dias/facilidad/fecha_proximo_repaso por usuario (SRS)
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
    │   ├── simulacros.py                     # /api/simulacros/generar y /guardar
    │   ├── flashcards.py                      # /api/flashcards/due y /review (ver 10-flashcards-y-provincia.md)
    │   ├── contacto.py                        # /api/contacto/enviar (soporte/sugerencias, trato Premium/Gratuito distinto)
    │   ├── usuarios.py                         # /api/usuarios/me
    │   └── waitlist.py                          # /api/waitlist + /export.csv (nuevo 2026-08-10, ver 02-autenticacion-y-pagos.md)
    ├── services/
    │   ├── security.py                        # JWT, bcrypt, Authlib, tokens de reset
    │   ├── calculo.py                          # motor de puntuacion fisico/teorico
    │   ├── rutinas.py                           # RUTINAS_PRO y TECNICAS_ESTUDIO_PRO (estaticos)
    │   ├── ai_tutor.py                          # RAG: vectorstore, chat, plan de estudio, simulacros
    │   ├── scraper_boletines.py                  # scraper BOE/BOJA + deep scraping + IA
    │   ├── rate_limit.py                          # limiter de slowapi (import aislado para evitar ciclo main.py<->chat.py)
    │   └── srs.py                                  # algoritmo de repeticion espaciada (SM-2 simplificado) de Flashcards
    └── conocimiento/                              # 73 archivos reales (.pdf/.docx/.xlsx/.txt) de temario, convocatorias y contenido de la provincia de Huelva -- conteo verificado el 2026-08-21 tras eliminar 11 duplicados, ver 10-flashcards-y-provincia.md
```

Modelo nuevo: **`models/waitlist.py`** (`Waitlist`: email único + fecha_registro, sin FK a `Usuario` a propósito — no exige cuenta para apuntarse). Ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md).

No listados arriba pero relevantes, en la raíz de `backend/`: **`generar_banco.py`** (genera preguntas del Simulacro con RAG, un tema a la vez, interactivo) y **`generar_banco_completo.py`** (idem pero los 7 temas de una sola vez, no interactivo — es el comando a correr tras ampliar `conocimiento/`, ver [06-simulacros-ia.md](06-simulacros-ia.md)) y **`purgar_preguntas.py`** (vacía la tabla `preguntas_test` antes de regenerar). Todos requieren `GOOGLE_API_KEY` en el `.env` del entorno donde se ejecuten (cargan su propio `load_dotenv()`, no dependen de que la app esté arrancada). **`generar_flashcards.py`** (nuevo, 2026-08-21): mismo patrón que `generar_banco_completo.py` pero para la tabla `flashcards` — reutiliza `TEMA_A_ARCHIVOS`/`TEMAS_CONOCIDOS`/`ENFOQUES_ROTATORIOS` de `generar_banco.py`, ver [10-flashcards-y-provincia.md](10-flashcards-y-provincia.md).

**`buffer_tool.py`** (marketing, no forma parte de la app en sí): programa tuits/hilos reales en la cuenta de X `opotracker` vía la API GraphQL de Buffer (`api.buffer.com`, requiere `BUFFER_ACCESS_TOKEN` en `.env`). Comandos: `listar` (canales), `publicar`/`programar` (un tuit suelto) y `programar_hilo` (tuit + réplicas encadenadas como hilo real, vía `metadata.twitter.thread`). Ver el punto 36 de [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md) para el histórico de hilos ya programados.

Ver [02](02-autenticacion-y-pagos.md) a [07](07-deuda-tecnica-y-pendientes.md) para el detalle de cada subsistema.
