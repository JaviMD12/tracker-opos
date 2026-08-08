← [handover.md](../../handover.md)

# 3. Rendimiento físico/teórico y gamificación

## Dashboard gratuito (motor de puntuación)
- `MarcaFisica` (dominadas, sprint_100m, carrera_1500m, natacion_100m) → `POST /api/marcas` → `services/calculo.py` interpola linealmente (min=5, max=10 puntos por prueba) y calcula la nota global física.
- `SimulacroTeorico` (aciertos/fallos/blancos, autoinforme manual) → `POST /api/teorica` → `(aciertos - fallos/3) / total * 10`, clampeado [0,10].
- `GET /api/dashboard/global` y `/evolucion`: nota combinada 50% física / 50% teórica + veredicto del entrenador + serie temporal para Chart.js.

## ⚠️ `Workout` — modelo activo en BD pero SIN uso desde el frontend
En una sesión se construyó un formulario dinámico (Fuerza/Carrera/Natación) que posteaba a `POST /api/workouts`, con su modelo `Workout` y router completos. **El usuario pidió revertirlo** ("quiero volver a lo de antes") y el Dashboard volvió a usar el formulario original de `MarcaFisica`. El modelo/endpoint `Workout` **se dejaron intactos en el backend** por si se retoma en el futuro, pero:
- No hay ningún botón/formulario en el frontend actual que llame a `/api/workouts`.
- El heatmap de actividad (ver abajo) cuenta `MarcaFisica`, **no** `Workout` — decisión explícita tomada porque `Workout` está inactivo.

Si en una sesión futura alguien pregunta "¿por qué hay un modelo Workout que no se usa?", esta es la razón — no es un olvido, es una reversión deliberada.

## Contenido de `RUTINAS_PRO` limpiado (marcadores `[cite: N]`)
`backend/app/services/rutinas.py` (contenido de "Entrenamiento Específico" del Plan Pro) tenía marcadores sueltos tipo `[cite: 1135]` en `descripcion_cientifica`, `detalle` y `bibliografia` — residuo de una generación con IA sobre un documento fuente, nunca resueltos a citas reales. Se quitaron todos con un regex (`\s*\[cite:[^\]]*\]` → `""`), verificando que no quedara puntuación rota. Si se añade contenido nuevo a `RUTINAS_PRO`/`TECNICAS_ESTUDIO_PRO`, poner directamente la referencia real en `bibliografia` en vez de un marcador placeholder.

## Acondicionamiento Físico Estratégico y Alto Rendimiento Teórico son gratis y viven en el Dashboard (actualizado 2026-08-08, commits `df19353`→`2cb3072`)
Estas dos secciones **ya no son exclusivas de Premium** — nunca lo fueron realmente del lado del backend (`/api/pro/entrenamiento` y `/api/pro/teorica` no exigían `is_pro`, solo sesión iniciada), y el frontend se actualizó para reflejar esa realidad:

- **`cargarAcondicionamientoDashboard()`** (`main.js`, llamada desde `mostrarApp()`) carga en el Dashboard gratuito: la gráfica de evolución (`#grafica-evolucion`), **Entrenamiento Específico real** (`#entrenamiento-contenido`, contenido de `RUTINAS_PRO` vía `/api/pro/entrenamiento`, personalizado a la prueba más floja del usuario) y **Técnicas de Estudio reales** (`#tecnicas-estudio-contenido`, `TECNICAS_ESTUDIO_PRO` vía `/api/pro/teorica`, biblioteca completa). Ambas se refrescan automáticamente tras registrar una marca nueva (`form.addEventListener("submit", ...)` llama a `cargarEntrenamientoEspecifico()` y `cargarGraficaEvolucion()` de nuevo).
- Hubo una etapa intermedia y ya superada (commit `df19353`, ~unas horas antes de `2cb3072`) donde el Dashboard tenía solo una **versión teaser** (rutina fija por prueba floja sin IA, 4 tarjetas estáticas de técnicas) mientras la versión real seguía en Premium — si se ve mencionado un "teaser gratuito" de Acondicionamiento Físico en algún sitio antiguo, es de esa etapa intermedia, ya no existe: `pintarAcondicionamientoTeaser()`, `RUTINA_TEASER_GRATIS` y las 4 tarjetas estáticas de técnicas se eliminaron del todo en `2cb3072`.
- La Zona Premium de pago real quedó reducida a Tablón de Plazas + Tutor Inteligente 24/7 + Simulacros + Modo Enfoque — ver [09-zona-premium-y-upsell.md](09-zona-premium-y-upsell.md) para el detalle completo de ese lado (incluida la pestaña renombrada y el CTA "profundiza con el Plan Pro" que ahora aparece bajo ambas secciones, dirigiendo al Tutor IA en vez de vender una versión superior de este mismo contenido).

### Orden del Dashboard gratuito (commits `ade3978`, `d954968`)
De arriba a abajo: Analista Estratégico Global (nota/veredicto) → Registrar marca del día (formulario) → Acondicionamiento Físico Estratégico (con el banner de upsell justo debajo) → Alto Rendimiento Teórico → teaser del Tablón de Plazas. El formulario va antes de Acondicionamiento Físico/la gráfica porque ambas dependen de que exista al menos un registro de marca.

## Banner de upsell contextual (Dashboard gratuito)
El banner (`#banner-upsell-entrenamiento`) **ya no está bajo el resultado del formulario de marca física** (`#resultado`) — se movió justo debajo de la sección de Acondicionamiento Físico Estratégico (`2cb3072`), y su visibilidad ya no depende de `pintarResultado()` sino que se gestiona junto con el resto del estado premium en `mostrarEstadoPremium()` (oculto por defecto, visible **solo si el usuario no es Pro**). Su CTA navega a la Zona Premium real (`activarVista("premium")`) — ver [09-zona-premium-y-upsell.md](09-zona-premium-y-upsell.md) para los otros dos componentes de conversión hermanos (teaser del tablón + modal) y el copy de precio unificado entre los tres.

## Heatmap de actividad (real, ya no mockeado)
- `GET /api/actividad/heatmap` (`backend/app/routers/actividad.py`): últimos 60 días, suma por día de `MarcaFisica` + `SesionEstudio` del usuario. Devuelve `[{"date": "YYYY-MM-DD", "intensity": N}, ...]`.
- Frontend: sección "Racha de Actividad" en el Dashboard (`#heatmap-container`, `.heatmap-cell`), ya existía con datos mock de una sesión anterior — se conectó al endpoint real en vez de duplicar un segundo widget. 3 niveles visuales: vacío `#1E293B`, tenue (1), brillante `#F97316` (2+).
- `cargarHeatmap()` en `main.js`, llamada desde `mostrarApp()`.

## `SesionEstudio` — Pomodoro con persistencia real
- Modelo `SesionEstudio` (`usuario_id`, `fecha`, `duracion_minutos`).
- `POST /api/actividad/sesion-estudio`: se llama **solo cuando termina un ciclo de TRABAJO** del Modo Enfoque (Pomodoro), nunca en un descanso. La distinción se lleva en JS con dos variables de estado (`cicloActualEsTrabajo`, `duracionCicloActualMinutos`) seteadas por los botones de trabajo/descanso.
- Esto rellena el `// Aqui en el futuro avisaremos al backend...` que llevaba pendiente desde el handover original — ya no es un pendiente, está hecho y verificado (ciclo de trabajo real de 1s forzado en pruebas, incrementó el heatmap; un descanso forzado igual, no lo incrementó).
