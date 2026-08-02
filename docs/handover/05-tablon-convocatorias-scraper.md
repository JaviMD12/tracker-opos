← [handover.md](../../handover.md)

# 5. Tablón de Convocatorias Premium + scraper de boletines

## Modelo y endpoint
- `Convocatoria` (`titulo_plaza`, `organismo_localidad`, `plazo_dias`, `fecha_publicacion`, `fecha_limite`, `requisitos_minimos`, más `url_origen` **único** — necesario para no duplicar filas ni gastar llamadas a Gemini de más cuando el cron reprocesa el mismo feed cada 24h). `dias_restantes` es una `@property` calculada al vuelo (no una columna) a partir de `fecha_limite`.
- `GET /api/convocatorias` (`routers/convocatorias.py`): 403 si `current_user.is_pro` es falso; si no, hasta 100 candidatas ordenadas por fecha, filtradas en Python por `dias_restantes is None or dias_restantes >= 0` (no en SQL — SQLite no conserva el tzinfo en sus columnas `DateTime(timezone=True)` al releerlas, a diferencia de Postgres, y comparar eso contra un datetime aware de Python da resultados inconsistentes entre los dos motores), devolviendo las primeras 20 vigentes.
- Frontend: sección "Dashboard / Inicio" dentro de la Zona Premium (tras el rediseño de pestañas, ver [09-zona-premium-y-upsell.md](09-zona-premium-y-upsell.md)) — la clase `.tablon-cta` ya no existe, el paywall es un único cartel compartido por toda la Zona Premium (`#premium-locked`), no un bloqueo por módulo.

## Scraper (`services/scraper_boletines.py`)

### Feeds — verificados manualmente, no adivinados
```
https://www.boe.es/rss/canal_per.php?l=p&c=140                  # BOE: Oposiciones
https://www.juntadeandalucia.es/boja/distribucion/s53.xml       # BOJA: 2.2 Oposiciones y concursos
```

### Filtro de palabras clave (positivo) y lista negra (negativo)
```python
PALABRAS_CLAVE = ["bombero", "bomberos", "extincion de incendios",
                   "extinción de incendios", "salvamento",
                   "proteccion civil", "protección civil"]
# "consorcio" se quito a proposito: solo, metia ruido (consorcios de agua, culturales...)

PALABRAS_PROHIBIDAS = ["policia", "policía", "guardia civil"]
# se comprueba ANTES que las palabras clave; si aparece, se descarta con
# `continue` aunque tambien contenga una palabra clave valida (resoluciones
# conjuntas ayuntamiento: bomberos + policia en el mismo anuncio)
```

### Deep scraping (texto completo, no solo el resumen del RSS)
El resumen del RSS es una frase; los datos clave (plazo, requisitos, fecha real de publicación) están en el cuerpo de la resolución completa. `_obtener_texto_completo(url)` hace `requests.get()` al `entrada.link` (con `User-Agent`, algunos boletines bloquean el UA por defecto) y extrae el texto de `<p>`, **`<dd>` y `<dt>`** con BeautifulSoup (los metadatos van primero, antepuestos a los párrafos — ver más abajo por qué), recortado a 15.000 caracteres. Si la descarga falla o no encuentra texto, cae de vuelta al resumen corto del RSS en vez de abortar la entrada (y ahora deja un log si eso pasa).

### Extracción con IA
`gemini-2.5-flash` con `response_mime_type="application/json"` (ya no `gpt-4o-mini`/`response_format: json_object` de OpenAI), con el System Prompt pedido por el usuario más el campo `fecha_publicacion_boletin` añadido en esta sesión (ver siguiente sección). Si el texto no es una convocatoria real, el modelo devuelve `{"error": "no es convocatoria"}` y se descarta.

### Cron (APScheduler, en `main.py`)
`CronTrigger(hour=3, minute=0)`, timezone `Europe/Madrid`, arrancado/parado en `@app.on_event("startup"/"shutdown")`. **Caveat de producción**: con varios workers de gunicorn, cada worker crearía su propio scheduler y el job se dispararía N veces a esa hora — el `UniqueConstraint` de `url_origen` evita duplicados en BD, pero convendría un solo worker dedicado al cron antes de escalar.

## 🔴 Bug real encontrado y corregido: fechas de publicación mal calculadas (impacto real en producción)
Se encontró una convocatoria de Huelva marcada como vigente (plazo hasta agosto) que en realidad **llevaba cerrada desde junio**. Causa raíz verificada contra el BOE real: `_obtener_texto_completo()` solo capturaba `<p>`, y la fecha real de publicación del BOE vive en metadatos `<dd>/<dt>` de una ficha ("Publicado en: BOE núm. 127, de 25 de mayo de 2026..."), así que el extractor nunca la veía y el cálculo caía al fallback de metadatos del RSS (`_fecha_publicacion_entrada`), que puede ir **meses** por delante de la fecha real de publicación (el campo `updated_parsed` del RSS a veces refleja cuándo el feed tocó/reactivó la entrada, no cuándo se publicó de verdad).

**Fix aplicado:**
- `_obtener_texto_completo` ahora también captura `<dd>`/`<dt>`, antepuestos a los `<p>` para que sobrevivan al recorte de 15.000 caracteres en páginas largas.
- Nuevo campo `fecha_publicacion_boletin` en el `SYSTEM_PROMPT`: se le pide al modelo la fecha de publicación **declarada explícitamente en el texto** (distinguiéndola a propósito de la fecha de la "Resolución de...", que es cuando se firmó el acto, normalmente antes de publicarse).
- `_parsear_fecha_boletin(valor)`: parsea y valida esa fecha (rechaza si no es `"AAAA-MM-DD"`, si es futura, o si es tan antigua — más de 3 años — que huele a alucinación), priorizada sobre `_fecha_publicacion_entrada()` (RSS).
- **Red de seguridad**: si con la mejor fecha disponible el plazo ya venció, la convocatoria se descarta **antes de guardarla** (`ejecutar_scraping_boletines`), no solo se filtra en la lectura (`GET /api/convocatorias`) dejando la fila muerta acumulándose en la tabla.

## 🔴 Audit posterior: más bugs corregidos (a petición explícita, "revisa el resto del scraper")
Un audit dedicado tras el fix de fechas encontró que **casi todo el cuerpo del bucle no tenía manejo de excepciones**, pese a que el docstring del módulo ya prometía que un fallo puntual nunca aborta el lote — solo la llamada al LLM estaba protegida. Corregido:
- `_fecha_publicacion_entrada()` ya **no usa `datetime.now()` como fallback** cuando el RSS no trae fecha: una fecha "ahora" siempre calcula un plazo en el futuro por construcción, lo que **anulaba por completo la red de seguridad recién añadida** (una convocatoria vieja sin metadatos de fecha se colaba disfrazada de recién publicada — el mismo bug de Huelva, por otra vía). Ahora devuelve `None`, y la entrada se descarta si tampoco hay fecha extraída del texto.
- `_normalizar_plazo_dias()` (nueva): `plazo_dias` como float (`20.0`) o string numérico (`"20"`) — Gemini lo hace pese a que el prompt pide `int` — antes se rechazaba con un `isinstance` estricto, dejando `fecha_limite` en `None` y colando convocatorias **ya vencidas** sin pasar por la red de seguridad (que solo actúa si `fecha_limite` es verdadero). `bool` se excluye a propósito (es subclase de `int` en Python).
- `_extraer_datos_convocatoria()` valida que la respuesta del modelo sea realmente un `dict` antes de usarla (evita `TypeError`/`AttributeError` si Gemini devolviera `null`, una lista o un string — `response_mime_type="application/json"` solo garantiza JSON sintácticamente válido, no la forma del objeto).
- `titulo_plaza`/`organismo_localidad` se validan como string no vacío antes de guardar — antes, un valor JSON `null` se guardaba como el string literal `"None"` vía `str(None)` (ambos campos son `nullable=False` en el modelo).
- **Todo el bloque de guardado (validación → cálculo de fechas → `db.commit()`) queda envuelto en `try/except Exception` con `db.rollback()`**: antes, una excepción no prevista (p.ej. un `IntegrityError` de carrera entre workers de gunicorn, cada uno con su propio scheduler) abortaba `ejecutar_scraping_boletines()` entero — y como la fila nunca se comprometía, tampoco quedaba deduplicada por `url_origen`, así que la misma entrada podía volver a reventar la ejecución del día siguiente, bloqueando indefinidamente todo lo que viniera después en el feed.
- **Verificado con una ejecución real** contra los feeds en vivo: la red de seguridad descartó automáticamente *otra* convocatoria ya vencida (`BOE-A-2026-13813`) sin intervención manual.

## Calidad de datos — limitaciones conocidas, no bugs
- El RSS a veces agrupa varias categorías de plaza en una sola resolución (ej. "Técnico/a de Administración General..." proviene de una resolución del Consorcio de Extinción de Incendios de Toledo que en realidad también cubre otras plazas) — el modelo extrae fielmente lo que hay en el texto, esto es fidelidad de la fuente, no un fallo de extracción.
- `plazo_dias`/`requisitos_minimos` pueden salir vacíos/0 si el texto fuente no los menciona explícitamente — esperado, no se inventan datos.
- **Pendiente, bajo impacto**: la deduplicación es solo por `url_origen` exacto — una "corrección de errores" republicada bajo otra URL para la misma plaza crearía una fila duplicada. No corregido, ver [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md).
