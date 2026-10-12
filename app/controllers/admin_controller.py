"""Panel del administrador: gestionar las fotos de cada máquina.

Las fotos viven SOLO en MongoDB (GridFS). Aquí el administrador las sube,
elige la portada y las elimina. Todas las rutas exigen sesión de administrador.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from pymongo.errors import PyMongoError

from app.builders import PageContextBuilder
from app.current_user import SesionActual, obtener_sesion_actual
from app.documentos.galeria import (
    MAX_FOTOS_POR_MAQUINA,
    agregar,
    documento_minimo,
    foto_nueva,
    poner_portada,
    quitar,
)
from app.factories import crear_imagenes_repositorio, crear_maquina_documentos_repositorio
from app.models.maquinaria import MaquinariaModel
from app.procesar_imagen import MAX_BYTES, FotoInvalida, procesar_foto
from app.templating import templates

router = APIRouter(prefix="/admin")


def exigir_admin(request: Request) -> SesionActual:
    sesion = obtener_sesion_actual(request)
    if sesion is None:
        raise HTTPException(status_code=303, headers={"Location": "/"})  # sin sesión -> inicio
    if sesion["tipo"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo para administradores")
    return sesion


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
    documentos = crear_maquina_documentos_repositorio().listar()
    fotos_por_placa = {d.placa: len(d.imagenes) for d in documentos}
    context = PageContextBuilder().with_title("MSPS · Panel de administración").with_sesion(sesion).build()
    context["maquinas"] = MaquinariaModel.listar()
    context["fotos_por_placa"] = fotos_por_placa
    return templates.TemplateResponse(request, "admin_maquinas.html", context)


@router.get("/maquinas/{id_maquinaria}/fotos")
def pagina_fotos(request: Request, id_maquinaria: int, sesion: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    documento = crear_maquina_documentos_repositorio().obtener_por_placa(maquina.placa)
    imagenes = documento.imagenes if documento else []

    params = request.query_params
    mensaje = None
    if params.get("subidas", "").isdigit() and params.get("rechazadas", "").isdigit():
        ok, mal = int(params["subidas"]), int(params["rechazadas"])
        if mal:
            mensaje = {"tipo": "error", "texto": f"Subidas: {ok}. Rechazadas: {mal} (formato no válido, más de 10 MB o galería llena)."}
        else:
            mensaje = {"tipo": "exito", "texto": f"Fotos subidas: {ok}."}
    elif params.get("hecho") in {"portada", "eliminada"}:
        mensaje = {"tipo": "exito", "texto": "Portada actualizada." if params["hecho"] == "portada" else "Foto eliminada."}
    elif params.get("error") == "mongo":
        mensaje = {"tipo": "error", "texto": "MongoDB no respondió. No se hizo ningún cambio; inténtalo de nuevo."}

    context = PageContextBuilder().with_title(f"MSPS · Fotos de {maquina.marca}").with_sesion(sesion).build()
    context.update(
        maquina=maquina,
        imagenes=imagenes,
        cupos=max(0, MAX_FOTOS_POR_MAQUINA - len(imagenes)),
        max_fotos=MAX_FOTOS_POR_MAQUINA,
        mensaje=mensaje,
    )
    return templates.TemplateResponse(request, "admin_fotos.html", context)


@router.post("/maquinas/{id_maquinaria}/fotos")
def subir_fotos(
    id_maquinaria: int,
    archivos: list[UploadFile] = File(...),
    _: SesionActual = Depends(exigir_admin),
):
    maquina = _maquina_o_404(id_maquinaria)
    documentos = crear_maquina_documentos_repositorio()
    almacen = crear_imagenes_repositorio()
    try:
        documento = documentos.obtener_por_placa(maquina.placa)
        if documento is None:
            # Máquina que existe en SQL pero aún no tiene documento en Mongo: se crea vacío.
            documentos.insertar_si_falta(
                documento_minimo(
                    maquina.placa, maquina.marca, maquina.modelo,
                    maquina.nombre_categoria or "", maquina.descripcion, maquina.capacidad,
                )
            )
            documento = documentos.obtener_por_placa(maquina.placa)
        if documento is None:
            return _volver(id_maquinaria, error="mongo")

        lista = list(documento.imagenes)
        alt = f"{maquina.marca} {maquina.modelo or ''}".strip()
        subidas = rechazadas = 0
        for archivo in archivos:
            if not archivo.filename:
                continue  # campo de archivo vacío
            if len(lista) >= MAX_FOTOS_POR_MAQUINA:
                rechazadas += 1
                continue
            try:
                jpeg = procesar_foto(archivo.file.read(MAX_BYTES + 1))
            except FotoInvalida:
                rechazadas += 1
                continue
            nueva = foto_nueva(documento.slug, len(lista), alt, archivo.filename)
            almacen.guardar(nueva.archivo, jpeg)  # primero los bytes...
            lista = agregar(lista, nueva)
            subidas += 1
        if subidas:
            documentos.actualizar_imagenes(maquina.placa, lista)  # ...después la referencia
    except PyMongoError:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, subidas=subidas, rechazadas=rechazadas)


@router.post("/maquinas/{id_maquinaria}/fotos/portada")
def elegir_portada(id_maquinaria: int, archivo: str = Form(...), _: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    documentos = crear_maquina_documentos_repositorio()
    try:
        documento = documentos.obtener_por_placa(maquina.placa)
        if documento is not None:
            documentos.actualizar_imagenes(maquina.placa, poner_portada(documento.imagenes, archivo))
    except PyMongoError:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, hecho="portada")


@router.post("/maquinas/{id_maquinaria}/fotos/eliminar")
def eliminar_foto(id_maquinaria: int, archivo: str = Form(...), _: SesionActual = Depends(exigir_admin)):
    maquina = _maquina_o_404(id_maquinaria)
    documentos = crear_maquina_documentos_repositorio()
    try:
        documento = documentos.obtener_por_placa(maquina.placa)
        # Solo se borran fotos que pertenecen a ESTA máquina.
        if documento is not None and any(i.archivo == archivo for i in documento.imagenes):
            documentos.actualizar_imagenes(maquina.placa, quitar(documento.imagenes, archivo))  # referencia primero...
            crear_imagenes_repositorio().eliminar(archivo)  # ...luego los bytes
    except PyMongoError:
        return _volver(id_maquinaria, error="mongo")
    return _volver(id_maquinaria, hecho="eliminada")