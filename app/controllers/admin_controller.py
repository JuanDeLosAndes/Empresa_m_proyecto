# ======================================================================
# QUÉ HACE
#   Controlador del panel del administrador: lista de máquinas con su número de fotos
#   (/admin/maquinas) y gestión de fotos de una máquina: ver, subir, elegir portada y
#   eliminar (/admin/maquinas/{id}/fotos...).
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo exige ser administrador, lee los formularios (incluidos los bytes de los
#   archivos), llama al Modelo (GaleriaMaquinaModel) y redirige o muestra la plantilla.
#   NO valida ni procesa fotos, no decide el orden de las fotos y no importa pymongo:
#   eso es models/galeria_maquina.py.
# ======================================================================
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
    return RedirectResponse(f"/admin/maquinas/{id_maquinaria}/fotos?{query}", status_code=303)


@router.get("/maquinas")
def panel(request: Request, sesion: SesionActual = Depends(exigir_admin)):
    context = PageContextBuilder().with_title("MSPS · Panel de administración").with_sesion(sesion).build()
    context["maquinas"] = MaquinariaModel.listar()
    context["fotos_por_placa"] = crear_galeria_maquina().fotos_por_placa()
    return templates.TemplateResponse(request, "admin_maquinas.html", context)


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
    return templates.TemplateResponse(request, "admin_fotos.html", context)


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

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - Todas las rutas llevan Depends(exigir_admin) (controllers/dependencias.py).
#   - subir_fotos: lee cada archivo con UploadFile.file.read(...) y le pasa al Modelo
#     una lista (nombre, bytes); el Modelo devuelve cuántas se subieron y cuántas se
#     rechazaron. El controlador redirige con esos números en la URL.
#   - Si el Modelo lanza AlmacenNoDisponible (MongoDB caído), se redirige con
#     ?error=mongo y mensajes.py muestra el aviso.
# USA
#   app/models/ (galeria_maquina, maquinaria), app/factories.py (crear_galeria_maquina),
#   app/mensajes.py, app/builders.py, app/templating.py.
# DÓNDE SE LLAMA
#   app/__init__.py: create_app() hace app.include_router(admin_controller.router).
#   El navbar del administrador enlaza a /admin/maquinas.
# ======================================================================