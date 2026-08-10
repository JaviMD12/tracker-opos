← [handover.md](../../handover.md)

# 9. Zona Premium (rediseño de navegación) y componentes de upsell Free→Premium

Rediseño de pestañas original de la sesión del 2026-08-02. **Actualizado el 2026-08-08**: una tanda de 11 commits posteriores (`f3454a1`..`f000ca9`) sacó Acondicionamiento Físico y Alto Rendimiento Teórico de Premium por completo (ahora viven gratis en el Dashboard, ver [03](03-rendimiento-fisico-teorico-gamificacion.md)) y añadió el Modo Enfoque como 4ª pestaña — la Zona Premium de pago real quedó reducida a **Tablón de Plazas + Tutor Inteligente 24/7 + Simulacros + Modo Enfoque**. Antes de la sesión del 2026-08-02, la Zona Premium era una única página larga con todo apilado y el Dashboard gratuito no tenía ningún gancho de conversión hacia el Plan Pro.

## De página larga a 4 sub-vistas con pestañas (hoy: Tablón / Tutor / Simulacros / Modo Enfoque)
La Zona Premium (`#view-premium` en `frontend/index.html`) tiene 4 sub-vistas con su propia sub-navegación por pestañas (`.premium-tab-btn` + `data-premium-view`, función `activarVistaPremium(nombre)` en `main.js`):

- **`#premium-view-inicio`** (`data-premium-view="inicio"`, pestaña rotulada **"Tablón de Plazas en Tiempo Real"**, no "Inicio" — renombrada en `ade3978` porque es lo único que queda ahí desde que Acondicionamiento Físico/Alto Rendimiento Teórico se mudaron al Dashboard gratuito en `2cb3072`). El id de la sub-vista en el HTML sigue siendo `premium-view-inicio`/`data-premium-view="inicio"` internamente — solo cambió el rótulo visible, no lo confundas con una sub-vista nueva.
- **`#premium-view-tutor`**: el chat del Tutor IA (rotulado **"Tutor Inteligente 24/7"** en el texto visible, ver más abajo), a pantalla completa estilo chat real: historial crece para ocupar toda la altura, input fijo abajo de verdad (no `position: sticky`). **Mensaje de bienvenida actualizado (2026-08-09)**: ahora menciona explícitamente que también resuelve dudas de "legislación, emergencias y materia específica de bomberos", no solo rutinas/técnicas de estudio como decía antes. Se probaron y luego se quitaron (mismo día, a petición explícita) 3 tarjetas de acción rápida bajo el mensaje de bienvenida — si se ve alguna referencia suelta a `.chat-sugerencia-card` en el historial de commits, es código que ya no existe, no hace falta reconstruirlo salvo que se pida de nuevo.
- **`#premium-view-simulacros`**: config/test/corrección de Simulacros, vista centrada (`max-w-2xl`).
- **`#premium-view-enfoque`** (nueva, `7d8c096`): el Pomodoro/Modo Enfoque, ver sección dedicada más abajo.

### Cambio estructural clave: el shell pasó de scroll de página a altura fija (`h-dvh`)
Para que el input del chat quede fijo de verdad, **todo `#app-shell` cambió de `min-h-screen` (scroll de página normal) a `h-dvh overflow-hidden`**, con cada vista principal (`view-dashboard`, `view-guia`, `view-premium`) siendo `flex-1 min-h-0 overflow-y-auto` — cada una hace scroll dentro de sí misma, no la página entera. Esto afecta a las 3 vistas principales, no solo a la Zona Premium, aunque solo el Tutor IA necesitaba realmente el cambio (las otras dos simplemente pasaron de "scroll de `<body>`" a "scroll de su propio contenedor", visualmente idéntico para el usuario).

**Si en el futuro algo se ve raro con el scroll** (contenido cortado, doble scrollbar, etc.), sospechar primero de esta cadena de `flex`/`min-h-0`/`overflow-y-auto` antes de asumir que es un bug de contenido.

### Tour guiado de onboarding, adaptado
`PASOS_TOUR_PREMIUM` (`main.js`) tiene un campo `vista` por paso, y `pintarPasoTour()` llama a `activarVistaPremium(paso.vista)` **antes** de buscar/resaltar el elemento — cada paso vive en una sub-vista oculta hasta que se activa (buscar un elemento con `display:none` da un `getBoundingClientRect()` vacío). **Sigue teniendo solo 3 pasos** (`#tour-tablon`/inicio, `#tour-tutor`/tutor, `#tour-simulacros`/simulacros) — la 4ª pestaña **Modo Enfoque no se añadió al tour** cuando se creó en `7d8c096`, no es un bug, simplemente no se ha hecho todavía.

### Verificado en 3 breakpoints
Desktop (1280×720/1024×768), tablet (768×1024) y móvil (375×812): sin scroll de página en ningún caso, chat con input pegado al borde inferior real del viewport en los tres, tour completo hasta el registro en backend (`tour_premium_completado`).

## Acondicionamiento Físico y Alto Rendimiento Teórico salieron de Premium (sesión 2026-08-02 tarde/noche, commits `df19353`→`2cb3072`)
Estas dos secciones **ya no están en la Zona Premium en absoluto** — se movieron al Dashboard gratuito, contenido real completo (no un teaser), porque sus endpoints (`/api/pro/entrenamiento`, `/api/pro/teorica`) **nunca estuvieron protegidos por `is_pro` en el backend**: la Zona Premium solo reflejaba una restricción que no existía realmente del lado del servidor. Detalle completo (incluida la breve etapa intermedia de "teaser gratuito" que existió solo entre `df19353` y `2cb3072`) en [03-rendimiento-fisico-teorico-gamificacion.md](03-rendimiento-fisico-teorico-gamificacion.md).

Consecuencias en esta zona:
- La pestaña que antes se llamaba "Dashboard / Inicio" de Premium se **renombró a "Tablón de Plazas en Tiempo Real"** (`ade3978`) porque es lo único real que queda ahí — el id/atributo interno sigue siendo `premium-view-inicio`/`data-premium-view="inicio"`, no cambió, solo el rótulo visible.
- El modal de pago y el cartel de venta de Premium (`#premium-locked`) **ya no prometen "evolución gráfica y entrenamiento específico"** como beneficio exclusivo — se corrigió en `0e54ff2` porque se habían quedado desactualizados tras `2cb3072` (seguían vendiendo algo que ya era gratis). Beneficios de pago reales listados hoy: Tablón de Plazas, Tutor Inteligente 24/7, Simulacros, Modo Enfoque.
- **✅ Eliminado (2026-08-10, commit `d1d861a`): el CTA "profundiza con el Plan Pro"** que vivía bajo la rutina de Entrenamiento Específico y bajo las Técnicas de Estudio (`htmlCtaProfundizarPremium()` en `main.js`, clase `.btn-cta-profundizar-premium`) — a petición explícita, por saturar de botones de pago la vista junto al nuevo banner de upsell contextual. Se quitó la función entera y su listener de clic (quedaban sin ningún otro uso). Flujo resultante del Dashboard gratuito: rutina generada → banner de upsell de 9,99€ → Alto Rendimiento Teórico, sin ningún botón debajo. La clase CSS `.btn-plan-ia` que usaba el botón sigue en uso en otros sitios (Tablón de convocatorias, banner de upsell), no se tocó su CSS.

## Sidebar móvil: menú hamburguesa (2026-08-10)
Por debajo de `lg`, los 4 botones del sidebar (Dashboard/Guía/Zona Premium/Cerrar sesión) no caben como fila horizontal — bug real encontrado con una captura de un iPhone real: "Zona Premium" y "Cerrar sesión" quedaban físicamente fuera del viewport, intocables. Sustituido por una barra compacta (logo + botón hamburguesa, `#btn-menu-movil`) que despliega el menú completo en columna (`#sidebar-nav`, clase propia `menu-movil-abierto`, no `hidden`/`lg:flex` de Tailwind — ver la entrada de [08-convenciones-de-codigo.md](08-convenciones-de-codigo.md) sobre el bug del CDN de Tailwind con el cascade de variantes responsive, que se descubrió arreglando justo esto: la primera versión con `hidden lg:flex` dejó el sidebar invisible también en escritorio). En `lg:` el sidebar se comporta exactamente igual que siempre. Verificado en producción real a 375px (menú se abre, navega, se cierra solo) y a 1794px (sidebar fijo, sin hamburguesa).

## Mejoras del embudo de conversión del Dashboard/login (2026-08-09)
Auditoría del embudo (login → registro → primera vista del Dashboard) encontró y corrigió, sin tocar la Zona Premium en sí:
- Meta description + Open Graph en el `<head>` (antes no había ninguno).
- Propuesta de valor visible en móvil dentro de la propia tarjeta de login (antes solo vivía en el panel lateral, oculto por CSS por debajo de 1024px — un visitante en móvil solo veía un formulario pelado, sin contexto de qué es la web).
- Precio ("Gratis para empezar · Premium desde 9,99€/mes") bajo el botón de registro, para que no se descubra el precio solo después de crear la cuenta.
- Mensaje del estado vacío del Analista Estratégico Global reescrito con instrucción clara + enlace directo (`#registrar-marca`) al formulario, en vez de dejar al usuario buscando por su cuenta.
- **Plausible instalado** (ver [01-stack-y-arquitectura.md](01-stack-y-arquitectura.md)) — antes no había ninguna forma de saber cuánta gente visita la web ni si se va sin hacer nada.

## Modo Enfoque: de overlay del sidebar a 4ª pestaña de Premium (`7d8c096`)
El Pomodoro dejó de ser un overlay a pantalla completa activado desde un botón del sidebar (`btn-activar-enfoque`, `#pantalla-enfoque`, clase `body.modo-enfoque-activo`) y pasó a ser `#premium-view-enfoque` (`data-premium-view="enfoque"`), una sub-vista más de Premium que reutiliza el mismo mecanismo de pestañas (`activarVistaPremium`). Se eliminaron el botón "Activar Modo Enfoque" del lateral, el botón "Salir del Modo Enfoque" (cambiar de pestaña cumple esa función ahora) y el CSS muerto del overlay. **Nota**: esto significa que el Modo Enfoque, que antes era accesible sin ser Pro (vivía en el sidebar, fuera de cualquier gating), **ahora vive dentro de la Zona Premium** — comprobar si esto es una restricción deliberada nueva o un efecto colateral no buscado del traslado si alguna vez se pregunta por qué el Pomodoro dejó de estar disponible para usuarios Free.

## Renombrados de copy (varios commits, `ade3978`→`f000ca9`)
- "Tutor IA" → **"Tutor Inteligente 24/7"** en todo el texto visible que quedaba (pestaña, cartel de venta, cabecera de Premium desbloqueada, CTAs de profundización) — se hizo en varias pasadas porque quedaban restos sin renombrar de una limpieza anterior.
- "Simulacros tipo test generados por IA" → **"Simulacros de examen"**, y se quitó del todo la descripción "Exámenes tipo test generados a partir del temario oficial" (`8c5dc8a`) — sonaba a generación en vivo por convocatoria cuando el banco es fijo (600 preguntas precargadas, ver [06](06-simulacros-ia.md)).
- El copy del Tutor en el modal de paywall y en el cartel de venta de Premium se reforzó con lenguaje de autoridad ("entrenado exclusivamente con temario oficial", respaldo científico) en vez de la descripción genérica anterior ("dudas legislativas y técnicas") — `ca1ee7a` y `f000ca9`.

## 3 componentes de upsell Free → Premium (CRO), copy unificado en `f3454a1`
Integrados de verdad en el **Dashboard gratuito** (`#view-dashboard`):

1. **Teaser "cristal empañado"** (`#teaser-tablon`, hoy justo después de Alto Rendimiento Teórico, tras el traslado de esas dos secciones — ya no está "justo después del héroe"): vista previa real de tarjetas de convocatoria, `blur-[3px]` + `pointer-events-none` + `aria-hidden`, candado centrado (`#btn-teaser-tablon`) como único elemento clicable, que **abre el modal de conversión**.
2. **Modal de conversión** (`#modal-paywall`, hijo directo de `<body>`): título "Alcanza tu máximo rendimiento", CTA (`#btn-modal-actualizar-premium`) que **reutiliza `iniciarCheckoutStripe()`**. Cierre por botón, backdrop, o Escape (`cerrarModalPaywall()`). El beneficio de "entrenamientos personalizados" se quitó del modal en `2cb3072` (ya no es exclusivo) y luego se corrigió el pie que decía por error "Pago único" siendo una suscripción mensual (`f3454a1`).
3. **Banner contextual** (`#banner-upsell-entrenamiento`): **ya no vive justo tras `#resultado` del formulario de marca** — se movió justo debajo de la sección de Acondicionamiento Físico Estratégico (dentro del Dashboard gratuito, tras `2cb3072`), y ahora se muestra/oculta según `is_pro` desde `mostrarEstadoPremium()` en vez de solo tras pintar un resultado nuevo.

Los tres CTAs de precio quedaron unificados al mismo texto **"Desbloquear Premium por 9,99€/mes"** con el precio destacado tipográficamente (clases estándar de Tailwind: `text-2xl font-bold` / `text-sm opacity-75`, `f3454a1`/`df19353`).

### Gating: invisibles para quien ya es Pro
Los tres se ocultan automáticamente para usuarios premium — la comprobación vive en `mostrarEstadoPremium()`, para no tener una segunda fuente de verdad sobre "es Pro o no".

## Reordenación del Dashboard gratuito (commits `ade3978`, `d954968`)
Orden final de arriba a abajo: **Analista Estratégico Global** (nota/veredicto, vuelto a colocar arriba en `d954968`) → **Registrar marca del día** (formulario) → **Acondicionamiento Físico Estratégico** (real, con el banner de upsell justo debajo) → **Alto Rendimiento Teórico** (real) → **teaser del Tablón**. La razón del orden: Acondicionamiento Físico y la gráfica de evolución dependen de que exista al menos un registro de marca, así que el formulario tiene que ir antes.

## Checkout de Stripe probado de extremo a extremo (relacionado, detalle completo en [02](02-autenticacion-y-pagos.md))
El CTA del modal de conversión es el mismo botón que se usó para verificar el checkout real por primera vez en el proyecto — ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md) para el hallazgo del hCaptcha invisible de Stripe y por qué el paso final de "Pagar" no se puede automatizar de principio a fin.
