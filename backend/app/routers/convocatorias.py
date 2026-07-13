from fastapi import APIRouter, Depends, HTTPException

from app.models.usuario import Usuario
from app.schemas import ConvocatoriaOut
from app.services.security import get_current_user

router = APIRouter(prefix="/api/convocatorias", tags=["convocatorias"])

# TODO: sustituir por un scraper/lector real de BOE/BOJA. Por ahora, datos de
# ejemplo para poder construir y probar el Tablon de extremo a extremo.
_CONVOCATORIAS_MOCK = [
    {
        "titulo": "Bombero/a - Consorcio Provincial de Bomberos de Huelva",
        "organismo": "Diputacion de Huelva (BOJA)",
        "localidad": "Huelva",
        "dias_plazo": 12,
        "requisitos": ["Titulo de Bachiller o Tecnico", "Permiso C+E", "Prueba fisica eliminatoria"],
    },
    {
        "titulo": "Bombero/a Conductor - Ayuntamiento de Sevilla",
        "organismo": "Ayuntamiento de Sevilla (BOE)",
        "localidad": "Sevilla",
        "dias_plazo": 20,
        "requisitos": ["Permiso C", "Certificado de aptitud psicofisica", "Natacion 100m"],
    },
    {
        "titulo": "Bombero/a Forestal - Plan INFOCA",
        "organismo": "Junta de Andalucia (BOJA)",
        "localidad": "Cordoba",
        "dias_plazo": 7,
        "requisitos": ["Carnet de conducir B", "Disponibilidad campaña de verano"],
    },
]


@router.get("", response_model=list[ConvocatoriaOut])
def listar_convocatorias(current_user: Usuario = Depends(get_current_user)):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")
    return _CONVOCATORIAS_MOCK
