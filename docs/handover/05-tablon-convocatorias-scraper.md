← [handover.md](../../handover.md)

# 5. Tablón de Convocatorias Premium + scraper de boletines

## Modelo y endpoint
- `Convocatoria` (`titulo_plaza`, `organismo_localidad`, `plazo_dias`, `requisitos_minimos`, `fecha_publicacion`, más `url_origen` **único** — necesario para no duplicar filas ni gastar llamadas a OpenAI de más cuando el cron reprocesa el mismo feed cada 24h).
- `GET /api/convocatorias` (`routers/convocatorias.py`): 403 si `current_user.is_pro` es falso; si no, últimas 20 convocatorias ordenadas por fecha.
- Frontend: sección "Tablón de Plazas en Tiempo Real" dentro de Plan Pro. Si 403 → tarjetas de ejemplo con `filter: blur(4px)` + cartel `.tablon-cta` (reutilizado también en el bloqueo de Simulacros IA, ver [06-simulacros-ia.md](06-simulacros-ia.md)).

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
El resumen del RSS es una frase; los datos clave (plazo, requisitos) están en el cuerpo de la resolución completa. `_obtener_texto_completo(url)` hace `requests.get()` al `entrada.link` (con `User-Agent`, algunos boletines bloquean el UA por defecto) y extrae todo el texto de los `<p>` con BeautifulSoup, recortado a 15.000 caracteres. Si la descarga falla, cae de vuelta al resumen corto del RSS en vez de abortar la entrada.

### Extracción con IA
`gpt-4o-mini` en modo JSON forzado (`response_format: json_object`), con el System Prompt exacto pedido por el usuario. Si el texto no es una convocatoria real, el modelo devuelve `{"error": "no es convocatoria"}` y se descarta.

### Cron (APScheduler, en `main.py`)
`CronTrigger(hour=3, minute=0)`, timezone `Europe/Madrid`, arrancado/parado en `@app.on_event("startup"/"shutdown")`. **Caveat de producción**: con varios workers de gunicorn, cada worker crearía su propio scheduler y el job se dispararía N veces a esa hora — el `UniqueConstraint` de `url_origen` evita duplicados en BD, pero convendría un solo worker dedicado al cron antes de escalar en Render.

## Calidad de datos — limitaciones conocidas, no bugs
- El RSS a veces agrupa varias categorías de plaza en una sola resolución (ej. "Técnico/a de Administración General..." proviene de una resolución del Consorcio de Extinción de Incendios de Toledo que en realidad también cubre otras plazas) — GPT extrae fielmente lo que hay en el texto, esto es fidelidad de la fuente, no un fallo de extracción.
- `plazo_dias`/`requisitos_minimos` pueden salir vacíos/0 si el texto fuente no los menciona explícitamente — esperado, no inventamos datos.
