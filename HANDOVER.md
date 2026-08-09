# Handover — Tracker Analítico de Oposiciones

**Fecha del corte:** 2026-08-08 (sincronizado sobre el corte original del 2026-08-02 + 14 commits posteriores)
**Propósito:** punto de entrada único para retomar el proyecto en una sesión nueva sin contexto previo. Sustituye a los antiguos `HANDOVER.md`, `handover_v2.md` y `handover_v3.md` (su contenido está absorbido y actualizado en la estructura de abajo) — si ves alguno de esos tres archivos sueltos en la raíz del repo, son restos de sesiones anteriores, este documento es el que manda.

**Cómo usar este documento:** este archivo es solo el índice. El detalle real vive en `docs/handover/`, dividido por subsistema para que cada sesión pueda cargar solo lo que necesita en vez de un único archivo gigante. Cada archivo enlaza de vuelta aquí arriba y a los demás archivos relacionados — sigue los links en vez de buscar todo en un solo sitio.

---

## Lo más importante antes de tocar nada

1. **El proyecto está desplegado de verdad en producción**: VPS de Hostinger (`187.55.229.111`, hostname `srv1835603`), dominio público **`https://opotracker.tech`** (live), Postgres real (no SQLite — local sigue en SQLite, son bases de datos distintas), servicio systemd `tracker-opos.service`. Esto ya **no** es un plan a futuro ni algo "nunca desplegado" — está corriendo y se ha verificado repetidamente.
2. **Acceso SSH al VPS no es persistente entre sesiones de Claude.** Se genera un par de claves dedicado en el scratchpad de cada sesión, que desaparece al empezar una nueva — hay que regenerar el par y pedirle al usuario que autorice la clave pública otra vez desde su propia terminal ya abierta en el VPS. No hay contraseña de root guardada en ningún sitio.
3. **Despliegue**: `git push` (repo `https://github.com/JaviMD12/tracker-opos.git`, rama `main`) → `git pull` por SSH en el VPS → `systemctl restart tracker-opos.service` **solo si cambió código Python** (el frontend estático se sirve en caliente, sin reiniciar).
4. **Stripe está en modo test** (`sk_test_...`) en local y en el VPS — verificar esto explícitamente antes de cualquier prueba de pago, nunca asumirlo.
5. El motor de IA es **Gemini de punta a punta** (`gemini-2.5-flash` + `models/gemini-embedding-001`) — el proyecto usó OpenAI en su día, pero ya no queda ni una referencia funcional a `openai`/`langchain-openai`/`tiktoken` en el código.

## Resumen en una frase

SaaS FastAPI + SQLite (local) / Postgres (producción real en VPS) + frontend Vanilla JS para opositores a bombero/emergencias (foco Huelva/Andalucía): auth multitenant con `is_pro` activado por un **webhook real de Stripe** (verificado con un pago de prueba completo de extremo a extremo), dashboard gratuito de rendimiento físico/teórico (con contenido real de entrenamiento/técnicas de estudio, ya no solo un teaser, más heatmap y **3 componentes de upsell hacia Premium**), y una Zona Premium en 4 pestañas — Tablón de Plazas, Tutor Inteligente 24/7 a pantalla completa, Simulacros y Modo Enfoque — con **Tutor IA en Gemini + RAG persistido en disco** (rate-limited a 60 peticiones/hora), **Tablón de Convocatorias scrapeado de BOE/BOJA** (con un bug real de fechas encontrado y corregido, más un blindaje general contra excepciones), y un **banco de 600 preguntas de Simulacro generadas con RAG acotado por tema** — todo protegido de verdad por 403 en el backend, no solo por UI.

## Índice

| Archivo | Contenido |
|---|---|
| [01-stack-y-arquitectura.md](docs/handover/01-stack-y-arquitectura.md) | Stack (Gemini, no OpenAI), estructura de carpetas, **infraestructura real del VPS y flujo de despliegue** |
| [02-autenticacion-y-pagos.md](docs/handover/02-autenticacion-y-pagos.md) | Auth multitenant, `is_pro` vía webhook real de Stripe, **checkout verificado de extremo a extremo (con el hallazgo del hCaptcha de Stripe)** |
| [03-rendimiento-fisico-teorico-gamificacion.md](docs/handover/03-rendimiento-fisico-teorico-gamificacion.md) | MarcaFisica/SimulacroTeorico, `Workout` inactivo, heatmap real, Pomodoro, **Acondicionamiento Físico/Alto Rendimiento Teórico ahora gratis en el Dashboard (ya no Premium)** |
| [04-tutor-ia-y-rag.md](docs/handover/04-tutor-ia-y-rag.md) | RAG compartido — migrado a Gemini, 38 documentos indexados (14.599 fragmentos, verificado en local y VPS), metadata `archivo` para filtrado por tema, rate limiting nuevo |
| [05-tablon-convocatorias-scraper.md](docs/handover/05-tablon-convocatorias-scraper.md) | Scraper BOE/BOJA — **bug real de fechas encontrado/corregido + blindaje general (excepciones, validación de tipos, red de seguridad)** |
| [06-simulacros-ia.md](docs/handover/06-simulacros-ia.md) | Banco precargado (no generación en vivo), RAG real acotado por tema, 6 temas, 600 preguntas generadas, **copy corregido (ya no "generado por IA")** |
| [07-deuda-tecnica-y-pendientes.md](docs/handover/07-deuda-tecnica-y-pendientes.md) | **Leer antes de tocar producción** — bloqueantes ordenados por impacto |
| [08-convenciones-de-codigo.md](docs/handover/08-convenciones-de-codigo.md) | Reglas de estilo/estructura + convenciones nuevas de despliegue/Gemini/cuotas |
| [09-zona-premium-y-upsell.md](docs/handover/09-zona-premium-y-upsell.md) | Zona Premium en **4 pestañas** (Tablón/Tutor/Simulacros/**Modo Enfoque**, nuevo), 3 componentes de upsell con copy unificado, Acondicionamiento Físico salió de Premium |

## Los bloqueantes más urgentes ahora mismo

1. 🔴 **Credenciales reales sin `.gitignore` en la raíz del repo** (`backend/Internal Database URL.txt`, `client_secret_...json`) — siguen ahí y siguen trackeadas en git, sin resolver.
2. 🟠 Login con Google sigue sin probarse en navegador real de extremo a extremo.
3. 🟠 Portal de Cliente de Stripe (`POST /api/pagos/portal`) sin probar de extremo a extremo (aunque ya se generó un `stripe_customer_id` real durante la prueba de checkout).
4. 🟠 `WEBHOOK_RECUPERACION_URL` sigue apuntando a webhook.site (no envía emails reales).

Ya **no** son bloqueantes (resueltos, con verificación real, no solo "debería funcionar"): `DOMINIO_APP` hardcodeado, despliegue nunca hecho, checkout de Stripe nunca completado con tarjeta real, y el índice de Chroma que se quedó a medias el 2026-08-08 tras chocar con la cuota de Gemini (reconstruido y verificado en local y VPS el 2026-08-09, 14.599 fragmentos/38 documentos en ambos). Detalle completo, incluidos los pendientes menores, en [07](docs/handover/07-deuda-tecnica-y-pendientes.md).

## Qué está verificado end-to-end (no solo "debería funcionar")

- Auth completo (registro/login/Google estructural/recuperación), aislamiento multitenant.
- `is_pro` activado por un **checkout real de Stripe completado hasta el final** (modo test) contra producción, no solo un webhook firmado a mano — incluye el hallazgo de que Stripe presenta un hCaptcha invisible al detectar automatización en el pago.
- Dashboard físico/teórico + heatmap de actividad + 3 componentes de upsell hacia Premium, verificados en desktop/tablet/móvil.
- Zona Premium rediseñada en 3 pestañas (Dashboard/Inicio, Tutor IA a pantalla completa, Simulacros), sin scroll de página en ningún breakpoint, tour de onboarding adaptado y verificado paso a paso.
- Tutor IA (chat, plan de estudio por convocatoria) migrado por completo a Gemini, RAG sobre 30+ documentos reales de temario, persistido en disco.
- Banco de Simulacros (600 preguntas, 6 temas) generado con RAG real acotado por tema — verificado que cada tema recupera del documento correcto y no de otros por pura similitud semántica.
- Scraper de BOE/BOJA: un bug real de fechas (convocatoria de Huelva mostrada como vigente llevando cerrada desde junio) encontrado, corregido, y blindado con una red de seguridad + manejo de excepciones en todo el pipeline — verificado con una ejecución real contra los feeds en vivo, que descartó automáticamente otra convocatoria vencida sin intervención manual.

Ver cada archivo de `docs/handover/` para el detalle de cómo se verificó cada pieza.
