← [handover.md](../../handover.md)

# 4. Tutor IA y RAG (`services/ai_tutor.py`)

Este módulo es compartido por **dos** funcionalidades del Plan Pro que sí llaman a Gemini en vivo por petición — todas gatean por `is_pro` en su router respectivo, ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md):

| Función en `ai_tutor.py` | Router que la usa | Qué hace |
|---|---|---|
| `preguntar_al_tutor(query)` | `routers/chat.py` → `POST /api/pro/chat` | Chat libre restringido al contenido del Plan Pro |
| `generar_plan_estudio_convocatoria(titulo_plaza, requisitos_minimos)` | `routers/tutor.py` → `POST /api/tutor/analizar-plaza/{id}` | Plan de ataque en Markdown para una convocatoria concreta del Tablón |

Las dos comparten la misma instancia de vectorstore (`_vectorstore`, singleton de módulo) — ninguna duplica lecturas de disco ni llamadas a Gemini para embeddings. `generar_banco.py` (offline, no un router) **también** usa este mismo vectorstore para generar el banco de Simulacros con RAG — ver [06-simulacros-ia.md](06-simulacros-ia.md).

> **Los Simulacros ya NO llaman a Gemini en vivo por petición.** Existió una `generar_simulacro_test()` en este módulo que hacía eso; se eliminó hace tiempo (ver el comentario en `app/models/pregunta_test.py`) y se sustituyó por un banco de preguntas precargado (`PreguntaTest`) generado offline — el endpoint `POST /api/simulacros/generar` hoy es un simple `SELECT` aleatorio sobre ese banco, sin coste ni latencia de LLM por petición de usuario. Ver [06-simulacros-ia.md](06-simulacros-ia.md) para el mecanismo real y completo.

## Motor: **Gemini, no OpenAI** (migración completa)
Todo el módulo (`ai_tutor.py`) usa `langchain_google_genai` (`ChatGoogleGenerativeAI`, `GoogleGenerativeAIEmbeddings`), no `langchain_openai`. Modelos: `gemini-2.5-flash` (chat) + **`models/gemini-embedding-001`** (embeddings — no `text-embedding-004`, que da 404 en esta API/clave, ni `gemini-embedding-1.0`). Las excepciones de proveedor son `google.genai.errors.APIError`, no `openai.OpenAIError`. Esto se aplicó también al scraper de convocatorias (ver [05](05-tablon-convocatorias-scraper.md)) y a los routers `chat.py`/`tutor.py`, que capturan `APIError` en vez de `OpenAIError`.

## Base de conocimiento (`app/conocimiento/`)
Contiene ahora mismo **más de 30 documentos reales** (creció bastante en esta ronda): PDFs del CTE (DBHE, DBHR, DBHS, DBSE*, DBSI, DBSUA), BOE consolidados, temario específico del Consorcio de Bomberos de Huelva (TEMA-10 a TEMA-38: EPI, GLP, organización, procedimientos, estatutos...), 7 PDFs de temario técnico añadidos en esta sesión (`acondicionamiento.pdf`, `eov.pdf`, `incendios.pdf`, `mandos.pdf`, `rescate.pdf`, `riesgos_tecnologicos.pdf`, `sanitario.pdf`), 4 PDFs de preparación (nutrición, optimización cognitiva, preparación científica, rendimiento físico), más 2 TXT (técnicas de estudio, análisis científico del entrenamiento). Si en el futuro se ve un documento nuevo aquí, probablemente lo subió el usuario directamente, no hace falta preguntar.

**Procedimiento para añadir contenido nuevo** (verificado, se ha hecho varias veces): copiar los archivos a `backend/app/conocimiento/`, hacer commit/push del binario (los PDFs de `conocimiento/` **sí viajan con git**, no están en `.gitignore`), `git pull` en el VPS, y borrar `backend/chroma_db_data/` en **ambos** entornos para forzar la reconstrucción (se reconstruye solo en la primera pregunta al tutor, 1-2 min). **Hacerlo siempre en serie, local y VPS nunca a la vez** — la cuota de embeddings de Gemini es por minuto y reconstruir en paralelo la agota (ya pasó una vez).

## Metadata `archivo` en cada chunk indexado (nueva)
`_cargar_documentos_conocimiento()` añade `documento.metadata["archivo"] = Path(source).name` a cada fragmento (nombre de archivo, no ruta completa — difiere entre Windows local y el VPS Linux). Esto es lo que permite que `generar_banco.py` filtre el RAG del Simulacro por tema restringiéndose a documentos concretos (`TEMA_A_ARCHIVOS`, ver [06-simulacros-ia.md](06-simulacros-ia.md)) en vez de por pura similitud semántica sobre todo el corpus. Si se reconstruye el índice con una versión de `ai_tutor.py` anterior a esta metadata, el filtrado por tema deja de funcionar silenciosamente (el `filter={"archivo": {"$in": [...]}}` de Chroma simplemente no encuentra coincidencias) — si el generador de preguntas empieza a devolver 0 resultados para un tema, sospechar de esto primero.

## Persistencia en disco (`chroma_db_data/`) — antes no existía
Hasta hace poco, el vectorstore se reconstruía **en memoria desde cero en cada arranque del servidor**, leyendo los PDFs y regenerando embeddings vía Gemini — esto tardaba **1-2 minutos** en la primera petición tras cada reinicio. Se refactorizó `_obtener_vectorstore()`:

- **CASO A** (índice ya existe en `backend/chroma_db_data/`): `Chroma(persist_directory=..., embedding_function=...)` — carga en **~0.5s**.
- **CASO B** (carpeta vacía/borrada, ej. tras un `git clone`): reconstruye todo el pipeline y persiste con `Chroma.from_documents(..., persist_directory=...)`. Tarda ~105s medido en real.
- `chroma_db_data/` está en `.gitignore` (pesa ~120MB) — **si alguien clona el repo de cero, la primera petición al Tutor IA/Simulacros volverá a tardar 1-2 minutos**, es esperado, no un bug.

## Saneado de texto Unicode (bug real ya corregido)
`_sanear_texto_unicode()` limpia surrogates UTF-16 sueltos que `pypdf` deja al extraer texto de algunos PDFs (fuentes no estándar). Sin esto, `Chroma`/`chromadb` (bindings en Rust) lanza `UnicodeEncodeError: 'utf-8' codec can't encode characters ... surrogates not allowed` y **rompe el vectorstore entero** — afecta a las tres funcionalidades de la tabla de arriba a la vez, no solo a una. Se aplica en `_cargar_documentos_conocimiento()` a cada `Document.page_content` antes de trocear/indexar.

## Prompts: nada de temario mezclado
El prompt de `generar_plan_estudio_convocatoria` fue reescrito explícitamente para **no forzar siempre "hidráulica"** — el system prompt es genérico ("analista experto en oposiciones") y el user prompt exige: identificar el cuerpo real por el título, y construir el plan **exclusivamente** según la naturaleza de esa plaza (administrativa → legislación; bomberos → fuego/hidráulica). Verificado con una plaza administrativa (sin mención de fuego/hidráulica) y una de bomberos (sí las menciona).

## Filtro de "consorcio" — relacionado, ver también scraper
El scraper de convocatorias (`services/scraper_boletines.py`, [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md)) alimenta la tabla `Convocatoria` que consume `generar_plan_estudio_convocatoria` — si el filtro del scraper deja pasar ruido (policía, consorcios de agua...), ese ruido llega también al generador de planes de estudio. Los dos módulos están acoplados por los datos, aunque el código esté separado.
