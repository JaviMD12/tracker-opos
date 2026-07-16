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

## Heatmap de actividad (real, ya no mockeado)
- `GET /api/actividad/heatmap` (`backend/app/routers/actividad.py`): últimos 60 días, suma por día de `MarcaFisica` + `SesionEstudio` del usuario. Devuelve `[{"date": "YYYY-MM-DD", "intensity": N}, ...]`.
- Frontend: sección "Racha de Actividad" en el Dashboard (`#heatmap-container`, `.heatmap-cell`), ya existía con datos mock de una sesión anterior — se conectó al endpoint real en vez de duplicar un segundo widget. 3 niveles visuales: vacío `#1E293B`, tenue (1), brillante `#F97316` (2+).
- `cargarHeatmap()` en `main.js`, llamada desde `mostrarApp()`.

## `SesionEstudio` — Pomodoro con persistencia real
- Modelo `SesionEstudio` (`usuario_id`, `fecha`, `duracion_minutos`).
- `POST /api/actividad/sesion-estudio`: se llama **solo cuando termina un ciclo de TRABAJO** del Modo Enfoque (Pomodoro), nunca en un descanso. La distinción se lleva en JS con dos variables de estado (`cicloActualEsTrabajo`, `duracionCicloActualMinutos`) seteadas por los botones de trabajo/descanso.
- Esto rellena el `// Aqui en el futuro avisaremos al backend...` que llevaba pendiente desde el handover original — ya no es un pendiente, está hecho y verificado (ciclo de trabajo real de 1s forzado en pruebas, incrementó el heatmap; un descanso forzado igual, no lo incrementó).
