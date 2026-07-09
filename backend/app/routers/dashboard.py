from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.marca import MarcaFisica
from app.models.simulacro import SimulacroTeorico
from app.models.usuario import Usuario
from app.schemas import DashboardGlobal
from app.services.calculo import calcular_puntuacion_completa
from app.services.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

NOTA_FISICA_MAXIMA = 10
NOTA_TEORICA_MAXIMA = 10


@router.get("/global", response_model=DashboardGlobal)
def dashboard_global(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ultima_marca = (
        db.query(MarcaFisica)
        .filter(MarcaFisica.usuario_id == current_user.id)
        .order_by(MarcaFisica.fecha.desc(), MarcaFisica.id.desc())
        .first()
    )
    ultimo_simulacro = (
        db.query(SimulacroTeorico)
        .filter(SimulacroTeorico.usuario_id == current_user.id)
        .order_by(SimulacroTeorico.fecha.desc(), SimulacroTeorico.id.desc())
        .first()
    )

    nota_fisica = None
    if ultima_marca is not None:
        resultado = calcular_puntuacion_completa(
            dominadas=ultima_marca.dominadas,
            sprint_100m=ultima_marca.sprint_100m,
            carrera_1500m=ultima_marca.carrera_1500m,
            natacion_100m=ultima_marca.natacion_100m,
        )
        nota_fisica = {
            "valor": resultado["nota_global"],
            "sobre": NOTA_FISICA_MAXIMA,
            "fecha": ultima_marca.fecha.isoformat(),
            "porcentaje": round(resultado["nota_global"] / NOTA_FISICA_MAXIMA, 4),
        }

    nota_teorica = None
    if ultimo_simulacro is not None:
        nota_teorica = {
            "valor": ultimo_simulacro.nota_calculada,
            "sobre": NOTA_TEORICA_MAXIMA,
            "fecha": ultimo_simulacro.fecha.isoformat(),
            "porcentaje": round(ultimo_simulacro.nota_calculada / NOTA_TEORICA_MAXIMA, 4),
        }

    if nota_fisica is None and nota_teorica is None:
        return DashboardGlobal(
            nota_fisica=None,
            nota_teorica=None,
            nota_global_combinada=None,
            veredicto="Registra al menos un entreno fisico y un simulacro teorico para ver tu analisis global.",
        )

    if nota_fisica is None:
        return DashboardGlobal(
            nota_fisica=None,
            nota_teorica=nota_teorica,
            nota_global_combinada=None,
            veredicto="Te falta registrar una marca fisica para calcular el veredicto del entrenador.",
        )

    if nota_teorica is None:
        return DashboardGlobal(
            nota_fisica=nota_fisica,
            nota_teorica=None,
            nota_global_combinada=None,
            veredicto="Te falta registrar un simulacro teorico para calcular el veredicto del entrenador.",
        )

    nota_global_combinada = round(
        (nota_fisica["porcentaje"] * 0.5 + nota_teorica["porcentaje"] * 0.5) * 10, 2
    )

    if nota_teorica["porcentaje"] < nota_fisica["porcentaje"]:
        veredicto = "Margen de mejora mayor en temario. Prioriza el estudio esta semana."
    elif nota_fisica["porcentaje"] < nota_teorica["porcentaje"]:
        veredicto = "Temario solido. Toca apretar en la pista y el lastre."
    else:
        veredicto = "Fisico y temario van en equilibrio. Manten el ritmo en ambos frentes."

    return DashboardGlobal(
        nota_fisica=nota_fisica,
        nota_teorica=nota_teorica,
        nota_global_combinada=nota_global_combinada,
        veredicto=veredicto,
    )


@router.get("/evolucion")
def dashboard_evolucion(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Serie temporal de la Nota Global Oposicion (fisica+teorica 50/50).

    Recorre todas las fechas con algun registro (fisico o teorico) en orden
    cronologico, arrastrando el ultimo valor conocido de cada bloque. Solo
    emite un punto una vez que ambos bloques tienen al menos un registro.
    """
    marcas = (
        db.query(MarcaFisica)
        .filter(MarcaFisica.usuario_id == current_user.id)
        .order_by(MarcaFisica.fecha.asc(), MarcaFisica.id.asc())
        .all()
    )
    simulacros = (
        db.query(SimulacroTeorico)
        .filter(SimulacroTeorico.usuario_id == current_user.id)
        .order_by(SimulacroTeorico.fecha.asc(), SimulacroTeorico.id.asc())
        .all()
    )

    marcas_por_fecha = {m.fecha: m for m in marcas}
    simulacros_por_fecha = {s.fecha: s for s in simulacros}
    todas_las_fechas = sorted(set(marcas_por_fecha) | set(simulacros_por_fecha))

    last_fisica_valor = None
    last_fisica_pct = None
    last_teorica_valor = None
    last_teorica_pct = None
    puntos = []

    for fecha in todas_las_fechas:
        marca = marcas_por_fecha.get(fecha)
        if marca is not None:
            resultado = calcular_puntuacion_completa(
                dominadas=marca.dominadas,
                sprint_100m=marca.sprint_100m,
                carrera_1500m=marca.carrera_1500m,
                natacion_100m=marca.natacion_100m,
            )
            last_fisica_valor = resultado["nota_global"]
            last_fisica_pct = last_fisica_valor / NOTA_FISICA_MAXIMA

        simulacro = simulacros_por_fecha.get(fecha)
        if simulacro is not None:
            last_teorica_valor = simulacro.nota_calculada
            last_teorica_pct = last_teorica_valor / NOTA_TEORICA_MAXIMA

        if last_fisica_pct is None or last_teorica_pct is None:
            continue

        puntos.append(
            {
                "fecha": fecha.isoformat(),
                "nota_global_combinada": round((last_fisica_pct * 0.5 + last_teorica_pct * 0.5) * 10, 2),
                "nota_fisica": round(last_fisica_valor, 2),
                "nota_teorica": round(last_teorica_valor, 2),
            }
        )

    return {"puntos": puntos}
