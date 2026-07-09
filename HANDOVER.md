# Documento de Estado del Proyecto — Tracker Analítico de Oposiciones

**Fecha del corte:** 2026-07-07
**Propósito de este documento:** handover completo para retomar el proyecto en una sesión nueva sin contexto previo. Todo lo descrito aquí ha sido verificado contra el código real en disco (no es un resumen de memoria).

**Corrección importante sobre el encargo original:** se pidió documentar "la tarea en la que nos quedamos" como *"vamos a implementar un sistema RAG con LangChain, ChromaDB y OpenAI"*. Eso ya no es exacto: **el sistema RAG está completamente implementado** (backend + frontend, código escrito y verificado estructuralmente). Lo que queda pendiente no es implementarlo, sino **verificarlo con una clave real de OpenAI y en un navegador real** (ver sección 8). Este documento refleja el estado real, no la petición original.

---

## 1. Stack tecnológico completo

**Backend:**
- Python 3.14, **FastAPI** (`fastapi>=0.110`) sobre **Uvicorn** (`uvicorn[standard]>=0.29`, con `--reload`)
- **SQLAlchemy** (`>=2.0`) + **SQLite** como base de datos (`sqlite:///./oposiciones.db`)
- **Pydantic** (`>=2.6`) para validación de esquemas
- **Stripe** (`>=15.0`) — Checkout en modo test
- **LangChain** (`>=1.3`, arquitectura nueva v1.x) + **langchain-openai** (`>=1.3`) + **langchain-chroma** (`>=1.1`) + **chromadb** (`>=1.5`) + **tiktoken** (`>=0.8`) — motor RAG del Tutor IA
- Modelo de OpenAI usado: `gpt-4o-mini` (chat) + `OpenAIEmbeddings` (embeddings, modelo por defecto de langchain-openai)

**Frontend:**
- HTML + JavaScript vanilla (sin build step, sin framework)
- **Tailwind CSS** vía CDN (`https://cdn.tailwindcss.com`)
- **Chart.js 4.4.4** vía CDN (`https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js`) para la gráfica de evolución
- CSS custom en `frontend/css/style.css` para todo lo que Tailwind CDN no cubre sin configuración JIT (clases con estado `.active`, badges, timeline, chat, toasts)
- Diseño: **dark mode** (`bg-gray-950`), acento en gradiente naranja→ámbar (`from-orange-600 to-amber-500`), tipografía del sistema

**Infraestructura de desarrollo:**
- `backend/run.py`: wrapper que lee `PORT` de entorno (default 8000) y lanza `uvicorn.run("app.main:app", ..., reload=True)`
- `.claude/launch.json`: config del preview tool de Claude Code (nombre `oposiciones-api`, puerto 5001, `autoPort: true`)
- FastAPI sirve el frontend estático directamente vía `StaticFiles` montado en `/` (no hay servidor de frontend separado)

---

## 2. Estructura de carpetas y archivos

```
tracker-oposiciones/
├── .claude/
│   └── launch.json                  # config del preview tool
├── oposiciones.db                   # ⚠️ BD SQLite REAL/CANÓNICA (ver sección 9, punto crítico)
├── HANDOVER.md                      # este documento
├── backend/
│   ├── requirements.txt
│   ├── run.py                       # entrypoint: uvicorn con PORT de entorno
│   ├── oposiciones.db               # ⚠️ BD SQLite DUPLICADA/OBSOLETA (ver sección 9)
│   └── app/
│       ├── __init__.py
│       ├── main.py                  # crea la app FastAPI, registra 6 routers, monta el frontend
│       ├── database.py              # engine SQLAlchemy, SessionLocal, Base, get_db()
│       ├── schemas.py                # Pydantic: MarcaFisica*, SimulacroTeorico*, DashboardGlobal
│       ├── models/
│       │   ├── __init__.py
│       │   ├── marca.py             # modelo SQLAlchemy MarcaFisica
│       │   └── simulacro.py         # modelo SQLAlchemy SimulacroTeorico
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── marcas.py            # POST/GET /api/marcas
│       │   ├── teorica.py           # POST/GET /api/teorica
│       │   ├── dashboard.py         # GET /api/dashboard/global y /evolucion
│       │   ├── pro.py               # GET /api/pro/entrenamiento y /teorica
│       │   ├── pagos.py             # POST /api/pagos/checkout (Stripe)
│       │   └── chat.py              # POST /api/pro/chat (Tutor IA / RAG)
│       └── services/
│           ├── __init__.py
│           ├── calculo.py           # motor de puntuación físico/teórico (interpolación lineal)
│           ├── rutinas.py           # diccionarios RUTINAS_PRO y TECNICAS_ESTUDIO_PRO (datos estáticos)
│           └── ai_tutor.py          # motor RAG: Chroma + OpenAIEmbeddings + ChatOpenAI
└── frontend/
    ├── index.html                   # SPA de una sola página, 3 vistas (dashboard/guía/pro)
    ├── css/
    │   └── style.css                # ~410 líneas, todo el CSS custom del proyecto
    └── js/
        └── main.js                  # ~550 líneas, toda la lógica del frontend (sin módulos, un solo archivo)
```

**Nota:** no es un repositorio git (`git status` confirma "no es repo git", sin `.gitignore`). Esto es relevante para la sección 9 (hay una clave secreta de Stripe hardcodeada en el código).

---

## 3. Cómo arrancar el proyecto

```bash
cd tracker-oposiciones/backend
pip install -r requirements.txt
python run.py
```

Sirve en `http://localhost:8000/` (o el puerto que indique `$PORT`). El frontend se sirve como estático desde el mismo proceso FastAPI — no hace falta levantar nada aparte.

**IMPORTANTE:** arrancar siempre con `python run.py` desde `backend/`, o con `python backend/run.py` desde la raíz del proyecto — **nunca** con `uvicorn app.main:app` ejecutado con cwd dentro de `backend/` sin pasar por `run.py`, porque la ruta de la base de datos (`sqlite:///./oposiciones.db`) es relativa al directorio de trabajo y esto crea un segundo archivo de base de datos divergente (ver sección 9).

---

## 4. Funcionalidades core implementadas y verificadas

Todo lo siguiente está **implementado, probado (por curl y/o navegador) y funcionando**:

### 4.1 Cálculo de marcas físicas (escala /10)
- 4 pruebas: dominadas, sprint 100m, carrera 1500m, natación 100m.
- Interpolación lineal por prueba: el mínimo exigido puntúa 5, el máximo puntúa 10, por debajo del mínimo puntúa 0. Nunca se superan los 10 puntos por prueba.
- **La nota global física es el PROMEDIO de las 4 pruebas (escala 0-10)**, no la suma (esto cambió respecto a una versión anterior que sumaba sobre 40 — ya migrado en todo el código, backend y frontend).
- Motor de recomendación: identifica la prueba donde es "más barato" (menor esfuerzo relativo a la marca actual) ganar el siguiente punto entero.

### 4.2 Simulacro teórico
- Fórmula: `(aciertos - fallos/3) / total_preguntas * 10`, clampeada a `[0, 10]`. `total_preguntas` por defecto 100.

### 4.3 Dashboard combinado / Analista Estratégico Global
- `GET /api/dashboard/global`: combina la última marca física y el último simulacro teórico (50%/50%, ambos ya sobre 10), calcula un "veredicto del entrenador" comparando qué porcentaje de su máximo tiene cada bloque.
- `GET /api/dashboard/evolucion`: serie temporal de la nota global combinada a lo largo de las fechas registradas (algoritmo de "arrastre" del último valor conocido de cada bloque, fecha a fecha, solo emite puntos una vez que ambos bloques tienen al menos un dato).
- El frontend pinta esto con **Chart.js** (gráfica de línea, tema oscuro, eje Y fijo 0-10) dentro de la pestaña Plan Pro.

### 4.4 Guía del Opositor (contenido estático informativo, gratis)
- 3 tarjetas: Requisitos Mínimos (edad, titulación, acreditaciones — contenido oficial verificado), Permisos de Conducir (B/C/C+E), Fuentes del Temario (enlaces reales al BOE, verificados uno a uno con curl).

### 4.5 Plan Pro — muro de pago con Stripe (modo test)
- `POST /api/pagos/checkout` crea una `stripe.checkout.Session` (modo `payment`, producto "Plan Pro - Tracker Oposiciones", 999 céntimos EUR), `success_url`/`cancel_url` apuntan a `http://localhost:8000/?pago=exito` / `?pago=cancelado`.
- **`stripe.api_key` en `backend/app/routers/pagos.py` YA TIENE UNA CLAVE DE TEST REAL configurada** (no un placeholder) — puesta directamente por el usuario en el código fuente. **No se reproduce aquí por seguridad.** Punto pendiente crítico: ver sección 9.
- Frontend: botón "Desbloquear por 9,99€" → fetch al endpoint → redirect a `data.url` (URL de Stripe). Al volver, `main.js` lee `?pago=exito|cancelado`, desbloquea el Plan Pro en `localStorage` (clave `plan_pro_desbloqueado`), limpia la URL con `history.replaceState`, y muestra un toast.
- Además existe un botón "Simular pago (solo desarrollo)" que desbloquea directamente sin pasar por Stripe, para poder probar el resto del Plan Pro sin gastar una sesión de Stripe real.
- **Nunca se ha completado un checkout real de Stripe en navegador** (bloqueo de entorno todo el turno en que se implementó, ver sección 9). El manejo de errores sí está verificado: con clave inválida el endpoint devuelve 502 con detalle claro.

### 4.6 Carga dinámica de rutinas y técnicas de estudio
- `GET /api/pro/entrenamiento`: toma la última marca física, calcula las 4 puntuaciones, detecta la prueba con menor puntuación (`min(detalle, key=...)`), y devuelve la rutina completa de `RUTINAS_PRO` para esa prueba (ver formato exacto en sección 5).
- `GET /api/pro/teorica`: devuelve las 4 técnicas de estudio de `TECNICAS_ESTUDIO_PRO` (lista completa, sin lógica de selección).
- El frontend consume ambos y renderiza: timeline vertical numerado con badges de intensidad/volumen + bloque "💡 Por qué funciona" (fundamento fisiológico, fondo azul) para la rutina física; tarjetas anchas con pasos y un bloque "Ejemplo aplicado al temario" (fondo degradado ámbar) para las técnicas de estudio.

---

## 5. Formato exacto de la base de datos y los diccionarios

### 5.1 Modelos SQLAlchemy (tablas SQLite)

```python
# app/models/marca.py
class MarcaFisica(Base):
    __tablename__ = "marcas_fisicas"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    dominadas = Column(Integer, nullable=False)          # repeticiones
    sprint_100m = Column(Float, nullable=False)          # segundos (con decimales)
    carrera_1500m = Column(Integer, nullable=False)      # segundos totales
    natacion_100m = Column(Integer, nullable=False)      # segundos totales

# app/models/simulacro.py
class SimulacroTeorico(Base):
    __tablename__ = "simulacros_teoricos"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    aciertos = Column(Integer, nullable=False)
    fallos = Column(Integer, nullable=False)
    blancos = Column(Integer, nullable=False)
    nota_calculada = Column(Float, nullable=False)       # ya calculada y persistida (a diferencia de MarcaFisica)
```

**Importante:** `MarcaFisica` **no persiste la nota calculada** — se recalcula al vuelo en cada endpoint que la necesita, llamando a `calcular_puntuacion_completa()` desde `services/calculo.py`. `SimulacroTeorico` sí persiste `nota_calculada` directamente en la tabla.

### 5.2 `RUTINAS_PRO` (`app/services/rutinas.py`)

Diccionario con 4 claves fijas: `"dominadas"`, `"sprint_100m"`, `"carrera_1500m"`, `"natacion_100m"` (deben coincidir exactamente con las claves de `PRUEBAS` en `calculo.py`, ya que `pro.py` indexa `RUTINAS_PRO[prueba_debil]` con la clave devuelta por el motor de cálculo). Cada valor tiene esta forma exacta:

```python
{
    "titulo": str,                      # título de la rutina
    "descripcion_cientifica": str,      # 2-3 frases de fundamento científico general
    "entrenamiento_semanal": [          # lista de 3 fases (siempre 3 en las 4 rutinas actuales)
        {
            "fase": str,                # nombre de la fase
            "intensidad": str,          # ej. "Alta (25-50% Vdec)"
            "volumen": str,             # ej. "3-6 series x 3-5 reps"
            "detalle": str,             # qué hacer exactamente
            "fundamento": str,          # POR QUÉ funciona esa fase concreta (fisiología)
        },
        # ... 2 fases más
    ],
    "bibliografia": str,   # UNA sola string con referencias separadas por "; " (no es lista)
}
```

**Nota de contenido:** los textos incluyen marcadores `[cite: 1135]` etc. sin resolver (residuo de un documento de origen pegado por el usuario). Es contenido real y currentemente en uso — no se ha limpiado, se ha respetado tal cual porque el usuario los introdujo deliberadamente. Si se quiere pulir para producción, habría que sustituir esos marcadores por citas reales o quitarlos.

El frontend (`main.js`, función `cargarEntrenamientoEspecifico`) hace `rutina.bibliografia.split(/;\s*/)` para convertir esa string en una lista de tarjetas — **si se cambia `bibliografia` a una lista real, hay que actualizar ese `.split()`**.

### 5.3 `TECNICAS_ESTUDIO_PRO` (mismo archivo)

Diccionario con 4 claves: `"recuerdo_activo"`, `"repeticion_espaciada"`, `"tecnica_feynman"`, `"practica_intercalada"`. Cada valor:

```python
{
    "nombre": str,                  # ej. "Recuerdo Activo (Active Recall)"
    "concepto_cientifico": str,     # fundamento en neurociencia cognitiva
    "paso_a_paso": [str, str, ...], # lista de pasos (actualmente 4 pasos en las 4 técnicas)
    "ejemplo_aplicado": str,        # SIEMPRE centrado en la oposición de bombero (Ley de
                                     # Gestión de Emergencias de Andalucía, hidráulica,
                                     # comportamiento del fuego — nunca genérico)
}
```

El endpoint `GET /api/pro/teorica` devuelve `{"tecnicas": list(TECNICAS_ESTUDIO_PRO.values())}` — es decir, **una lista**, no el diccionario con sus claves internas.

---

## 6. Endpoints de la API (completo)

| Método | Ruta | Body / Query | Devuelve | Notas |
|---|---|---|---|---|
| POST | `/api/marcas` | `MarcaFisicaCreate` (fecha?, dominadas, sprint_100m, carrera_1500m, natacion_100m) | marca guardada + detalle + `nota_global` (0-10) + recomendación | |
| GET | `/api/marcas/historial` | — | lista de marcas ordenadas por fecha desc | |
| POST | `/api/teorica` | `SimulacroTeoricoCreate` (fecha?, aciertos, fallos, blancos) | simulacro guardado + `nota_calculada` | |
| GET | `/api/teorica/historial` | — | lista de simulacros ordenados por fecha desc | |
| GET | `/api/dashboard/global` | — | `nota_fisica`, `nota_teorica`, `nota_global_combinada`, `veredicto` | maneja casos sin datos con mensajes específicos |
| GET | `/api/dashboard/evolucion` | — | `{"puntos": [{fecha, nota_global_combinada, nota_fisica, nota_teorica}, ...]}` | |
| GET | `/api/pro/entrenamiento` | — | `{prueba_detectada, nombre, puntos_actuales, fecha_analisis, rutina}` | 404 si no hay ninguna marca registrada |
| GET | `/api/pro/teorica` | — | `{"tecnicas": [...]}` | |
| POST | `/api/pagos/checkout` | — | `{"session_id": ..., "url": ...}` | 502 si Stripe falla (clave inválida, etc.) |
| POST | `/api/pro/chat` | `{"mensaje": str}` (1-1000 chars) | `{"respuesta": str}` | 502 si OpenAI falla; 422 si mensaje vacío |

---

## 7. Tutor IA (RAG) — estado real: **implementado, no verificado en navegador**

Esto es lo que el mensaje original llamaba "la tarea en la que nos quedamos", pero **ya está construido**. Detalle exacto:

### 7.1 Dependencias
Ya añadidas a `requirements.txt`: `langchain>=1.3`, `langchain-openai>=1.3`, `langchain-chroma>=1.1`, `chromadb>=1.5`, `tiktoken>=0.8`.

**Gotcha importante:** el usuario pidió originalmente `langchain`, `langchain-openai`, `chromadb`, `tiktoken` — pero en LangChain 1.x la integración de Chroma vive en un paquete separado (**`langchain-chroma`**), que no estaba en la lista original y hubo que añadir. Sin él, `from langchain_chroma import Chroma` falla con `ModuleNotFoundError`.

### 7.2 `app/services/ai_tutor.py`
- `os.environ.setdefault("OPENAI_API_KEY", "sk-TU_CLAVE_AQUI")` — **esto sigue siendo un placeholder literal, no una clave real.** Hay que sustituirlo (o mejor, exportar `OPENAI_API_KEY` como variable de entorno real antes de arrancar el servidor, y quitar esta línea o dejarla solo como fallback).
- `SYSTEM_PROMPT`: restringe al tutor a responder solo con el contexto recuperado (rutinas + técnicas), en español, y a rechazar cortésmente preguntas fuera de ese ámbito.
- `_construir_documentos()`: convierte cada una de las 4 rutinas físicas y las 4 técnicas de estudio en un `Document` de LangChain con texto plano estructurado (título, base científica, fases con fundamento, bibliografía / concepto, pasos, ejemplo aplicado) — **8 documentos en total**.
- **Inicialización perezosa (lazy) crítica:** `_vectorstore` es un singleton global que empieza en `None` y solo se construye (`Chroma.from_documents(...)` con `OpenAIEmbeddings()`) la primera vez que se llama a `preguntar_al_tutor()`. Esto es deliberado: si se construyera al importar el módulo, la clave placeholder tumbaría el arranque de **toda la aplicación** (todos los routers dependen de que `main.py` importe correctamente). Verificado: con la clave placeholder, el servidor arranca limpio y todos los demás endpoints (marcas, teórica, dashboard, pro, pagos) responden 200 con normalidad.
- `preguntar_al_tutor(query)`: `similarity_search(query, k=4)` sobre el vectorstore → concatena los 4 fragmentos → los pasa junto al `SYSTEM_PROMPT` a `ChatOpenAI(model="gpt-4o-mini", temperature=0.3)` vía `.invoke([SystemMessage(...), HumanMessage(...)])` → devuelve `.content`.

### 7.3 `app/routers/chat.py`
- `POST /api/pro/chat`, Pydantic `ChatMensaje(mensaje: str, min_length=1, max_length=1000)`.
- Captura `openai.OpenAIError` (clase base real, confirmada por inspección: `AuthenticationError` hereda de `APIStatusError` → `APIError` → `OpenAIError` → `Exception`) y devuelve 502 con el detalle del error de OpenAI.
- **Verificado con curl:** con la clave placeholder, devuelve `502 {"detail": "El tutor IA no esta disponible ahora mismo: Error code: 401 - ... Incorrect API key provided..."}`. Reintentos posteriores no dejan el singleton en estado roto (si `Chroma.from_documents` lanza excepción, la asignación a `_vectorstore` nunca ocurre, así que el próximo intento vuelve a intentarlo desde cero — importante si el usuario actualiza la clave sin reiniciar el servidor... aunque en la práctica sí conviene reiniciar tras cambiar variables de entorno).

### 7.4 Frontend — bloque "Tutor Inteligente 24/7"
- Dentro de la pestaña Plan Pro (desbloqueada), al final, después de las subsecciones "1. Acondicionamiento Físico Estratégico" y "2. Alto Rendimiento Teórico".
- Burbujas de chat: usuario a la derecha (gradiente ámbar), IA a la izquierda con avatar 🚒 (fondo gris oscuro). Indicador de "escribiendo..." con 3 puntos animados (`@keyframes chat-dot-pulso`) mientras espera la respuesta.
- `main.js`: `formChat` (submit) → `pintarBurbujaChat(texto, "usuario")` → `pintarEscribiendo()` → `fetch POST /api/pro/chat` → `quitarEscribiendo()` → `pintarBurbujaChat(respuesta o error, "ia")`. Si el backend devuelve 502, el mensaje de error se pinta igualmente como burbuja de la IA (no rompe la UI).

### 7.5 Lo que falta para tener el Tutor IA 100% operativo
1. **Sustituir la clave placeholder por una clave real de OpenAI** en `ai_tutor.py` (o, mejor, exportarla como variable de entorno `OPENAI_API_KEY` antes de arrancar `run.py`).
2. **Probar en un navegador real** — nunca se ha completado una prueba visual end-to-end (preguntar algo, ver la respuesta real de `gpt-4o-mini`). Todo lo verificado hasta ahora es estructural: construcción de documentos, manejo de errores con clave inválida, sintaxis JS, simulación en Node del renderizado de las burbujas contra una respuesta de error real. **Nunca se ha visto una respuesta real generada por el modelo.**
3. Revisar que el tono/restricción del `SYSTEM_PROMPT` funciona como se espera (rechaza preguntas fuera de tema) — esto solo se puede comprobar con la clave real.
4. Decidir si se quiere persistir el historial de chat (ahora mismo vive solo en el DOM, se pierde al recargar la página).

---

## 8. Convenciones de código a seguir

- **Sin acentos en identificadores/nombres de tabla/nombres de variable** (todo el código Python usa `calculo`, `simulacro`, `nota_teorica`, etc., sin tildes) — pero **el contenido de texto (strings) sí lleva tildes correctamente** (verificado a nivel de bytes UTF-8 varias veces; si algo se ve con tildes rotas en una consola de Windows, es casi seguro un problema de codepage de la terminal, no un bug real — comprobar siempre con `.encode('utf-8')` antes de asumir que hay un bug).
- **Manejo de errores de SDKs externos:** patrón consistente en `pagos.py` y `chat.py` — capturar la excepción base del SDK (`stripe.error.StripeError`, `openai.OpenAIError`), envolver en `HTTPException(status_code=502, detail=f"...: {exc}")`. Nunca dejar que una excepción de un SDK externo tumbe el proceso.
- **Inicialización perezosa para cualquier cosa que dependa de una clave de API externa** (ver sección 7.2) — nunca hacer llamadas de red al importar un módulo.
- **Estilo Tailwind:** dark mode (`bg-gray-950` / `bg-gray-800/60` para tarjetas / `border-gray-700`), acento en gradiente `from-orange-600 to-amber-500`, `rounded-xl`/`rounded-2xl`, `shadow-lg`. Clases de estado (`.active`, badges, timeline) definidas en `style.css` porque Tailwind CDN no soporta JIT de clases custom.
- **SPA de una sola página** sin router: `main.js` tiene un objeto `views` (`dashboard`/`guia`/`pro`) y una función `activarVista(nombre)` que hace toggle de `.hidden`. Todo vive en `index.html`, no hay build step ni bundler.
- **Un único `main.js`**, sin módulos ES ni imports — todo en el mismo archivo, funciones y `const` a nivel global.

---

## 9. Deuda técnica y pendientes conocidos (leer antes de tocar nada)

1. **🔴 CRÍTICO — clave secreta de Stripe hardcodeada en el código fuente.** `backend/app/routers/pagos.py` tiene una clave `sk_test_...` real (no un placeholder) escrita directamente en el archivo. El proyecto no es un repo git todavía, pero **antes de inicializar git o subir esto a cualquier repositorio**, hay que: (a) mover la clave a una variable de entorno, (b) añadir un `.gitignore` que excluya cualquier archivo de configuración con secretos, (c) rotar la clave si en algún momento se ha compartido este código fuera de un entorno de confianza. Es una clave de test, no de producción, pero el hábito hay que corregirlo ya.

2. **🟠 Bases de datos SQLite duplicadas.** Existen **dos** archivos `oposiciones.db` divergentes:
   - `tracker-oposiciones/oposiciones.db` (raíz del proyecto) — **7 marcas físicas, 5 simulacros teóricos** — es la que usa `run.py` cuando se ejecuta como `python backend/run.py` desde la raíz (patrón usado en casi toda la sesión de desarrollo). **Esta es la canónica.**
   - `tracker-oposiciones/backend/oposiciones.db` — **2 marcas, 1 simulacro** — se creó en algún momento en que el servidor se arrancó con cwd dentro de `backend/` directamente. Está obsoleta y descoordinada con la de la raíz.
   - Acción recomendada: decidir cuál conservar (probablemente la de la raíz, tiene más datos), borrar la otra, y ser consistente con el cwd desde el que se arranca el servidor a partir de ahora (siempre `python run.py` con cwd=`backend/`, o `python backend/run.py` con cwd=raíz — **nunca mezclar ambos**).

3. **🟠 Tutor IA nunca probado con clave real ni en navegador** (ver sección 7.5 completa).

4. **🟠 Checkout de Stripe nunca completado en navegador real.** Solo se ha verificado que el endpoint responde bien (200 con URL válida cuando la clave es correcta a nivel de formato, 502 con clave inválida). Nunca se ha hecho clic en "Desbloquear", llegado a la página de Stripe, pagado con una tarjeta de test (`4242 4242 4242 4242`) y confirmado el redirect a `?pago=exito`.

5. **🟡 Verificación en navegador bloqueada durante gran parte de la sesión.** Dos causas recurrentes, ninguna relacionada con el código de este proyecto:
   - El tool de preview de Claude Code (`preview_start`) resuelve el `.claude/launch.json` de un directorio de trabajo distinto (`inversiones web`, un proyecto no relacionado) y en varias ocasiones un proceso ajeno ocupaba el puerto 8000, imposible de liberar desde esta sesión.
   - La extensión "Claude in Chrome" reportó "not connected" de forma intermitente.
   - Como mitigación se usó: arrancar el backend manualmente en un puerto alternativo (`PORT=XXXX python backend/run.py` en background) + verificación exhaustiva por `curl` + simulación de la lógica de renderizado del frontend en Node.js contra las respuestas JSON reales del backend (sin DOM real, pero comprobando que las plantillas no generan `undefined` ni excepciones). **Ninguna de las páginas de este proyecto se ha visto renderizada en un navegador real desde el rediseño premium** (sección "Plan Pro" con gráfica, timeline, chat).

6. **🟡 Contenido de `RUTINAS_PRO` con marcadores de cita sin resolver** (`[cite: 1135]` etc. — ver sección 5.2). Cosmético pero visible para el usuario final si se lee con atención.

7. **🟢 Menor:** el historial del chat del Tutor IA no se persiste (se pierde al recargar). El historial de marcas/simulacros sí se persiste (tablas SQL), pero no hay ningún endpoint ni UI que muestre ese historial completo más allá del último registro (los endpoints `/historial` existen y funcionan, pero el frontend no los consume en ningún sitio todavía).

---

## 10. Resumen para retomar en una frase

El proyecto es una app FastAPI + SQLite + frontend vanilla (Tailwind/Chart.js) para opositores a bombero, con un dashboard gratuito (cálculo físico/teórico sobre 10, gráficas, guía informativa) y un "Plan Pro" de pago (Stripe Checkout en modo test, ya con clave real puesta) que desbloquea rutinas de entrenamiento y técnicas de estudio basadas en diccionarios Python estáticos, más un Tutor IA con RAG (LangChain + Chroma en memoria + GPT-4o-mini) **ya implementado en código pero nunca probado de extremo a extremo con una clave real de OpenAI ni en un navegador real** — ese es el siguiente paso real, no la implementación desde cero.
