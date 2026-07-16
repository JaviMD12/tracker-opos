← [handover.md](../../handover.md)

# 4. Tutor IA y RAG (`services/ai_tutor.py`)

Este módulo es compartido por **tres** funcionalidades del Plan Pro — todas gatean por `is_pro` en su router respectivo, ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md):

| Función en `ai_tutor.py` | Router que la usa | Qué hace |
|---|---|---|
| `preguntar_al_tutor(query)` | `routers/chat.py` → `POST /api/pro/chat` | Chat libre restringido al contenido del Plan Pro |
| `generar_plan_estudio_convocatoria(titulo_plaza, requisitos_minimos)` | `routers/tutor.py` → `POST /api/tutor/analizar-plaza/{id}` | Plan de ataque en Markdown para una convocatoria concreta del Tablón |
| `generar_simulacro_test(tema, num_preguntas)` | `routers/simulacros.py` → `POST /api/simulacros/generar` | Examen tipo test JSON, con RAG sobre el temario |

Las tres comparten la misma instancia de vectorstore (`_vectorstore`, singleton de módulo) — ninguna duplica lecturas de disco ni llamadas a OpenAI para embeddings.

## Base de conocimiento (`app/conocimiento/`)
Contiene ahora mismo **~20 documentos reales**: PDFs del CTE (DBHE, DBHR, DBHS, DBSE*, DBSI, DBSUA), BOE consolidados, y temario específico del Consorcio de Bomberos de Huelva (TEMA-10 a TEMA-38: EPI, GLP, organización, procedimientos, estatutos...), más 2 TXT (técnicas de estudio, análisis científico del entrenamiento). Esto creció mucho respecto al handover anterior (que solo mencionaba 1 PDF + 2 TXT) — si en el futuro se ve un documento nuevo aquí, probablemente lo subió el usuario directamente, no hace falta preguntar.

## Persistencia en disco (`chroma_db_data/`) — antes no existía
Hasta hace poco, el vectorstore se reconstruía **en memoria desde cero en cada arranque del servidor**, leyendo los ~20 PDFs y regenerando embeddings vía OpenAI — esto tardaba **1-2 minutos** en la primera petición tras cada reinicio. Se refactorizó `_obtener_vectorstore()`:

- **CASO A** (índice ya existe en `backend/chroma_db_data/`): `Chroma(persist_directory=..., embedding_function=...)` — carga en **~0.5s**.
- **CASO B** (carpeta vacía/borrada, ej. tras un `git clone`): reconstruye todo el pipeline y persiste con `Chroma.from_documents(..., persist_directory=...)`. Tarda ~105s medido en real.
- `chroma_db_data/` está en `.gitignore` (pesa ~120MB) — **si alguien clona el repo de cero, la primera petición al Tutor IA/Simulacros volverá a tardar 1-2 minutos**, es esperado, no un bug.

## Saneado de texto Unicode (bug real ya corregido)
`_sanear_texto_unicode()` limpia surrogates UTF-16 sueltos que `pypdf` deja al extraer texto de algunos PDFs (fuentes no estándar). Sin esto, `Chroma`/`chromadb` (bindings en Rust) lanza `UnicodeEncodeError: 'utf-8' codec can't encode characters ... surrogates not allowed` y **rompe el vectorstore entero** — afecta a las tres funcionalidades de la tabla de arriba a la vez, no solo a una. Se aplica en `_cargar_documentos_conocimiento()` a cada `Document.page_content` antes de trocear/indexar.

## Prompts: nada de temario mezclado
El prompt de `generar_plan_estudio_convocatoria` fue reescrito explícitamente para **no forzar siempre "hidráulica"** — el system prompt es genérico ("analista experto en oposiciones") y el user prompt exige: identificar el cuerpo real por el título, y construir el plan **exclusivamente** según la naturaleza de esa plaza (administrativa → legislación; bomberos → fuego/hidráulica). Verificado con una plaza administrativa (sin mención de fuego/hidráulica) y una de bomberos (sí las menciona).

## Filtro de "consorcio" — relacionado, ver también scraper
El scraper de convocatorias (`services/scraper_boletines.py`, [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md)) alimenta la tabla `Convocatoria` que consume `generar_plan_estudio_convocatoria` — si el filtro del scraper deja pasar ruido (policía, consorcios de agua...), ese ruido llega también al generador de planes de estudio. Los dos módulos están acoplados por los datos, aunque el código esté separado.
