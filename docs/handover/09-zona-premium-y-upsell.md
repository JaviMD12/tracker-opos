← [handover.md](../../handover.md)

# 9. Zona Premium (rediseño de navegación) y componentes de upsell Free→Premium

Archivo nuevo — todo lo de aquí es de la sesión del 2026-08-02. Antes de esto, la Zona Premium era una única página larga con todo apilado (gráfica, entrenamiento, técnicas de estudio, tablón, chat, simulacros) y el Dashboard gratuito no tenía ningún gancho de conversión hacia el Plan Pro.

## Rediseño de la Zona Premium: de página larga a 3 sub-vistas con pestañas
A petición explícita del usuario (rol "Frontend Senior UX/UI"), la Zona Premium (`#view-premium` en `frontend/index.html`) se dividió en 3 sub-vistas con su propia sub-navegación por pestañas:

- **`#premium-view-inicio`**: lo que antes era toda la página — gráfica de evolución, Entrenamiento Específico, Técnicas de Estudio, Tablón de Plazas. Sin filtro de scroll propio más allá del normal.
- **`#premium-view-tutor`**: el chat del Tutor IA, ahora a **pantalla completa estilo chat real** (ChatGPT-like): el historial de mensajes crece para ocupar toda la altura disponible, y el input queda **realmente fijo abajo** (no solo `position: sticky`, que es poco fiable combinado con scroll de página).
- **`#premium-view-simulacros`**: la config/test/corrección de Simulacros, en una vista centrada (`max-w-2xl`) sin distracciones.

Sub-navegación: `.premium-tab-btn` + `data-premium-view` en cada botón, función `activarVistaPremium(nombre)` en `main.js` (análoga a la `activarVista()` ya existente para Dashboard/Guía/Premium, pero anidada un nivel más adentro).

### Cambio estructural clave: el shell pasó de scroll de página a altura fija (`h-dvh`)
Para que el input del chat quede fijo de verdad, **todo `#app-shell` cambió de `min-h-screen` (scroll de página normal) a `h-dvh overflow-hidden`**, con cada vista principal (`view-dashboard`, `view-guia`, `view-premium`) siendo `flex-1 min-h-0 overflow-y-auto` — cada una hace scroll dentro de sí misma, no la página entera. Esto afecta a las 3 vistas principales, no solo a la Zona Premium, aunque solo el Tutor IA necesitaba realmente el cambio (las otras dos simplemente pasaron de "scroll de `<body>`" a "scroll de su propio contenedor", visualmente idéntico para el usuario).

**Si en el futuro algo se ve raro con el scroll** (contenido cortado, doble scrollbar, etc.), sospechar primero de esta cadena de `flex`/`min-h-0`/`overflow-y-auto` antes de asumir que es un bug de contenido.

### Tour guiado de onboarding, adaptado
`PASOS_TOUR_PREMIUM` (`main.js`) ahora tiene un campo `vista` por paso (`inicio`/`tutor`/`simulacros`), y `pintarPasoTour()` llama a `activarVistaPremium(paso.vista)` **antes** de buscar/resaltar el elemento — antes todo era visible a la vez en la misma página, ahora cada paso vive en una sub-vista oculta hasta que se activa (buscar un elemento con `display:none` da un `getBoundingClientRect()` vacío).

### Verificado en 3 breakpoints
Desktop (1280×720/1024×768), tablet (768×1024) y móvil (375×812): sin scroll de página en ningún caso, chat con input pegado al borde inferior real del viewport en los tres, tour completo hasta el registro en backend (`tour_premium_completado`).

## 3 componentes de upsell Free → Premium (CRO)
A petición explícita del usuario (rol "Frontend Senior CRO/UX"), integrados de verdad en el **Dashboard gratuito** (`#view-dashboard`), no solo como snippets sueltos:

1. **Teaser "cristal empañado"** (`#teaser-tablon`, justo después del héroe "Analista Estratégico Global"): vista previa real de tarjetas de convocatoria, con `blur-[3px]` + `pointer-events-none` + `aria-hidden`, y un candado centrado (`#btn-teaser-tablon`) como único elemento clicable. Al pulsarlo, **abre el modal de conversión** (no navega directamente).
2. **Modal de conversión** (`#modal-paywall`, hijo directo de `<body>` para poder abrirse desde cualquier vista): título "Alcanza tu máximo rendimiento", 3 beneficios (Tutor IA 24/7, Simulacros ilimitados, Tablón en vivo), y un CTA (`#btn-modal-actualizar-premium`) que **reutiliza `iniciarCheckoutStripe()`** — checkout real de un solo clic, no una navegación intermedia a otra pantalla. Cierre por botón, backdrop, o tecla Escape (`cerrarModalPaywall()`). Transición de apertura con el mismo patrón `.show` (añadida un frame después de quitar `.hidden`, vía `requestAnimationFrame`) que ya usaban los toasts — consistente con el resto del código.
3. **Banner contextual** (`#banner-upsell-entrenamiento`, dentro de `#panel-fisico`, justo tras `#resultado`): oculto por defecto, se revela junto con el resultado del formulario de marca física (`pintarResultado()` en `main.js`) **solo si el usuario no es Pro**. Texto "¿Estancado en tus marcas?..." + CTA (`.btn-plan-ia`, clase ya existente reutilizada) que navega a la Zona Premium real (`activarVista("premium")`).

### Gating: invisibles para quien ya es Pro
Los tres se ocultan automáticamente para usuarios premium — la comprobación vive en el mismo sitio que decide el resto del estado premium (`mostrarEstadoPremium()`), para no tener una segunda fuente de verdad sobre "es Pro o no".

### Verificado
Apertura/cierre del modal (backdrop, botón, Escape — comprobado con `dispatchEvent` directo, ya que la simulación de teclado del entorno de pruebas no siempre llega a una pestaña sin foco visual real), visibilidad condicionada al estado premium (oculto tras simular `is_pro=True`), navegación del banner a Zona Premium, responsivo en desktop y móvil.

## Checkout de Stripe probado de extremo a extremo (relacionado, detalle completo en [02](02-autenticacion-y-pagos.md))
El CTA del modal de conversión es el mismo botón que se usó para verificar el checkout real por primera vez en el proyecto — ver [02-autenticacion-y-pagos.md](02-autenticacion-y-pagos.md) para el hallazgo del hCaptcha invisible de Stripe y por qué el paso final de "Pagar" no se puede automatizar de principio a fin.
