← [handover.md](../../handover.md)

# 6. Simulacros IA (examen tipo test, Plan Pro)

## Backend
- `ResultadoSimulacro` (`usuario_id`, `fecha`, `tema`, `aciertos`, `total_preguntas`). **Distinto de `SimulacroTeorico`** (el autoinforme manual del dashboard gratuito, ver [03-rendimiento-fisico-teorico-gamificacion.md](03-rendimiento-fisico-teorico-gamificacion.md)) — nombres parecidos, conceptos distintos, no fusionar.
- `services/ai_tutor.py::generar_simulacro_test(tema, num_preguntas)` — RAG sobre el mismo vectorstore del Tutor IA (ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md)), `gpt-4o-mini` en modo JSON forzado.
- `routers/simulacros.py`:
  - `POST /generar`: 403 si no `is_pro`. Devuelve `{"preguntas": [{"pregunta", "opciones", "correcta", "explicacion"}]}`.
  - `POST /guardar`: persiste el resultado, sin gating adicional (solo requiere login; es autoinforme del propio usuario, bajo riesgo).

## Frontend
Vista "Simulacros IA" en el sidebar, con el mismo cartel `.tablon-cta` de bloqueo que el Tablón Premium (comparten `proEstaDesbloqueado()` para la UI; la protección real es el 403 del backend).

Flujo en 3 pasos:
1. **Config**: selects de tema (Legislación/Hidráulica/Fuego) y nº de preguntas (5/10/20).
2. **Test**: preguntas con `<input type="radio">`, generadas dinámicamente. Las preguntas quedan en memoria (`preguntasSimulacroActual`) para poder corregir sin volver a llamar al backend.
3. **Corrección**: compara cada respuesta marcada contra el índice `correcta`; pinta verde/rojo tenue, muestra `explicacion`, calcula nota sobre 10, y hace `POST /guardar` en silencio (sin bloquear la UI ni molestar al usuario si falla).

## Rendimiento esperado
La primera generación tras un reinicio del servidor puede tardar más si el vectorstore aún no está persistido (ver [04-tutor-ia-y-rag.md](04-tutor-ia-y-rag.md), CASO B ~105s). Con el índice ya en disco, generar un examen de 5 preguntas tarda ~10-12s de principio a fin, dominado por el tiempo de generación de OpenAI (no por la carga del índice).
