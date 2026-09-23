"""
Controlador (la C de MVC) de las rutas públicas de MSPS: home, catálogo
de máquinas y detalle de máquina.

El controlador solo orquesta: le pide a los Modelos los datos, le pide
al Builder el contexto de la página y se lo entrega al motor de
plantillas (Singleton). No conoce los detalles de cómo se arma cada
formulario, cómo se configura Jinja, ni contiene SQL.

Antes, buscar_maquinas.html y detalle_maquina.html tenían máquinas
"de mentira" escritas directamente en el HTML (violación de MVC: la
Vista no debe cargar datos de negocio). Ahora esos datos salen de
MaquinariaModel / CategoriaModel, que a su vez leen de la base SQLite.
"""
from fastapi import APIRouter, HTTPException, Request

from app.builders import PageContextBuilder
from app.current_user import obtener_sesion_actual
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.templating import templates

router = APIRouter()


def _mensaje_desde_query(request: Request) -> dict | None:
    """Traduce los parámetros ?login=ok / ?registro=error, etc. (que
    ponen los redirects de auth_controller) en un mensaje para la
    plantilla. Es una decisión de presentación, así que vive en el
    Controlador, no en el Modelo."""
    params = request.query_params
    if params.get("login") == "ok":
        return {"tipo": "exito", "texto": "Inicio de sesión exitoso."}
    if params.get("login") == "error":
        return {"tipo": "error", "texto": "Usuario o contraseña incorrectos."}
    if params.get("registro") == "ok":
        return {"tipo": "exito", "texto": "Cuenta creada correctamente."}
    if params.get("registro") == "error":
        return {"tipo": "error", "texto": "No se pudo crear la cuenta (verifica los datos)."}
    return None


@router.get("/")
def home(request: Request):
    categorias = CategoriaModel.listar()
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
                    "image": None,
                    "color": "#ff7020",
                }
                for c in categorias
            ]
        )
        .with_sesion(obtener_sesion_actual(request))
        .with_mensaje(_mensaje_desde_query(request))
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
    return templates.TemplateResponse(request, "detalle_maquina.html", context)