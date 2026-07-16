← [handover.md](../../handover.md)

# 1. Stack y arquitectura

## Backend
- Python 3.14, **FastAPI** sobre **Uvicorn** (`--reload` en dev; `gunicorn`/`uvicorn` listos para producción vía `Procfile`).
- **SQLAlchemy 2.x** — SQLite en local, PostgreSQL en producción (Render), decidido automáticamente por `DATABASE_URL` (ver `backend/app/database.py`).
- **Pydantic 2.x** para validación (`backend/app/schemas.py`, un único archivo con todos los schemas).
- **JWT** (`python-jose`) + **bcrypt** (`passlib`, `bcrypt==4.0.1` fijado — ver [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md)).
- **Authlib** (Google OAuth2/OIDC), **itsdangerous** (tokens de reset de 15 min), **Stripe** (`>=15.0`, checkout + webhook reales).
- **LangChain 1.x** + `langchain-openai` + `langchain-chroma` + `langchain-community` + `chromadb` + `tiktoken` + `pypdf` — motor RAG del Tutor IA (ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md)).
- **feedparser** + **requests** + **beautifulsoup4** — scraper de boletines oficiales (ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md)).
- **APScheduler** — cron del scraper (03:00 Madrid).
- **OpenAI**: `gpt-4o-mini` (chat/generación) + `text-embedding-3-small` (embeddings).

## Frontend
- HTML + JavaScript vanilla (`frontend/js/main.js`, un único archivo sin build step, sin módulos ES).
- **Tailwind CSS** vía CDN + `frontend/css/style.css` para todo lo que Tailwind CDN no cubre.
- **Chart.js 4.4.4** (evolución de nota), **marked.js 12.0.2** + **DOMPurify 3.1.6** (Markdown del Tutor IA / plan de estudio, siempre sanitizado antes de `innerHTML`).
- Diseño dark mode, acento gradiente naranja→ámbar (`#F97316`/`#0F172A`/`#1E293B`).

## Infraestructura
- `backend/run.py`: wrapper que lee `PORT` y lanza uvicorn con reload.
- `backend/Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Render).
- `.claude/launch.json`: preview tool de Claude Code en el puerto 5001 (`autoPort: true`). **Cuidado**: en este entorno, el preview tool a veces deja procesos huérfanos de sesiones anteriores; si el arranque falla por puerto ocupado, verificar con `Get-CimInstance Win32_Process` antes de matar nada.
- FastAPI sirve el frontend estático directamente vía `StaticFiles` montado en `/` (`backend/app/main.py`).
- **`DOMINIO_APP = "http://localhost:8000"` sigue hardcodeado** en `auth.py`/`pagos.py` — bloqueante crítico antes de desplegar, ver [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md).

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
    │   └── resultado_simulacro.py   # ResultadoSimulacro (notas de los examenes IA)
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

Ver [02](02-autenticacion-y-pagos.md) a [07](07-deuda-tecnica-y-pendientes.md) para el detalle de cada subsistema.
