"""Motor de calculo de puntuaciones fisicas contra el baremo oficial real.

Fuente de datos: backend/baremos_fisicas.json (Anexo 3, Decreto 36/2025,
BOP Huelva 80/2026 -- Consorcio Provincial contra Incendios y Salvamentos
de Huelva), con tramos discretos de 5 a 10 puntos, separados por sexo.
No es interpolacion continua: cada marca cae en un tramo exacto y puntua
el entero de ese tramo (asi es como el baremo oficial esta redactado, no
hay ninguna formula de interpolacion en el texto original).
"""

import json
import re
from functools import lru_cache
from pathlib import Path

RUTA_BAREMO = Path(__file__).resolve().parent.parent.parent / "baremos_fisicas.json"

# clave interna -> (clave dentro del JSON, es_prueba_de_tiempo)
# es_prueba_de_tiempo=False significa "mas alto es mejor" (dominadas);
# True significa "menos tiempo es mejor" (las otras 3).
_PRUEBAS: dict[str, tuple[str, bool]] = {
    "dominadas": ("ejercicio_1_dominadas", False),
    "sprint_100m": ("ejercicio_2_velocidad_100m", True),
    "carrera_1500m": ("ejercicio_3_resistencia_1500m", True),
    "natacion_100m": ("ejercicio_4_natacion_100m", True),
}

NOMBRES: dict[str, str] = {
    "dominadas": "Dominadas",
    "sprint_100m": "Sprint 100m lisos",
    "carrera_1500m": "Carrera 1500m",
    "natacion_100m": "Natación 100m",
}

UNIDADES: dict[str, str] = {
    "dominadas": "reps",
    "sprint_100m": "s",
    "carrera_1500m": "s",
    "natacion_100m": "s",
}

SEXOS_VALIDOS = ("hombre", "mujer")
_SEXO_A_CLAVE_JSON = {"hombre": "hombres", "mujer": "mujeres"}

_PATRON_MINUTOS_SEGUNDOS = re.compile(r"^(\d+)['´](\d+(?:,\d+)?)[”\"]?$")
_PATRON_SOLO_SEGUNDOS = re.compile(r"^(\d+(?:,\d+)?)[”\"]?$")


def _a_segundos(texto: str) -> float:
    """Convierte una marca de tiempo del baremo ("12,80"" o "5'00,00"") a
    segundos totales."""
    texto = texto.strip()
    coincidencia = _PATRON_MINUTOS_SEGUNDOS.match(texto)
    if coincidencia:
        minutos, segundos = coincidencia.groups()
        return int(minutos) * 60 + float(segundos.replace(",", "."))
    coincidencia = _PATRON_SOLO_SEGUNDOS.match(texto)
    if coincidencia:
        return float(coincidencia.group(1).replace(",", "."))
    raise ValueError(f"No se pudo interpretar la marca de tiempo del baremo: {texto!r}")


def _limite_superior_tramo(rango_texto: str) -> float:
    """Extrae el limite superior de un tramo del baremo (ej. de
    '>14,20" y <=14,50"' o de '<=12,20"' devuelve 14.50 / 12.20 en
    segundos) -- es el tiempo mas lento que todavia puntua ese tramo."""
    coincidencia = re.search(r"<=\s*(\S+)\s*$", rango_texto)
    if not coincidencia:
        raise ValueError(f"Formato de tramo no reconocido en el baremo: {rango_texto!r}")
    return _a_segundos(coincidencia.group(1))


@lru_cache(maxsize=1)
def _cargar_baremo() -> dict[str, dict[str, dict[int, float]]]:
    """Carga y parsea baremos_fisicas.json una sola vez por proceso.
    Devuelve, por prueba y por sexo, un dict {puntos: valor_limite} donde
    valor_limite es el minimo de repeticiones (dominadas) o el maximo de
    segundos (resto) que hace falta para ese numero de puntos."""
    with open(RUTA_BAREMO, encoding="utf-8") as f:
        datos = json.load(f)

    baremo: dict[str, dict[str, dict[int, float]]] = {}
    for clave, (clave_json, es_tiempo) in _PRUEBAS.items():
        entrada = datos[clave_json]
        baremo[clave] = {}
        for sexo, clave_sexo_json in _SEXO_A_CLAVE_JSON.items():
            tramos_json = entrada[clave_sexo_json]
            if es_tiempo:
                baremo[clave][sexo] = {
                    int(puntos): _limite_superior_tramo(valor) for puntos, valor in tramos_json.items()
                }
            else:
                baremo[clave][sexo] = {int(puntos): float(valor) for puntos, valor in tramos_json.items()}
    return baremo


def calcular_punto(clave: str, valor: float, sexo: str) -> int:
    """Puntuacion (0, o entero de 5 a 10) de una marca contra el tramo del
    baremo oficial que le corresponde segun sexo. 0 si no alcanza ni el
    tramo minimo (5 puntos)."""
    if sexo not in SEXOS_VALIDOS:
        raise ValueError(f"sexo debe ser 'hombre' o 'mujer', recibido: {sexo!r}")

    _, es_tiempo = _PRUEBAS[clave]
    tramos = _cargar_baremo()[clave][sexo]

    for puntos in range(10, 4, -1):
        limite = tramos[puntos]
        if es_tiempo:
            if valor <= limite:
                return puntos
        else:
            if valor >= limite:
                return puntos
    return 0


def calcular_puntuacion_completa(
    dominadas: int, sprint_100m: float, carrera_1500m: int, natacion_100m: int, sexo: str
) -> dict:
    valores = {
        "dominadas": dominadas,
        "sprint_100m": sprint_100m,
        "carrera_1500m": carrera_1500m,
        "natacion_100m": natacion_100m,
    }

    detalle = {}
    for clave, valor in valores.items():
        puntos = calcular_punto(clave, valor, sexo)
        detalle[clave] = {
            "nombre": NOMBRES[clave],
            "valor": valor,
            "unidad": UNIDADES[clave],
            "puntos": puntos,
        }

    nota_global = round(sum(d["puntos"] for d in detalle.values()) / len(detalle), 2)

    return {
        "detalle": detalle,
        "nota_global": nota_global,
        "recomendacion": _calcular_recomendacion(valores, detalle, sexo),
    }


def _calcular_recomendacion(valores: dict, detalle: dict, sexo: str) -> dict | None:
    """Identifica en que prueba es 'mas barato' ganar el siguiente punto
    entero, comparando contra el limite del SIGUIENTE tramo del baremo
    (no una interpolacion continua -- el baremo real es de tramos)."""
    baremo = _cargar_baremo()
    candidatas = []

    for clave, info in detalle.items():
        puntos_actuales = info["puntos"]
        if puntos_actuales >= 10:
            continue

        _, es_tiempo = _PRUEBAS[clave]
        tramos = baremo[clave][sexo]
        siguiente_tramo = puntos_actuales + 1 if puntos_actuales >= 5 else 5
        limite_siguiente = tramos[siguiente_tramo]
        valor_actual = valores[clave]

        distancia = (valor_actual - limite_siguiente) if es_tiempo else (limite_siguiente - valor_actual)
        distancia = max(distancia, 0.01)  # por si la marca ya cumple el limite exacto

        esfuerzo_relativo = distancia / valor_actual if valor_actual else float("inf")

        candidatas.append(
            {
                "clave": clave,
                "nombre": NOMBRES[clave],
                "puntos_actuales": puntos_actuales,
                "unidades_para_subir_1_punto": round(distancia, 2),
                "unidad": UNIDADES[clave],
                "esfuerzo_relativo": round(esfuerzo_relativo, 4),
            }
        )

    if not candidatas:
        return None

    mejor = min(candidatas, key=lambda c: c["esfuerzo_relativo"])
    return {
        "prueba_recomendada": mejor["clave"],
        "mensaje": (
            f"La prueba más 'barata' para subir tu nota es {mejor['nombre']}: "
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
