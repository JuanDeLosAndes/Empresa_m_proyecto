# ======================================================================
# QUÉ HACE
#   Rutas públicas que muestran páginas: '/' (portada con las categorías),
#   '/maquinas' (catálogo, con filtro ?categoria=) y '/maquina/{id}' (detalle con
#   galería y ficha técnica). Incluye el ayudante _imagenes_por_categoria, que elige
#   una imagen por categoría.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Pide datos y escoge la plantilla. No escribe SQL ni habla con MongoDB
#   directamente: usa los modelos (SQL) y los repositorios (MongoDB).
# ======================================================================
"""
Controlador (la C de MVC) de las rutas públicas de MSPS: home, catálogo
de máquinas y detalle de máquina.
"""
from fastapi import APIRouter, HTTPException, Request

from app.builders import PageContextBuilder
from app.current_user import obtener_sesion_actual
from app.factories import crear_maquina_documentos_repositorio
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.templating import templates

router = APIRouter()

# Imágenes que YA trae el proyecto, usadas como respaldo para las categorías que
# todavía no tienen ninguna máquina con fotos en MongoDB.
_RECORTES = {  # PNG con fondo transparente: lucen sobre los cuadros naranja de la portada
    "Excavadora": "/images/hero/hero-excavadora.png",
    "Retroexcavadora": "/images/hero/retrox.png",
    "Volqueta": "/images/hero/planchoin.png",
}
_FOTOS = {  # fotos completas
    "Excavadora": "/images/hero/retro.jpeg",
    "Retroexcavadora": "/images/hero/retroex.jpg",
    "Volqueta": "/images/hero/planchon.jpeg",
}


def _imagenes_por_categoria(request: Request, nombres: list[str], preferir_recorte: bool = False) -> dict:
    """Para cada categoría devuelve {"url": ..., "foto": bool} con la imagen de una
    máquina de ESA categoría (nunca de otra), o nada si no hay ninguna.

    Orden de preferencia:
      - cuadros de la portada (preferir_recorte=True): recorte transparente -> foto de MongoDB -> foto estática
      - listado y detalle: foto de MongoDB -> foto estática -> recorte
    """
    portadas = crear_maquina_documentos_repositorio().portadas_por_categoria()
    imagenes: dict[str, dict] = {}
    for nombre in nombres:
        opciones = []
        if nombre in portadas:
            opciones.append((str(request.url_for("imagen_maquina", archivo=portadas[nombre].archivo)), True))
        if nombre in _FOTOS:
            opciones.append((str(request.url_for("static", path=_FOTOS[nombre])), True))
        if nombre in _RECORTES:
            recorte = (str(request.url_for("static", path=_RECORTES[nombre])), False)
            if preferir_recorte:
                opciones.insert(0, recorte)
            else:
                opciones.append(recorte)
        if opciones:
            url, es_foto = opciones[0]
            imagenes[nombre] = {"url": url, "foto": es_foto}
    return imagenes


def _mensaje_desde_query(request: Request) -> dict | None:
    """Traduce los parámetros ?login=ok / ?registro=error, etc."""
    params = request.query_params
    if params.get("login") == "ok":
        return {"tipo": "exito", "texto": "Inicio de sesión exitoso."}
    if params.get("login") == "error":
        return {"tipo": "error", "texto": "Usuario o contraseña incorrectos."}
    if params.get("registro") == "error":
        return {"tipo": "error", "texto": "No se pudo crear la cuenta (verifica los datos)."}
    return None


@router.get("/")
def home(request: Request):
    categorias = CategoriaModel.listar()
    imagenes = _imagenes_por_categoria(
        request, [c.nombre_categoria for c in categorias], preferir_recorte=True
    )
    context = (
        PageContextBuilder()
        .with_title("MSPS · Alquiler de Maquinaria Pesada")
        .with_active_nav("Inicio")
        .with_hero(
            headline_lines=["ALQUILER", "MAQUINARIA", "PESADA."],
            subtitle="Servicio y alquiler de equipos de excavación para toda Bogotá.",
        )
        .with_categories(
            [
                {
                    "name": c.nombre_categoria,
                    "href": f"/maquinas?categoria={c.nombre_categoria}",
                    "image": imagenes.get(c.nombre_categoria, {}).get("url"),
                    "image_foto": imagenes.get(c.nombre_categoria, {}).get("foto", False),
                    "color": "#ff7020",
                }
                for c in categorias
            ]
        )
        .with_sesion(obtener_sesion_actual(request))
        .with_mensaje(_mensaje_desde_query(request))
        .with_registro_ok(request.query_params.get("registro") == "ok")
        .build()
    )
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/maquinas")
def buscar_maquinas(request: Request, categoria: str | None = None):
    maquinas = MaquinariaModel.listar(categoria=categoria)
    categorias = CategoriaModel.listar()
    context = (
        PageContextBuilder()
        .with_title("MSPS · Buscar Máquinas")
        .with_active_nav("Buscar Maquina")
        .with_sesion(obtener_sesion_actual(request))
        .build()
    )
    context["maquinas"] = maquinas
    context["categorias"] = categorias
    context["categoria_activa"] = categoria
    # Portada de cada máquina (base NoSQL de documentos), indexada por placa.
    context["portadas"] = crear_maquina_documentos_repositorio().portadas_por_placa()
    # Máquinas sin fotos propias: se muestra una foto de otra máquina de su categoría.
    context["imagenes_categoria"] = _imagenes_por_categoria(
        request, sorted({m.nombre_categoria for m in maquinas})
    )
    return templates.TemplateResponse(request, "buscar_maquinas.html", context)


@router.get("/maquina/{id}")
def detalle_maquina(request: Request, id: int):
    maquina = MaquinariaModel.obtener_por_id(id)
    if maquina is None:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    context = (
        PageContextBuilder()
        .with_title(f"MSPS · {maquina.marca} {maquina.modelo or ''}".strip())
        .with_active_nav("Buscar Maquina")
        .with_sesion(obtener_sesion_actual(request))
        .build()
    )
    context["maquina"] = maquina
    # Galería y cuadro de información: documento NoSQL (None si no tiene).
    context["ficha"] = crear_maquina_documentos_repositorio().obtener_por_placa(maquina.placa)
    # Sin fotos propias: foto de referencia de otra máquina de la misma categoría.
    context["imagen_categoria"] = _imagenes_por_categoria(
        request, [maquina.nombre_categoria]
    ).get(maquina.nombre_categoria)
    return templates.TemplateResponse(request, "detalle_maquina.html", context)

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - home(): CategoriaModel.listar() -> _imagenes_por_categoria(...) ->
#     PageContextBuilder...with_categories(...).build() -> index.html.
#   - buscar_maquinas(): MaquinariaModel.listar(categoria) (SQL con JOIN a
#     categorías) + repositorio.portadas_por_placa() (MongoDB: una portada por placa)
#     + imagen de categoría para las máquinas sin foto propia ->
#     buscar_maquinas.html.
#   - detalle_maquina(id): MaquinariaModel.obtener_por_id (404 si no existe) +
#     repositorio.obtener_por_placa(maquina.placa) (documento de MongoDB con galería
#     y ficha) -> detalle_maquina.html. El enlace entre SQL y MongoDB es la PLACA.
#   - _imagenes_por_categoria: toma portadas_por_categoria() de MongoDB; si una
#     categoría no tiene, usa las imágenes de /static/images/hero (retro.jpeg,
#     retroex.jpg, planchon.jpeg y los PNG recortados). Las URL salen de
#     request.url_for.
# USA
#   models/categoria.py, models/maquinaria.py,
#   factories.crear_maquina_documentos_repositorio, builders.py, current_user.py,
#   templating.py.
# DÓNDE SE LLAMA
#   app/__init__.py: include_router(home_controller.router).
#   El navegador: GET /, GET /maquinas y GET /maquina/N (buscar_maquinas.html navega
#   a '/maquina/' + id con JavaScript).
# ======================================================================