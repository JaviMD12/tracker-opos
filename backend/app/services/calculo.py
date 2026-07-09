"""Motor de calculo de puntuaciones fisicas por interpolacion lineal.

Baremo: el minimo exigido puntua 5, el maximo puntua 10. Por debajo del
minimo la prueba puntua 0. Nunca se superan los 10 puntos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prueba:
    clave: str
    nombre: str
    minimo: float   # valor que puntua 5
    maximo: float   # valor que puntua 10
    invertido: bool  # True si "menos es mas" (pruebas de tiempo)
    unidad: str


PRUEBAS: dict[str, Prueba] = {
    "dominadas": Prueba("dominadas", "Dominadas", 12, 30, invertido=False, unidad="reps"),
    "sprint_100m": Prueba("sprint_100m", "Sprint 100m lisos", 14.50, 12.20, invertido=True, unidad="s"),
    "carrera_1500m": Prueba("carrera_1500m", "Carrera 1500m", 366, 272, invertido=True, unidad="s"),
    "natacion_100m": Prueba("natacion_100m", "Natacion 100m", 110, 78, invertido=True, unidad="s"),
}


def _interpolar(valor: float, prueba: Prueba) -> float:
    rango = abs(prueba.maximo - prueba.minimo)
    factor = 5 / rango

    if prueba.invertido:
        # tiempos: menos segundos = mejor marca
        if valor > prueba.minimo:
            return 0.0
        if valor <= prueba.maximo:
            return 10.0
        return 5 + (prueba.minimo - valor) * factor

    if valor < prueba.minimo:
        return 0.0
    if valor >= prueba.maximo:
        return 10.0
    return 5 + (valor - prueba.minimo) * factor


def calcular_punto(clave: str, valor: float) -> float:
    puntos = _interpolar(valor, PRUEBAS[clave])
    return round(puntos, 2)


def calcular_puntuacion_completa(
    dominadas: int, sprint_100m: float, carrera_1500m: int, natacion_100m: int
) -> dict:
    valores = {
        "dominadas": dominadas,
        "sprint_100m": sprint_100m,
        "carrera_1500m": carrera_1500m,
        "natacion_100m": natacion_100m,
    }

    detalle = {}
    for clave, valor in valores.items():
        prueba = PRUEBAS[clave]
        puntos = calcular_punto(clave, valor)
        detalle[clave] = {
            "nombre": prueba.nombre,
            "valor": valor,
            "unidad": prueba.unidad,
            "puntos": puntos,
        }

    nota_global = round(sum(d["puntos"] for d in detalle.values()) / len(detalle), 2)

    return {
        "detalle": detalle,
        "nota_global": nota_global,
        "recomendacion": _calcular_recomendacion(valores, detalle),
    }


def _calcular_recomendacion(valores: dict, detalle: dict) -> dict | None:
    """Identifica en que prueba es 'mas barato' ganar el siguiente punto.

    Para cada prueba que no esta ya a 10, calcula cuanto esfuerzo fisico
    (relativo a la marca actual) hace falta para subir un punto entero, y
    recomienda la prueba con menor esfuerzo relativo.
    """
    candidatas = []
    for clave, info in detalle.items():
        prueba = PRUEBAS[clave]
        puntos_actuales = info["puntos"]
        if puntos_actuales >= 10:
            continue

        rango = abs(prueba.maximo - prueba.minimo)
        coste_por_punto = rango / 5  # unidades fisicas necesarias para +1 punto
        valor_actual = valores[clave]

        # esfuerzo relativo = cuanto hay que mover la marca actual, en
        # proporcion a la marca actual (mas bajo => "mas barato")
        esfuerzo_relativo = coste_por_punto / valor_actual if valor_actual else float("inf")

        candidatas.append(
            {
                "clave": clave,
                "nombre": prueba.nombre,
                "puntos_actuales": puntos_actuales,
                "unidades_para_subir_1_punto": round(coste_por_punto, 2),
                "unidad": prueba.unidad,
                "esfuerzo_relativo": round(esfuerzo_relativo, 4),
            }
        )

    if not candidatas:
        return None

    mejor = min(candidatas, key=lambda c: c["esfuerzo_relativo"])
    return {
        "prueba_recomendada": mejor["clave"],
        "mensaje": (
            f"La prueba mas 'barata' para subir tu nota es {mejor['nombre']}: "
            f"solo necesitas mejorar {mejor['unidades_para_subir_1_punto']} {mejor['unidad']} "
            f"para ganar 1 punto entero."
        ),
        "detalle_candidatas": candidatas,
    }


def calcular_nota_teorica(aciertos: int, fallos: int, total_preguntas: int = 100) -> float:
    """Nota sobre 10 con penalizacion de 1/3 por fallo, sobre un test de
    `total_preguntas` preguntas (100 por defecto)."""
    puntos_brutos = aciertos - (fallos / 3)
    nota = (puntos_brutos / total_preguntas) * 10
    return round(max(0.0, min(10.0, nota)), 2)
