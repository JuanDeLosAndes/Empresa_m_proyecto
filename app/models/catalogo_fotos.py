
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional

from app.documentos.maquina_documento import ImagenMaquina, MaquinaDocumento

if TYPE_CHECKING:
    from app.repositories.maquina_documentos_repository import MaquinaDocumentosLector

# PNG con fondo transparente: lucen sobre los cuadros naranja de la portada
_RECORTES = {
    "Excavadora": "/images/hero/hero-excavadora.png",
    "Retroexcavadora": "/images/hero/retrox.png",
    "Volqueta": "/images/hero/planchoin.png",
}
# Fotos completas
_FOTOS = {
    "Excavadora": "/images/hero/retro.jpeg",
    "Retroexcavadora": "/images/hero/retroex.jpg",
    "Volqueta": "/images/hero/planchon.jpeg",
}


@dataclass(frozen=True)
class ImagenCategoria:
    origen: Literal["media", "static"]  # 'media' = GridFS (MongoDB); 'static' = app/static
    ruta: str  # nombre del archivo en GridFS o ruta dentro de /static
    es_foto: bool  # False = recorte PNG transparente


class CatalogoFotosModel:
    def __init__(self, documentos: "MaquinaDocumentosLector") -> None:
        self._documentos = documentos

    def portadas_por_placa(self) -> dict[str, ImagenMaquina]:
        return self._documentos.portadas_por_placa()

    def ficha_de(self, placa: str) -> Optional[MaquinaDocumento]:
        return self._documentos.obtener_por_placa(placa)

    def imagenes_por_categoria(
        self, nombres: list[str], preferir_recorte: bool = False
    ) -> dict[str, ImagenCategoria]:
        """Por cada categoría: foto real de MongoDB, si no una foto estática, si no un recorte."""
        portadas = self._documentos.portadas_por_categoria()
        imagenes: dict[str, ImagenCategoria] = {}
        for nombre in nombres:
            opciones: list[ImagenCategoria] = []
            if nombre in portadas:
                opciones.append(ImagenCategoria("media", portadas[nombre].archivo, True))
            if nombre in _FOTOS:
                opciones.append(ImagenCategoria("static", _FOTOS[nombre], True))
            if nombre in _RECORTES:
                recorte = ImagenCategoria("static", _RECORTES[nombre], False)
                if preferir_recorte:
                    opciones.insert(0, recorte)
                else:
                    opciones.append(recorte)
            if opciones:
                imagenes[nombre] = opciones[0]
        return imagenes
# esta monda no guarda bien
