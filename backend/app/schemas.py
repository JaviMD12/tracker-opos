from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class UsuarioCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_pro: bool
    fecha_registro: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MarcaFisicaCreate(BaseModel):
    fecha: date | None = Field(default=None, description="Si se omite, se usa la fecha de hoy")
    dominadas: int = Field(ge=0, description="Repeticiones")
    sprint_100m: float = Field(gt=0, description="Segundos")
    carrera_1500m: int = Field(gt=0, description="Segundos totales")
    natacion_100m: int = Field(gt=0, description="Segundos totales")


class MarcaFisicaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    dominadas: int
    sprint_100m: float
    carrera_1500m: int
    natacion_100m: int


class MarcaFisicaCalculada(BaseModel):
    marca: MarcaFisicaOut
    detalle: dict
    nota_global: float
    recomendacion: dict | None


class SimulacroTeoricoCreate(BaseModel):
    fecha: date | None = Field(default=None, description="Si se omite, se usa la fecha de hoy")
    aciertos: int = Field(ge=0)
    fallos: int = Field(ge=0)
    blancos: int = Field(ge=0)


class SimulacroTeoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    aciertos: int
    fallos: int
    blancos: int
    nota_calculada: float


class SimulacroTeoricoCalculado(BaseModel):
    simulacro: SimulacroTeoricoOut
    nota_calculada: float


class DashboardGlobal(BaseModel):
    nota_fisica: dict | None
    nota_teorica: dict | None
    nota_global_combinada: float | None
    veredicto: str
