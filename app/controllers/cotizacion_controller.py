from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.models import cotizacion

router = APIRouter()


class SolicitudCotizacion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id_maquinaria: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    telefono: str = Field(min_length=7, max_length=24, pattern=r"^\+?[0-9](?:[ ()-]*[0-9]){6,14}$")
    mensaje: str = Field(default="", max_length=2000)


@router.post("/cotizaciones", status_code=201)
def registrar(datos: SolicitudCotizacion):
    try:
        numero = cotizacion.registrar(**datos.model_dump())
    except LookupError as error:
        raise HTTPException(404, str(error))
    return {"id_cotizacion": numero}