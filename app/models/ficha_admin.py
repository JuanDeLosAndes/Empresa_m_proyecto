from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict, StringConstraints

Etiqueta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Valor = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Ficha = Annotated[dict[Etiqueta, Valor], Field(min_length=1, max_length=32)]


class EdicionMaquina(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    costo_por_hora: float = Field(ge=0, allow_inf_nan=False)
    capacidad: str = Field(default="", max_length=200)
    descripcion: str = Field(default="", max_length=4000)
    disponible: bool = True
    ficha_tecnica: Ficha | None = None


class AltaMaquina(EdicionMaquina):
    ficha_tecnica: Ficha
    marca: str = Field(min_length=1, max_length=120)
    modelo: str = Field(default="", max_length=120)
    placa: str = Field(min_length=1, max_length=50)
    id_categoria: int = Field(gt=0)
