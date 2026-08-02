← [handover.md](../../handover.md)

# 6. Simulacros IA (examen tipo test, Plan Pro)

> **Esta sección estaba desactualizada respecto al mecanismo real** (describía generación en vivo por petición vía `ai_tutor.py::generar_simulacro_test`). Esa función **ya no existe** — fue eliminada hace tiempo (ver el propio comentario en `app/models/pregunta_test.py`) y sustituida por un banco de preguntas precargado. Reescrito para reflejar el estado real, más los cambios de RAG y taxonomía de esta sesión.

## Por qué un banco precargado y no generación en vivo
Generar preguntas con Gemini en cada `POST /api/simulacros/generar` era lento (varios segundos) y caro (una llamada al modelo por cada examen de cada usuario). Se sustituyó por: preguntas generadas **offline**, guardadas en una tabla, y el endpoint hace un `SELECT ... ORDER BY RANDOM() LIMIT N` — instantáneo, sin coste por petición, y `ORDER BY RANDOM()` se compila igual en SQLite y en Postgres (los dos motores que soporta `database.py`).

## Backend
- `PreguntaTest` (`app/models/pregunta_test.py`): `tema`, `enunciado`, `opciones` (JSON), `respuesta_correcta` (índice 0-3), `justificacion`. Es el banco precargado.
- `ResultadoSimulacro` (`usuario_id`, `fecha`, `tema`, `aciertos`, `total_preguntas`) — **distinto de `SimulacroTeorico`** (el autoinforme manual del dashboard gratuito, ver [03](03-rendimiento-fisico-teorico-gamificacion.md)). Nombres parecidos, conceptos distintos, no fusionar.
- `routers/simulacros.py`:
  - `POST /generar`: 403 si no `is_pro`. `SELECT` aleatorio sobre `PreguntaTest` filtrado por `tema`, `LIMIT num_preguntas`. 404 si no hay preguntas precargadas para ese tema (mensaje explícito: "Genera el banco con backend/generar_banco.py").
  - `POST /guardar`: persiste el resultado, sin gating adicional (solo requiere login).

## Generación del banco — `backend/generar_banco.py` / `generar_banco_completo.py`
**Cambio de esta sesión: ahora usa RAG real contra `conocimiento/`**, no el conocimiento general de Gemini sin anclar. Cada lote recupera 8 fragmentos del mismo vectorstore que el Tutor IA (`ai_tutor.py::_obtener_vectorstore()`) para el tema+enfoque de ese lote, y se le pide al modelo que base las preguntas **únicamente** en ese contexto — verificado con ejemplos reales donde la pregunta y la justificación citan literalmente el contenido del PDF fuente.

### Taxonomía de temas — cambiada esta sesión
De `Legislacion / Hidraulica / Fuego` a:

| Tema | Documentos que lo alimentan (RAG) |
|---|---|
| Legislacion | Constitución (BOE-A-1978), RD Instalaciones Térmicas (BOE-A-2007), RD seguridad incendios industriales (BOE-A-2025), Estatutos CPBH (TEMA-37), Anuncio convocatoria (BOP-80) |
| General | **Sin filtro** — todo `conocimiento/` (excepción deliberada) |
| Rescate | `rescate.pdf` |
| Sanitario | `sanitario.pdf` |
| Incendio | `incendios.pdf`, `DBSI.pdf`, TEMA-33 (GLP), `riesgos_tecnologicos.pdf` |
| Equipos de Intervencion | `eov.pdf`, `mandos.pdf`, TEMA-10, TEMA-36, TEMA-38 |

Reflejado en el `<select id="simulacro-tema">` de `frontend/index.html` y en `TEMA_A_ARCHIVOS` dentro de `generar_banco.py` (única fuente de verdad del mapa, editable ahí si se reclasifica algo).

### Filtrado RAG por tema (`TEMA_A_ARCHIVOS`)
Antes, el RAG de cada tema buscaba por pura similitud semántica en **todo** el corpus — "Legislación" acababa recuperando fragmentos de los códigos técnicos de edificación (CTE) por parecido de vocabulario, no por ser realmente legislación. Ahora cada tema (salvo `General`) restringe la búsqueda a una lista de archivos concretos, comparando la metadata `archivo` que `ai_tutor.py` añade a cada chunk indexado (ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md)) vía `filter={"archivo": {"$in": [...]}}` de Chroma.

### Bugs corregidos en el generador
- **Gemini 2.5 Flash reserva parte de `max_output_tokens` para "pensar" internamente** (`thinking`), dejando muy poco margen para el JSON real y cortándolo a mitad (`json.loads` fallaba con `"Unterminated string"` / `"Expecting ',' delimiter"`). Se desactivó (`thinking_config=types.ThinkingConfig(thinking_budget=0)`, esta tarea es extracción/generación estructurada, no requiere razonamiento) y se subió `max_output_tokens` de 8192 a 16384.
- **El bucle descontaba `restantes` por el tamaño de lote pedido, no por lo realmente guardado** — Gemini a veces devuelve menos preguntas de las pedidas (más probable cuanto más larga es la lista de "no repitas esto"), y eso dejaba el banco por debajo del objetivo real sin que nadie se enterara. Corregido en `generar_y_guardar_lotes()` (función reutilizable, usada tanto por el flujo interactivo de `generar_banco.py` como por `generar_banco_completo.py`).

### Comandos
```bash
cd backend
python generar_banco.py              # interactivo, un tema a la vez, pide tema y cantidad por consola
python generar_banco_completo.py     # no interactivo, los 6 temas de una vez, 100 por defecto (argumento opcional para otra cantidad)
python purgar_preguntas.py           # vacia toda la tabla preguntas_test antes de regenerar
```
`generar_banco_completo.py` es **idempotente**: si un tema ya tiene la cantidad objetivo o más, se omite; si tiene menos, solo genera lo que falta (reutiliza `generar_y_guardar_lotes()`).

### Estado actual de los datos
**600 preguntas (100 × 6 temas)**, generadas y verificadas tanto en local (SQLite) como en producción (VPS, Postgres) al cierre de esta sesión.

## Frontend
Vista "Simulacros" dentro de la Zona Premium (tras el rediseño de pestañas de esta sesión — antes vivía apilada en la misma página que el resto de Plan Pro, ver [09-zona-premium-y-upsell.md](09-zona-premium-y-upsell.md)). Diseño centrado (`max-w-2xl`), sin distracciones.

Flujo en 3 pasos, sin cambios en esta sesión:
1. **Config**: selects de tema (los 6 nuevos) y nº de preguntas (5/10/20).
2. **Test**: preguntas con `<input type="radio">`, generadas dinámicamente. Quedan en memoria (`preguntasSimulacroActual`) para poder corregir sin volver a llamar al backend.
3. **Corrección**: compara cada respuesta marcada contra el índice `correcta`; pinta verde/rojo tenue, muestra `explicacion`, calcula nota sobre 10, y hace `POST /guardar` en silencio.

## Rendimiento esperado
Como es un `SELECT` sobre un banco ya generado, `POST /generar` es prácticamente instantáneo (no depende de Gemini ni de la carga del vectorstore) — el único caso lento es *generar* el banco (`generar_banco_completo.py`), que si además tiene que reconstruir `chroma_db_data/` desde cero puede tardar varios minutos antes de empezar a generar preguntas.
