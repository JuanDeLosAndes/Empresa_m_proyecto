from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.builders import PageContextBuilder
from app.controllers.dependencias import exigir_admin
from app.current_user import SesionActual
from app.factories import crear_galeria_maquina
from app.mensajes import mensaje_de_fotos
from app.models.galeria_maquina import AlmacenNoDisponible, GaleriaMaquinaModel
from app.models.maquinaria import MaquinariaModel
from app.templating import templates

router = APIRouter(prefix="/admin")


def _maquina_o_404(id_maquinaria: int):
    maquina = MaquinariaModel.obtener_por_id(id_maquinaria)
    if maquina is None:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    return maquina


def _volver(id_maquinaria: int, **params) -> RedirectResponse:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"/maquina/{id_maquinaria}?{query}", status_code=303)


@router.get("/maquinas")
def panel(request: Request, sesion: SesionActual = Depends(exigir_admin)):
    return RedirectResponse("/maquinas", status_code=303)


@router.get("/maquinas/{id_maquinaria}/fotos")
def pagina_fotos(request: Request, id_maquinaria: int, sesion: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    galeria = crear_galeria_maquina()
    imagenes = galeria.fotos_de(maquina)

    context = PageContextBuilder().with_title(f"MSPS · Fotos de {maquina.marca}").with_sesion(sesion).build()
    context.update(
        maquina=maquina,
        imagenes=imagenes,
        cupos=galeria.cupos_libres(imagenes),
        max_fotos=GaleriaMaquinaModel.MAX_FOTOS,
        mensaje=mensaje_de_fotos(request.query_params),
    )
    return templates.TemplateResponse(request, "components/admin_fotos.html", context)


@router.post("/maquinas/{id_maquinaria}/fotos")
def subir_fotos(
    id_maquinaria: int,
    archivos: list[UploadFile] = File(...),
    _: SesionActual = Depends(exigir_admin),
):
    maquina = _maquina_o_404(id_maquinaria)
    limite = GaleriaMaquinaModel.MAX_BYTES_POR_FOTO + 1  # un byte de más permite detectar "pesa demasiado"
    leidos = [(a.filename, a.file.read(limite)) for a in archivos if a.filename]  # sin nombre = campo vacío
    try:
        resultado = crear_galeria_maquina().subir(maquina, leidos)
    except AlmacenNoDisponible:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, subidas=resultado.subidas, rechazadas=resultado.rechazadas)


@router.post("/maquinas/{id_maquinaria}/fotos/portada")
def elegir_portada(id_maquinaria: int, archivo: str = Form(...), _: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    try:
        crear_galeria_maquina().poner_portada(maquina, archivo)
    except AlmacenNoDisponible:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, hecho="portada")


@router.post("/maquinas/{id_maquinaria}/fotos/eliminar")
def eliminar_foto(id_maquinaria: int, archivo: str = Form(...), _: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    try:
        crear_galeria_maquina().eliminar(maquina, archivo)
    except AlmacenNoDisponible:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, hecho="eliminada")



class EdicionMaquina(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    costo_por_hora: float = Field(ge=0, allow_inf_nan=False)
    capacidad: str = Field(default="", max_length=200)
    descripcion: str = Field(default="", max_length=4000)
    disponible: bool = True


class AltaMaquina(EdicionMaquina):
    marca: str = Field(min_length=1, max_length=120)
    modelo: str = Field(default="", max_length=120)
    placa: str = Field(min_length=1, max_length=50)
    id_categoria: int = Field(gt=0)


@router.post("/maquinas", status_code=201)
def crear_maquina(datos: AltaMaquina, _: SesionActual = Depends(exigir_admin)):
    try:
        maquina = MaquinariaModel.crear(**datos.model_dump())
    except ValueError as error:
        raise HTTPException(409, str(error))
    return {"id_maquinaria": maquina.id_maquinaria}


@router.put("/maquinas/{id_maquinaria}")
def actualizar_maquina(id_maquinaria: int, datos: EdicionMaquina, _: SesionActual = Depends(exigir_admin)):
    try:
        maquina = MaquinariaModel.actualizar(id_maquinaria, **datos.model_dump())
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {"id_maquinaria": maquina.id_maquinaria}


@router.delete("/maquinas/{id_maquinaria}")
def borrar_maquina(id_maquinaria: int, _: SesionActual = Depends(exigir_admin)):
    try:
        MaquinariaModel.eliminar(id_maquinaria)
    except LookupError as error:
        raise HTTPException(404, str(error))
    return {"status": "ok"}