from fastapi import APIRouter, Depends, HTTPException, Request

from app.views.builders import PageContextBuilder
from app.controllers.sesion import obtener_sesion_actual
from app.factories import crear_carrito, crear_catalogo_fotos
from app.views.mensajes import mensaje_de_fotos
from app.models.carrito import (
    CarritoModel, MaquinaNoEncontrada, MaquinaNoDisponible, RequiereCotizacion,
)
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.views.maquinas import filas_tecnicas, urls_de_imagenes
from app.views.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request):
    categorias = CategoriaModel.listar()
    imagenes = urls_de_imagenes(
        request,
        crear_catalogo_fotos().imagenes_por_categoria(
            [c.nombre_categoria for c in categorias], preferir_recorte=True
        ),
    )
    context = (
        PageContextBuilder()
        .with_title("MSPS · Alquiler de Maquinaria Pesada")
        .with_active_nav("Inicio")
        .with_hero(
            headline_lines=["ALQUILER", "MAQUINARIA", "PESADA."],
            subtitle="Servicio y alquiler de equipos de excavación para toda Bogotá.",
        )
        .with_category_cards(categorias, imagenes)
        .with_sesion(obtener_sesion_actual(request))
        .with_registro_ok(request.query_params.get("registro") == "ok")
        .build()
    )
    context["categorias"] = categorias
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/maquinas")
def buscar_maquinas(request: Request, categoria: str | None = None):
    catalogo = crear_catalogo_fotos()
    maquinas = MaquinariaModel.listar(categoria=categoria)
    context = (
        PageContextBuilder()
        .with_title("MSPS · Buscar Máquinas")
        .with_active_nav("Buscar Maquina")
        .with_sesion(obtener_sesion_actual(request))
        .build()
    )
    context["maquinas"] = maquinas
    context["categorias"] = CategoriaModel.listar()
    context["categoria_activa"] = categoria
    context["portadas"] = catalogo.portadas_por_placa()
    context["imagenes_categoria"] = urls_de_imagenes(
        request, catalogo.imagenes_por_categoria(sorted({m.nombre_categoria for m in maquinas}))
    )
    return templates.TemplateResponse(request, "buscar_maquinas.html", context)


@router.get("/maquina/{id}")
def detalle_maquina(
    request: Request, id: int, carrito: CarritoModel = Depends(crear_carrito)
):
    maquina = MaquinariaModel.obtener_por_id(id)
    if maquina is None:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    catalogo = crear_catalogo_fotos()
    context = (
        PageContextBuilder()
        .with_title(f"MSPS · {maquina.marca} {maquina.modelo or ''}".strip())
        .with_active_nav("Buscar Maquina")
        .with_sesion(obtener_sesion_actual(request))
        .build()
    )
    context["maquina"] = maquina
    try:
        estimacion = carrito.estimar(id, 1)
    except MaquinaNoEncontrada:
        raise HTTPException(404, "Máquina no encontrada") from None
    except (RequiereCotizacion, MaquinaNoDisponible):
        context["estimacion_inicial"] = None
    else:
        context["estimacion_inicial"] = estimacion.total
    context["ficha"] = catalogo.ficha_de(maquina.placa)
    context["filas_tecnicas"] = filas_tecnicas(maquina, context["ficha"])
    context["imagen_categoria"] = urls_de_imagenes(
        request, catalogo.imagenes_por_categoria([maquina.nombre_categoria])
    ).get(maquina.nombre_categoria)
    context["mensaje_fotos"] = mensaje_de_fotos(request.query_params)
    return templates.TemplateResponse(request, "detalle_maquina.html", context)

