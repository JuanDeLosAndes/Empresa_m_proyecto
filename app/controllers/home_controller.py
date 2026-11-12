
from fastapi import APIRouter, HTTPException, Request

from app.builders import PageContextBuilder
from app.current_user import obtener_sesion_actual
from app.factories import crear_maquina_documentos_repositorio
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.templating import templates

router = APIRouter()

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
   
    context["portadas"] = crear_maquina_documentos_repositorio().portadas_por_placa()

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

    context["ficha"] = crear_maquina_documentos_repositorio().obtener_por_placa(maquina.placa)

    context["imagen_categoria"] = _imagenes_por_categoria(
        request, [maquina.nombre_categoria]
    ).get(maquina.nombre_categoria)
    return templates.TemplateResponse(request, "detalle_maquina.html", context)

