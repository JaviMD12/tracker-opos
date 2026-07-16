# Handover — Tracker Analítico de Oposiciones

**Fecha del corte:** 2026-07-15
**Propósito:** punto de entrada único para retomar el proyecto en una sesión nueva sin contexto previo. Sustituye a los antiguos `HANDOVER.md` y `handover_v2.md` (su contenido está absorbido y actualizado en la estructura de abajo).

**Cómo usar este documento:** este archivo es solo el índice. El detalle real vive en `docs/handover/`, dividido por subsistema para que cada sesión pueda cargar solo lo que necesita en vez de un único archivo gigante. Cada archivo enlaza de vuelta aquí arriba y a los demás archivos relacionados — sigue los links en vez de buscar todo en un solo sitio.

---

## Resumen en una frase

SaaS FastAPI + SQLite/Postgres + frontend Vanilla JS para opositores a bombero/emergencias (foco Huelva/Andalucía): auth multitenant con `is_pro` ahora activado por un **webhook real de Stripe** (ya no solo `localStorage`), dashboard gratuito de rendimiento físico/teórico con **heatmap de actividad real**, y un Plan Pro con **Tutor IA (RAG persistido en disco)**, **Tablón de Convocatorias scrapeado de BOE/BOJA con IA**, y **generador de Simulacros tipo test con IA** — todo protegido de verdad por 403 en el backend, no solo por UI.

## Índice

| Archivo | Contenido |
|---|---|
| [01-stack-y-arquitectura.md](docs/handover/01-stack-y-arquitectura.md) | Stack tecnológico completo, estructura de carpetas backend/frontend |
| [02-autenticacion-y-pagos.md](docs/handover/02-autenticacion-y-pagos.md) | Auth multitenant, y el cambio clave: `is_pro` vía webhook real de Stripe |
| [03-rendimiento-fisico-teorico-gamificacion.md](docs/handover/03-rendimiento-fisico-teorico-gamificacion.md) | MarcaFisica/SimulacroTeorico, el modelo `Workout` inactivo, heatmap real, Pomodoro con persistencia |
| [04-tutor-ia-y-rag.md](docs/handover/04-tutor-ia-y-rag.md) | RAG compartido (chat, plan de estudio, simulacros), persistencia de Chroma en disco, saneado Unicode |
| [05-tablon-convocatorias-scraper.md](docs/handover/05-tablon-convocatorias-scraper.md) | Scraper BOE/BOJA, filtro de palabras clave/prohibidas, deep scraping, cron |
| [06-simulacros-ia.md](docs/handover/06-simulacros-ia.md) | Generador de exámenes tipo test con IA, flujo de 3 pasos |
| [07-deuda-tecnica-y-pendientes.md](docs/handover/07-deuda-tecnica-y-pendientes.md) | **Leer antes de desplegar** — bloqueantes ordenados por impacto |
| [08-convenciones-de-codigo.md](docs/handover/08-convenciones-de-codigo.md) | Reglas de estilo/estructura, y confusiones repetidas a evitar |

## Los 3 bloqueantes más urgentes ahora mismo

1. 🔴 `DOMINIO_APP` hardcodeado a `localhost` — rompe todo en cuanto se despliegue (detalle en [07](docs/handover/07-deuda-tecnica-y-pendientes.md)).
2. 🔴 Credenciales reales sin `.gitignore` en la raíz del repo (`Internal Database URL.txt`, `client_secret_...json`) — riesgo de exposición si se hace `git add -A` sin mirar (detalle en [07](docs/handover/07-deuda-tecnica-y-pendientes.md)).
3. 🟠 Nunca desplegado de verdad en Render, ni probado Google login/Stripe checkout con datos reales de extremo a extremo (detalle en [07](docs/handover/07-deuda-tecnica-y-pendientes.md)).

## Qué está verificado end-to-end (no solo "debería funcionar")

- Auth completo (registro/login/Google estructural/recuperación), aislamiento multitenant.
- `is_pro` activado por un webhook de Stripe real firmado correctamente (no solo simulado en cliente).
- Dashboard físico/teórico + heatmap de actividad combinando marcas y sesiones de estudio reales.
- Tutor IA (chat, plan de estudio por convocatoria, generador de simulacros) con RAG sobre ~20 documentos reales de temario, persistido en disco.
- Scraper de BOE/BOJA con datos reales (Consorcio de Bomberos de Huelva incluido), filtro de ruido, deep scraping.

Ver cada archivo de `docs/handover/` para el detalle de cómo se verificó cada pieza.
