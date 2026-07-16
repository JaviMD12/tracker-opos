← [handover.md](../../handover.md)

# 7. Deuda técnica y pendientes (leer antes de desplegar)

Ordenado por impacto. 🔴 crítico, 🟠 importante, 🟡 menor.

1. **🔴 `DOMINIO_APP = "http://localhost:8000"` hardcodeado** en `routers/auth.py` y `routers/pagos.py`. Se usa para el redirect de Google OAuth, el link de recuperación de contraseña y las `success_url`/`cancel_url` de Stripe. Se romperá en cuanto se despliegue en Render. Sacarlo a variable de entorno antes de desplegar.

2. **🔴 Credenciales reales sueltas en la raíz del repo, sin `.gitignore`:**
   - `backend/Internal Database URL.txt` — URL real de Postgres de Render con usuario/contraseña en texto plano.
   - `client_secret_190520933732-....json` (raíz del proyecto) — **credenciales reales de OAuth de Google Cloud** (client ID + secret), en un archivo JSON que probablemente descargaste tú mismo desde Google Cloud Console. Ninguno de los dos está cubierto por `.gitignore` (que solo tiene `.env`, `*.db*`, `__pycache__/`, `*.pyc`, y ahora `backend/chroma_db_data/`). Si se hace `git add -A` sin mirar, ambos quedarían expuestos en el historial. Recomendación: mover ambos fuera del repo o añadirlos al `.gitignore` y regenerarlos si ya se llegaron a commitear alguna vez.

3. **🟠 Nunca desplegado de verdad en Render.** La rama Postgres de `database.py` solo está verificada a nivel de motor (dialecto, reescritura de `postgres://`), sin conexión real — este entorno de desarrollo no tiene Postgres accesible.

4. **🟠 Login con Google nunca completado en navegador real** (solo verificado estructuralmente).

5. **🟠 Checkout de Stripe nunca completado con tarjeta real** — el webhook (ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md)) sí está verificado, pero con eventos firmados a mano, no con un pago real de Stripe.

6. **🟠 `WEBHOOK_RECUPERACION_URL` apunta a webhook.site** — no envía emails reales. Sustituir antes de que la recuperación de contraseña funcione de cara al usuario final.

7. **🟠 Cron del scraper (APScheduler) y multi-worker.** Ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md) — con `gunicorn -w N` en Render, el job se dispararía N veces a las 03:00. El `UniqueConstraint` de `Convocatoria.url_origen` evita duplicados en BD pero no evita el trabajo/coste redundante.

8. **🟡 Sin Alembic / migraciones incrementales.** Cada cambio de esquema no trivial implica borrar/recrear la BD (ya pasó varias veces esta ronda de sesiones: `Workout`, `SesionEstudio`, `Convocatoria`, `ResultadoSimulacro` se añadieron así). Aceptable en desarrollo, peligroso en cuanto haya usuarios reales en producción.

9. **🟡 `bcrypt==4.0.1` fijado explícitamente** — `passlib` 1.7.4 rompe con `bcrypt>=4.1` (`AttributeError: module 'bcrypt' has no attribute '__about__'`). Si se actualiza sin querer, es esto.

10. **🟡 `chroma_db_data/` no viaja con el repo** (gitignored, ~120MB). Un `git clone` limpio necesitará 1-2 minutos en la primera petición al Tutor IA/Simulacros para reconstruir el índice — ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md). Considerar si en producción conviene pre-generar el índice como parte del build/deploy en vez de dejarlo para la primera petición real de un usuario.

11. **🟡 `Workout` inactivo en BD.** Modelo y endpoint completos pero sin ninguna UI que los llame — ver [03-rendimiento-fisico-teorico-gamificacion.md](03-rendimiento-fisico-teorico-gamificacion.md). No es un bug, es una reversión deliberada; decidir en algún momento si se retoma o se elimina.

12. **🟡 Filtro del scraper de convocatorias puede dejar pasar plazas no-bombero** cuando una resolución conjunta menciona varias categorías — ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md).

13. **🟡 Quirk del entorno de desarrollo**: el preview tool de Claude Code a veces reinicia el servidor a mitad de una petición larga (RAG/embeddings), lo que puede producir un 500 en logs que en realidad es solo una recarga del `--reload` de uvicorn interrumpiendo, no un bug del código. Si se ve un traceback raro con números de línea que no cuadran, sospechar de esto antes que del código.
