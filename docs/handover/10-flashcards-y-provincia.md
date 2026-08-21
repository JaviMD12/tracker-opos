← [handover.md](../../handover.md)

# 10. Flashcards (repetición espaciada) y categoría Provincia

Feature nueva de esta sesión (2026-08-21), añadida en dos rondas: primero el módulo de Flashcards en sí, luego (a petición explícita del usuario) una categoría nueva "Provincia" compartida por Flashcards y Simulacros, más una auditoría de cobertura de `TEMA_A_ARCHIVOS` en `generar_banco.py`.

## Flashcards — modelo de datos

- `Flashcard` (`app/models/flashcard.py`): `id`, `tema`, `pregunta`, `respuesta`. Banco compartido entre todos los usuarios Pro, generado offline (igual que `PreguntaTest` de Simulacros, ver [06](06-simulacros-ia.md)).
- `ProgresoFlashcard` (`app/models/progreso_flashcard.py`): `usuario_id`, `flashcard_id`, `intervalo_dias`, `facilidad`, `fecha_proximo_repaso`. `UniqueConstraint(usuario_id, flashcard_id)`. Sin fila hasta el primer repaso — una flashcard sin fila para un usuario cuenta como pendiente desde el primer momento.
- Tablas nuevas, creadas por `Base.metadata.create_all()` normal (no hace falta `_asegurar_columna()`, no son columnas nuevas sobre tablas existentes).

## Algoritmo de repetición espaciada (`app/services/srs.py`)

Versión **simplificada** de SM-2 (el algoritmo real de Anki): decisión deliberada de no llevar un contador aparte de "repeticiones correctas consecutivas" (los intervalos fijos de 1/6 días del SM-2 original) porque el modelo de progreso solo pide `intervalo_dias`/`facilidad`/`fecha_proximo_repaso` — en su lugar, `intervalo_dias` hace de estado acumulado:

- **Difícil** (resultado=3): `facilidad = max(1.3, facilidad - 0.2)`, `intervalo = 1` (reinicio total).
- **Medio** (resultado=2): `intervalo = max(1, round(intervalo * 1.2))`, facilidad sin cambios.
- **Fácil** (resultado=1): `intervalo = max(1, round(intervalo * facilidad))`, `facilidad = min(3.0, facilidad + 0.15)`.

Facilidad inicial: 2.5 (igual que el SM-2 estándar). Verificado en el navegador real con una sesión completa de 3 tarjetas (Difícil/Fácil/Medio) contra la fórmula exacta — los tres resultados en BD coincidieron al dígito.

## Endpoints (`app/routers/flashcards.py`)

- `GET /api/flashcards/due?tema=X`: `LEFT JOIN` de `Flashcard` contra `ProgresoFlashcard` del usuario actual — pendiente si no hay fila de progreso (nunca repasada) o si `fecha_proximo_repaso <= hoy`. Límite de 30 tarjetas por sesión (mismo criterio que el "daily review limit" de Anki). 403 si no `is_pro`.
- `POST /api/flashcards/review`: recibe `flashcard_id` + `resultado` (1/2/3), crea la fila de progreso si no existe, aplica `calcular_siguiente_repaso()` y persiste. 403 si no `is_pro`.

Verificado end-to-end: `/due` devuelve `[]` tras repasar todas las tarjetas pendientes de un tema, y vuelve a devolver resultados al día siguiente (según `fecha_proximo_repaso`).

## Generador (`backend/generar_flashcards.py`)

No interactivo (a diferencia de `generar_banco.py`), reutiliza de `generar_banco.py`: `TEMA_A_ARCHIVOS`, `TEMAS_CONOCIDOS`, `ENFOQUES_ROTATORIOS`, `_recuperar_contexto()` — mismo RAG que Simulacros y el Tutor IA, no lee los PDFs en crudo (decisión deliberada: el índice ya tiene meses de fixes reales aplicados — cabeceras repetidas, tablas de PDF extraídas con `pdfplumber` — releer los archivos originales los reintroduciría). `SYSTEM_PROMPT` propio, pide pares Pregunta/Respuesta concisos (memorizables en segundos), no preguntas tipo test.

```bash
cd backend
python generar_flashcards.py [cantidad_por_tema]   # no interactivo, todos los temas, 30 por defecto, idempotente
```

**Estado actual: 210 flashcards (30 × 7 temas)** generadas y verificadas en local el 2026-08-21. **🟠 Sin desplegar al VPS.**

## Frontend

Pestaña nueva "Flashcards" en la Zona Premium (`#premium-view-flashcards`), quinta pestaña junto a Inicio/Tutor/Simulacros/Enfoque, mismo patrón `premium-tab-btn`/`premium-subview` ya establecido — no se tocó el sistema de navegación. Tarjeta con flip 3D real (`rotateY(180deg)` + `transform-style: preserve-3d` + `backface-visibility: hidden`, perspectiva en el contenedor padre `.flashcard-escenario`), 3 botones (Difícil/Medio/Fácil) que aparecen tras voltear. Cola de tarjetas en memoria (`colaFlashcards`), avanza sin recargar hasta vaciarse → estado "Sin tarjetas pendientes".

**Nota de verificación**: el flip 3D se verificó funcionalmente completo (clases CSS correctas, única regla que aplica, lógica de avance/estado) pero no se pudo confirmar visualmente pixel a pixel — el panel del navegador de la sesión no estaba componiendo frames (`document.hidden=true`). Si en el futuro se reporta algo raro con la animación, verificar primero en un navegador real antes de asumir que el código está mal.

## Categoría "Provincia" — auditoría de `TEMA_A_ARCHIVOS`

A petición explícita del usuario: nueva categoría (cartografía/historia/cultura de la **provincia de Huelva**, distinta de "Legislacion" o del corpus sin filtrar de "General"), compartida por Simulacros y Flashcards porque ambos leen el mismo `TEMA_A_ARCHIVOS` de `generar_banco.py`.

Se comparó ese mapa contra el contenido real de `conocimiento/` (84 archivos) y se encontraron 68 huérfanos (solo alcanzables vía `General`). Cada uno se identificó leyendo su contenido real con `pdfplumber`/`python-docx` antes de decidir dónde mapearlo — **nunca solo por el nombre del archivo**, ver el patrón ya establecido en [08-convenciones-de-codigo.md](08-convenciones-de-codigo.md) punto 29.

**Bug real encontrado y corregido durante la generación**: dos documentos con nombre "de carreteras" que sonaban a cartografía de Huelva (`2018_modelo_hitos_km_0.pdf`, `ReddeCarreterasdeAndalucia_Diciembre2024_0.pdf`) resultaron ser datos de **toda Andalucía** al leerlos de verdad (ej. "¿Cuántos km de Red Provincial tiene Córdoba?"). Colaron flashcards de otras provincias en el primer lote generado. Se purgaron las 30 flashcards de "Provincia" de ese primer lote, se sacaron esos dos archivos de `TEMA_A_ARCHIVOS["Provincia"]` (se quedan solo en `General`) y se regeneró desde cero — verificado con una muestra de 10 tarjetas, las 10 específicas de Huelva. Moraleja para el futuro: el nombre de archivo no basta ni para el primer filtro, hay que leer el contenido siempre, incluso cuando "suena obvio".

Los Anexos 2 y 3 del PTEAnd (añadidos en la sesión del 2026-08-19 para cerrar el hueco de Geografía de Andalucía, ver [07](07-deuda-tecnica-y-pendientes.md) punto 35) se dejaron **fuera** de Provincia a propósito, por el mismo motivo: cubren Andalucía completa, no la provincia de Huelva.

**11 documentos duplicados eliminados** de paso: varios archivos existían tanto en `.docx` como en `.pdf` con el mismo contenido (verificado letra por letra, no solo por el nombre) — probablemente convertidos a PDF en su día porque el loader de `conocimiento/` aún no soportaba `.docx` (soporte añadido el 2026-08-16, ver [04](04-tutor-ia-y-rag.md)), y nunca se limpió el duplicado tras esa mejora. Se indexaban dos veces, sesgando la búsqueda semántica. Se conservó siempre el `.docx`. De paso se normalizó a NFC (`Í` precompuesto) el nombre de `POLÍGONOS INDUSTRIALES.docx`, que estaba en NFD (`I` + acento combinante) por algún proceso de guardado anterior — típico de macOS, causaba que cualquier referencia al archivo escrita a mano en el código no hiciera match con el nombre real en disco.

Índice `chroma_db_data/` local reconstruido desde cero tras los borrados (obligatorio: los duplicados borrados dejarían fragmentos huérfanos en el índice persistido si no se reconstruye).

## 🔴 Pendiente crítico: nada de esto está desplegado al VPS

Todo lo de esta sección (modelos, endpoints, frontend, `TEMA_A_ARCHIVOS` actualizado, los 11 archivos borrados/renombrados en `conocimiento/`, y los bancos generados) está commiteado en `origin/main` (commit `d4924cf`) pero el VPS sigue en el estado anterior: sin las tablas `flashcards`/`progreso_flashcards`, sin la categoría Provincia, sin las leyes nuevas de Legislacion/Incendio/Equipos de Intervencion, y con los 11 documentos duplicados todavía indexados. Desplegar requiere, en este orden:

1. `git pull` en el VPS.
2. `systemctl restart tracker-opos.service` (crea las tablas nuevas vía `create_all()` al arrancar).
3. Borrar `chroma_db_data/` en el VPS y dejar que se reconstruya (obligatorio, cambiaron los archivos fuente) — **hacerlo en serie, nunca a la vez que un rebuild en local** (cuota de embeddings de Gemini por minuto, ver [08](08-convenciones-de-codigo.md)). Puede tardar mucho: el rebuild anterior con extracción de tablas tardó 1022s en local y 2161s en el VPS (con swap), ver [07](07-deuda-tecnica-y-pendientes.md) punto 33 — vigilar memoria.
4. `python generar_flashcards.py 30` y `python generar_banco_completo.py 100` en el VPS, con `GOOGLE_API_KEY` en el `.env` real de producción.
