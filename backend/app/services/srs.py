"""Algoritmo de repeticion espaciada (SM-2 simplificado) para las Flashcards.

Version simplificada del SM-2 real (el algoritmo detras de Anki): no lleva
un contador aparte de "repeticiones correctas consecutivas" -- el modelo de
progreso (ver models/progreso_flashcard.py) solo pide intervalo_dias/
facilidad/fecha_proximo_repaso, asi que intervalo_dias hace el mismo papel
de estado acumulado: cada repaso lo multiplica por la facilidad (si fue
bien) o lo reinicia a 1 dia (si fue mal), en vez de derivarlo de un
contador de pasos aparte como hace el SM-2 original.
"""

from datetime import date, timedelta

FACILIDAD_INICIAL = 2.5
FACILIDAD_MINIMA = 1.3
FACILIDAD_MAXIMA = 3.0

# Codigos que manda el frontend en POST /api/flashcards/review.
DIFICIL = 3
MEDIO = 2
FACIL = 1


def calcular_siguiente_repaso(
    intervalo_dias: int, facilidad: float, resultado: int
) -> tuple[int, float, date]:
    """Devuelve (nuevo_intervalo_dias, nueva_facilidad, nueva_fecha_proximo_repaso)
    a partir del ultimo estado guardado y el resultado del repaso actual."""
    if resultado == DIFICIL:
        # Se olvido: vuelve a empezar desde el intervalo minimo y se penaliza
        # la facilidad, para que el siguiente ciclo de intervalos crezca mas
        # despacio que antes.
        nueva_facilidad = max(FACILIDAD_MINIMA, facilidad - 0.2)
        nuevo_intervalo = 1
    elif resultado == MEDIO:
        # Crecimiento conservador, la facilidad no se toca.
        nueva_facilidad = facilidad
        nuevo_intervalo = max(1, round(intervalo_dias * 1.2))
    elif resultado == FACIL:
        # Crecimiento multiplicativo segun la facilidad acumulada, que ademas
        # se premia un poco para que futuros repasos "Facil" crezcan mas.
        nueva_facilidad = min(FACILIDAD_MAXIMA, facilidad + 0.15)
        nuevo_intervalo = max(1, round(intervalo_dias * facilidad))
    else:
        raise ValueError(f"resultado invalido: {resultado} (debe ser 1, 2 o 3)")

    nueva_fecha = date.today() + timedelta(days=nuevo_intervalo)
    return nuevo_intervalo, nueva_facilidad, nueva_fecha
