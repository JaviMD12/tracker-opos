← [handover.md](../../handover.md)

# 7. Deuda técnica y pendientes (leer antes de tocar producción)

Ordenado por impacto. 🔴 crítico, 🟠 importante, 🟡 menor, ✅ resuelto (se deja el punto para que quede constancia de que ya no aplica).

0. **🔴 Nuevo, sin resolver (2026-08-08): el índice local de Chroma está incompleto/roto tras chocar con la cuota de embeddings de Gemini.** Al reconstruir `chroma_db_data/` tras añadir el BOJA25-032-00076 (Decreto 36/2025) a `conocimiento/`, `Chroma.from_documents()` reventó dos veces con `google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED` (límite `EmbedContentRequestsPerMinutePerProjectPerModel-PaidTier2`, 5000/min) antes de terminar los 38 documentos — la carga se hace de golpe, sin backoff ni reintento por lotes. `_indice_persistido_existe()` solo comprueba que la carpeta no esté vacía, así que un índice parcial se sirve como si estuviera completo, sin error visible: el Tutor IA/Simulacros tendrían lagunas silenciosas sobre los documentos que faltan. Detalle completo en [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md). **No tocar el índice del VPS hasta resolver esto en local** (nunca reconstruir en los dos sitios a la vez, la cuota es por minuto). Arreglo real pendiente: trocear la reconstrucción en lotes con pausas, no solo reintentar sin más a ver si esta vez no choca con la cuota.

1. ✅ **`DOMINIO_APP` hardcodeado — resuelto.** Ya se lee de `os.environ.get("DOMINIO_APP", "https://opotracker.tech")` en `auth.py` y `pagos.py`, con el dominio real como fallback. Confirmado en código, no solo de oídas.

2. **🔴 Credenciales reales sueltas en la raíz del repo, sin `.gitignore` — SIGUE sin resolver, verificado de nuevo en esta sesión:**
   - `backend/Internal Database URL.txt` — sigue existiendo y sigue trackeado en git (`git ls-files` lo confirma). Puede que ya ni sea la URL correcta (la producción real ahora es un VPS de Hostinger, no la Postgres que sea que describiera ese archivo), pero el archivo sigue expuesto en el historial igualmente.
   - `client_secret_190520933732-....json` (raíz del proyecto) — **credenciales reales de OAuth de Google Cloud**, confirmado que sigue existiendo, sin `.gitignore`, y **trackeado en git** (`git ls-files` lo confirma explícitamente esta sesión). Recomendación sigue siendo: moverlo fuera del repo o añadirlo al `.gitignore` y regenerar las credenciales si se considera comprometido (ya está en el historial de git, borrarlo del working tree no lo borra del historial).

3. ✅ **"Nunca desplegado de verdad" — resuelto, pero en Hostinger, no en Render.** El proyecto está desplegado en un VPS real (`187.55.229.111`, dominio `https://opotracker.tech`), con Postgres real en producción (confirmado `engine.dialect.name == "postgresql"`), servicio systemd `tracker-opos.service`, y se ha verificado repetidamente funcionando (RAG, banco de preguntas, scraper, checkout de Stripe). Si en algún documento viejo se sigue mencionando "Render" como destino de despliegue, está desactualizado — el proyecto nunca llegó a desplegarse en Render, se desplegó en Hostinger.

4. **🟠 Login con Google sigue sin probarse en navegador real de extremo a extremo** en esta sesión (no se tocó). Solo verificado estructuralmente en sesiones anteriores.

5. ✅ **Checkout de Stripe — resuelto, verificado de extremo a extremo con un pago real de prueba** (modo test, tarjeta `4242 4242 4242 4242`) contra producción real. Ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md) para el detalle, incluido el hallazgo de que Stripe presenta un hCaptcha invisible al detectar automatización en el envío del pago (el paso final de "Pagar" necesita una interacción humana real, no se puede automatizar de principio a fin).
   - **Nuevo pendiente menor derivado de esto**: el Portal de Cliente de Stripe (`POST /api/pagos/portal`) sigue sin probarse de extremo a extremo, aunque ya hay un `stripe_customer_id` real generado (de una cuenta de test ya eliminada).

6. **🟠 `WEBHOOK_RECUPERACION_URL` apunta a webhook.site** — no envía emails reales. No se tocó esta sesión. Sustituir antes de que la recuperación de contraseña funcione de cara al usuario final.

7. **🟠 Cron del scraper (APScheduler) y multi-worker.** No se tocó esta sesión (el foco fue la calidad de los datos que produce, ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md)). Con varios workers, cada uno crearía su propio scheduler y el job se dispararía N veces a esa hora — el `UniqueConstraint` de `Convocatoria.url_origen` evita duplicados en BD pero no evita el trabajo/coste redundante.

8. **🟡 Sin Alembic / migraciones incrementales.** No se tocó esta sesión. Cada cambio de esquema no trivial sigue implicando borrar/recrear la BD. Aceptable en desarrollo, peligroso en cuanto haya usuarios reales en producción — y ya hay usuarios/pagos reales de prueba pasando por el VPS, así que este riesgo es cada vez más real.

9. **🟡 `bcrypt==4.0.1` fijado explícitamente** — sin cambios esta sesión.

10. **🟡 `chroma_db_data/` no viaja con el repo** (gitignored, ~120MB) — sin cambios esta sesión, salvo que ahora también hay que tenerlo en cuenta en el VPS, no solo en local: si se hace un despliegue nuevo desde cero ahí, la primera petición al Tutor IA/Simulacros tardará 1-2 minutos reconstruyendo el índice. **Nuevo matiz importante**: reconstruirlo en local y en el VPS **a la vez** agota la cuota de embeddings de Gemini (es por minuto, no diaria) — ya pasó una vez esta sesión. Hacerlo siempre en serie.

11. **🟡 `Workout` inactivo en BD.** Sin cambios esta sesión.

12. **🟡 Filtro del scraper de convocatorias puede dejar pasar plazas no-bombero** cuando una resolución conjunta menciona varias categorías. Sin cambios esta sesión (se corrigieron bugs de fechas/excepciones, no el filtro de palabras clave).

13. **🟡 Deduplicación del scraper solo por `url_origen` exacto (nuevo, encontrado en el audit de esta sesión).** Una "corrección de errores" republicada bajo otra URL para la misma plaza real crearía una fila duplicada. No es un crash ni corrompe datos, es una cuestión de calidad de datos — no corregido, requeriría matching difuso por título+organismo.

14. **🟡 Quirk del entorno de desarrollo (confirmado que sigue pasando)**: el preview tool de Claude Code en esta máquina a veces resuelve el `launch.json` de otro proyecto no relacionado (`inversiones web`) en el puerto 8000 en vez del de `tracker-oposiciones`. Si pasa, arrancar el backend manualmente en otro puerto (`python -m uvicorn app.main:app --host 127.0.0.1 --port <libre>`) y navegar ahí directamente — no perder tiempo depurando el puerto 8000.

15. ✅ **`docs/handover/` estaba desactualizada tras 14 commits (2026-08-02 tarde/noche → 2026-08-08) — resuelta con esta sincronización.** Cambios cubiertos: rate limiting en el Tutor IA (slowapi, ver [04](04-tutor-ia-y-rag.md)), Acondicionamiento Físico/Alto Rendimiento Teórico movidos de Premium al Dashboard gratuito, Modo Enfoque movido del sidebar a Premium, varios renombrados de copy, reescritura de la Guía del Opositor con el Decreto 36/2025, corrección de tildes en todo el texto visible, y el BOJA25-032-00076 añadido a `conocimiento/`. Si en el futuro se vuelve a notar que estos documentos no cuadran con el código real, es que alguna sesión hizo cambios grandes sin sincronizar esta carpeta — pedir explícitamente "sincroniza docs/handover con lo de hoy" al final de una sesión con cambios importantes.

16. ✅ **Tildes faltantes en el texto visible — resuelto (`a4f78d1`, 2026-08-02).** Frontend y varios mensajes del backend (veredictos, `HTTPException.detail`, contenido de rutinas/técnicas) llevaban tiempo sin tildes. Se dejaron intactos a propósito los identificadores que no deben llevar tilde (ids, clases CSS, claves de diccionario/JSON, los `value=` de Simulacros que el backend espera sin acentuar).

17. ✅ **Rate limiting del Tutor IA — resuelto (`7708a12`, 2026-08-02).** Ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md) para el detalle (60 peticiones/hora por usuario, fallback a IP). Nota: solo protege `/api/pro/chat`, no `routers/tutor.py` ni los scripts offline de generación del banco.
