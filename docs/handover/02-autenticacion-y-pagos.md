← [handover.md](../../handover.md)

# 2. Autenticación y pagos (is_pro real)

## Autenticación multitenant
- `POST /api/auth/registro`, `POST /api/auth/login` (OAuth2 password flow, JWT 7 días). **Rate-limited (2026-08-10)**: `/registro` 10/hora, `/login` 10/min, `/olvido-password` 5/hora — antes ninguno tenía freno contra fuerza bruta/credential-stuffing, mismo `limiter` de slowapi que ya protegía `/api/pro/chat`.
- `GET /api/auth/google/login` / `.../google/callback`: login con Google vía Authlib.
- `POST /api/auth/olvido-password` / `.../reset-password`: token firmado (itsdangerous, 15 min), mensaje genérico anti-enumeración. **✅ Envío real por email resuelto (2026-08-10)**: ya no depende de `WEBHOOK_RECUPERACION_URL` (webhook.site, nunca mandó nada real) — `_enviar_email_recuperacion()` en `auth.py` manda por Gmail SMTP directo, reusando las mismas variables `SMTP_SERVER/PORT/USER/PASSWORD` que ya existían para el formulario de contacto (`routers/contacto.py`). `BackgroundTask`, fallo solo registrado en el log del servidor. Verificado con un envío real confirmado por el usuario.
- Todos los routers de datos exigen `Depends(get_current_user)` y filtran por `usuario_id` (patrón obligatorio para routers nuevos, ver [08-convenciones-de-codigo.md](08-convenciones-de-codigo.md)).

## Soporte/contacto con trato diferenciado Premium/Gratuito (`routers/contacto.py`, 2026-08-10)
`POST /api/contacto/enviar` (ya existía como formulario "¿Alguna sugerencia?" del Dashboard) se amplió con un campo `asunto` y ahora ramifica según `current_user.is_pro`:
- **Premium**: se reenvía el mensaje a `EMAIL_DESTINO` marcado `[PRIORIDAD ALTA]`, `Reply-To` al propio usuario.
- **Gratuito**: NO se reenvía al admin — autorespuesta automática al usuario explicando la espera y empujando a Premium/Tutor IA. El mensaje se registra igualmente en el log del servidor (aunque no llegue al admin) para no perderlo del todo.

Mismo patrón SMTP que recuperación de contraseña (`SMTP_*` del `.env`, `BackgroundTask`). El compromiso de "primer mes gratis" del waitlist (ver abajo) y el trato Premium/Gratuito de este formulario son decisiones de negocio, no bugs — si algo parece "raro" (un usuario gratuito que nunca ve su mensaje llegar al admin), es a propósito.

## 🔴 Interruptor `ENABLE_STRIPE` — Stripe checkout PAUSADO en producción ahora mismo (2026-08-10)
**Estado operativo, no un bug**: `ENABLE_STRIPE=false` está activo en el `.env` del VPS ahora mismo. Los botones "Desbloquear Premium por 9,99€/mes" **no crean sesiones reales de Stripe** — `POST /api/pagos/checkout` devuelve `{"stripe_habilitado": false}` y el frontend (`iniciarCheckoutStripe()` en `main.js`, la única función que llaman los 2 botones reales) abre un modal de lista de espera en su lugar, en vez de redirigir a Stripe. Si alguien prueba un checkout y no pasa nada raro/no llega a Stripe, **es esto, no un fallo** — comprobar primero `grep ENABLE_STRIPE backend/.env` en el VPS antes de investigar nada más.

- **Por qué**: el usuario quiso pausar el checkout real temporalmente para medir interés/capturar leads antes de reabrir. El copy del modal se acordó explícitamente para no mentir ("Estamos reestructurando el proceso de pago..." en vez de una versión original propuesta que afirmaba falsamente una "beta privada con el cupo lleno" — Premium ya lleva pagos reales verificados, ver más abajo).
- **Para volver a Stripe real**: `sed -i '/^ENABLE_STRIPE=false$/d' backend/.env && systemctl restart tracker-opos.service`. Ningún otro cambio de código hace falta — el flag por defecto (variable ausente) deja Stripe funcionando con normalidad, así que desplegar el commit que introdujo esto (`ca1ec5c`) no cambió nada por sí solo, hizo falta añadir la variable explícitamente.
- **Modelo `Waitlist`** (`models/waitlist.py`): email único, sin FK a `Usuario` (no exige cuenta). `POST /api/waitlist` (sin auth, 5/hora, duplicado = éxito silencioso) guarda el email y dispara una autorespuesta por email (mismo patrón SMTP, asunto "Acceso Prioritario - Tutor IA Oposiciones").
- **Sin mecanismo de canje**: la promesa de "primer mes gratis" a quien se apunta es solo texto en el email/modal — no hay cupón ni flag que lo aplique automáticamente. Cuando se reactive Stripe, hay que honrar esa promesa a mano contra la tabla `waitlist`.
- **Exportar la lista** (self-service, sin SSH): `GET /api/waitlist/export.csv?token=...` genera el CSV al vuelo, protegido por `ADMIN_EXPORT_TOKEN` (`.env`, comparado con `secrets.compare_digest`, 20/hora). El token se rotó una vez (2026-08-10) porque Claude lo había generado él mismo al arreglar un error de copia/pega del usuario — el usuario lo regeneró después en un único comando atómico (sin pasos manuales de copiar/pegar) para que solo él lo conociera. Si hace falta rotarlo otra vez, dar ese mismo comando (generar+escribir+reiniciar en un solo bloque), no uno de 3 pasos manuales — el primer intento falló exactamente por eso.

## `is_pro`: de flag de cliente a webhook real de Stripe
Este es el cambio más importante de esta ronda de sesiones. Antes, "desbloquear Plan Pro" era 100% client-side (`localStorage`). Ahora:

1. `POST /api/pagos/checkout` (`backend/app/routers/pagos.py`) crea la sesión de Stripe Checkout **con `client_reference_id=str(current_user.id)`** — así el webhook puede identificar al usuario.
2. `POST /api/pagos/webhook` verifica la firma (`stripe.Webhook.construct_event`, usando **`stripe.SignatureVerificationError` importado directo**, no `stripe.error.SignatureVerificationError` — esa forma lazy dio un `UnicodeEncodeError`/bug raro con esta versión del SDK, ver commit correspondiente) y, en `checkout.session.completed`, pone `Usuario.is_pro = True` en la BD.
3. El body del evento se relee como **JSON plano** (`json.loads(payload)`), no como el `StripeObject` que devuelve el SDK — evita depender de su API de atributos anidados (`.get()` no existe en `StripeObject`, usar indexado de dict).

### `STRIPE_WEBHOOK_SECRET`
Añadida a `.env`/`.env.example`. En `.env` local hay un **placeholder de desarrollo** (`whsec_placeholder_local_dev`) que permite firmar eventos de prueba manualmente (ver método de test en el histórico de sesión, con `crypto.subtle` HMAC-SHA256 desde el navegador). Para Stripe real:
```
stripe listen --forward-to localhost:5001/api/pagos/webhook
```
y copiar el secreto que imprime a `.env`.

### ⚠️ Lo que NO activa `is_pro` de verdad
- El botón **"Simular pago" (dev)**, si sigue existiendo en alguna vista, solo hace `localStorage.setItem(...)` — nunca toca el backend, nunca llama al webhook. Sirve solo para ver la UI desbloqueada visualmente, **no** para probar la protección real.
- Para probar de verdad la gating de Plan Pro (Tablón, Tutor IA, Simulacros), hay que completar un checkout real o firmar un evento de prueba a mano contra `/api/pagos/webhook`.

### ✅ Checkout de Stripe verificado de extremo a extremo (primera vez en el proyecto)
Contra producción real (`https://opotracker.tech`, Stripe en **modo test**, `sk_test_...` confirmado antes de tocar nada): botón "Desbloquear" → sesión real de Stripe Checkout → tarjeta de prueba `4242 4242 4242 4242` → **Stripe cargó un hCaptcha invisible al detectar automatización** en el envío del pago (Claude se detuvo ahí a propósito, sin intentar sortearlo — las reglas de seguridad lo prohíben explícitamente incluso en modo test) → el usuario completó el último clic de "Pagar" él mismo → confirmado en la base de datos de producción: `is_pro=True` y `stripe_customer_id` correctamente guardados por el webhook. **Conclusión operativa**: cualquier prueba automatizada de un checkout completo de Stripe va a chocar con este mismo hCaptcha — el paso final de "Pagar" siempre va a necesitar una interacción humana real, no asumir que se puede automatizar de principio a fin.
- El Portal de Cliente de Stripe (`POST /api/pagos/portal`) **sigue sin probarse** de extremo a extremo, aunque ya se generó un `stripe_customer_id` real durante esta prueba (de una cuenta de test ya eliminada).

### El patrón de seguridad en cascada, ya aplicado a: Tablón, Tutor IA (plan de estudio), Simulacros
Todos siguen el mismo patrón:
- El **frontend** usa `proEstaDesbloqueado()` (localStorage) solo para decidir qué UI mostrar (evita enseñar un generador inútil a quien no puede usarlo).
- El **backend** es la única protección real: `if not current_user.is_pro: raise HTTPException(403, ...)`.
- Esto se descubrió/reforzó explícitamente al construir el Tablón de Convocatorias: sin el webhook real, el 403 del backend se disparaba SIEMPRE aunque el frontend mostrara "desbloqueado" — ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md) para el caso de uso completo.
