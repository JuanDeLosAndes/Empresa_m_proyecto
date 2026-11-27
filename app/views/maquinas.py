from fastapi import Request

from app.models.catalogo_fotos import ImagenCategoria


def urls_de_imagenes(request: Request, imagenes: dict[str, ImagenCategoria]) -> dict[str, dict]:
    """Traduce lo que decidió el Modelo (origen + ruta) a la URL que pinta la plantilla."""
    resultado: dict[str, dict] = {}
    for nombre, imagen in imagenes.items():
        if imagen.origen == "media":
            url = request.url_for("imagen_maquina", archivo=imagen.ruta)
        else:
            url = request.url_for("static", path=imagen.ruta)
        resultado[nombre] = {"url": url.path, "foto": imagen.es_foto}
    return resultado


def filas_tecnicas(maquina, documento):
    if maquina.ficha_tecnica:
        return [{"etiqueta": k, "valor": v} for k, v in maquina.ficha_tecnica.items()]
    if documento and documento.cuadro_info:
        return documento.cuadro_info
    datos = {"Marca": maquina.marca, "Modelo": maquina.modelo, "Categoría": maquina.nombre_categoria,
             "Placa": maquina.placa, "Capacidad": maquina.capacidad, "Descripción": maquina.descripcion}
    return [{"etiqueta": k, "valor": v} for k, v in datos.items() if v]