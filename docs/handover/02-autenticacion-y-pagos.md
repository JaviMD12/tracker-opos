← [handover.md](../../handover.md)

# 2. Autenticación y pagos (is_pro real)

## Autenticación multitenant
- `POST /api/auth/registro`, `POST /api/auth/login` (OAuth2 password flow, JWT 7 días).
- `GET /api/auth/google/login` / `.../google/callback`: login con Google vía Authlib.
- `POST /api/auth/olvido-password` / `.../reset-password`: token firmado (itsdangerous, 15 min), mensaje genérico anti-enumeración. El envío real del email depende de `WEBHOOK_RECUPERACION_URL`, que hoy apunta a **webhook.site** (no envía correos de verdad — ver [07-deuda-tecnica-y-pendientes.md](07-deuda-tecnica-y-pendientes.md)).
- Todos los routers de datos exigen `Depends(get_current_user)` y filtran por `usuario_id` (patrón obligatorio para routers nuevos, ver [08-convenciones-de-codigo.md](08-convenciones-de-codigo.md)).

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
- El botón **"Simular pago" (dev)** solo hace `localStorage.setItem(...)` — nunca toca el backend, nunca llama al webhook. Sirve solo para ver la UI desbloqueada visualmente, **no** para probar la protección real.
- Para probar de verdad la gating de Plan Pro (Tablón, Tutor IA, Simulacros), hay que completar un checkout real (`stripe listen` + tarjeta de test `4242 4242 4242 4242`) o firmar un evento de prueba a mano contra `/api/pagos/webhook`.

### El patrón de seguridad en cascada, ya aplicado a: Tablón, Tutor IA (plan de estudio), Simulacros
Todos siguen el mismo patrón:
- El **frontend** usa `proEstaDesbloqueado()` (localStorage) solo para decidir qué UI mostrar (evita enseñar un generador inútil a quien no puede usarlo).
- El **backend** es la única protección real: `if not current_user.is_pro: raise HTTPException(403, ...)`.
- Esto se descubrió/reforzó explícitamente al construir el Tablón de Convocatorias: sin el webhook real, el 403 del backend se disparaba SIEMPRE aunque el frontend mostrara "desbloqueado" — ver [05-tablon-convocatorias-scraper.md](05-tablon-convocatorias-scraper.md) para el caso de uso completo.
