"""
Documento de máquina (lo que se guarda en la base NoSQL) y su Builder.

Forma del documento (una máquina = un documento, imágenes incluidas):

    {
      "placa": "MC770043",
      "slug": "john-deere-200g-mc770043",
      "identidad": {"marca": ..., "modelo": ..., "categoria": ...},
      "descripcion": "...", "capacidad": "...",
      "ficha_tecnica": {"tipo": "excavadora", "datos": {...}},
      "imagenes": [{"archivo": "john-deere-200g-mc770043/01.jpg", "portada": true, ...}],
      # "archivo" es también el _id de la foto en GridFS (ver imagen_maquina_repository)
      "fuentes": [{"descripcion": "...", "url": "..."}],
      "nota_verificacion": "..."
    }

Patrón creacional aplicado: BUILDER.
Un documento tiene muchas partes (identidad, ficha, N imágenes, fuentes)
y reglas de consistencia (sin fotos repetidas, una sola portada, nombre
de archivo derivado del orden). `MaquinaDocumentoBuilder` lo arma paso a
paso con interfaz fluida y valida todo en `build()`, de modo que es
imposible guardar un documento a medio construir. Internamente delega la
creación de la ficha a FichaTecnicaFactory (Factory Method).

Principios SOLID:
- SRP: este módulo solo define y construye el documento; no sabe dónde
  se guarda (eso es del repositorio) ni cómo se dibuja (plantillas).
- OCP/DIP: el Builder depende de la fábrica de fichas, no de ninguna
  ficha concreta.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.documentos.fichas import FichaTecnica, FichaTecnicaFactory


def slugify(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


@dataclass(frozen=True)
class ImagenMaquina:
    archivo: str  # clave de la foto en GridFS (_id), p. ej. "slug/01.jpg"
    orden: int
    portada: bool
    alt: str
    vista: str
    origen: str  # nombre del archivo original enviado (trazabilidad)
    confianza: str = "alta"  # "alta" | "media": certeza de que es ESTA máquina

    def to_document(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_document(doc: dict[str, Any]) -> "ImagenMaquina":
        return ImagenMaquina(**doc)


@dataclass(frozen=True)
class FuenteDato:
    descripcion: str
    url: str = ""


@dataclass
class MaquinaDocumento:
    placa: str
    slug: str
    marca: str
    modelo: Optional[str]
    categoria: str
    descripcion: str
    capacidad: Optional[str]
    ficha: FichaTecnica
    imagenes: list[ImagenMaquina]
    fuentes: list[FuenteDato] = field(default_factory=list)
    nota_verificacion: str = ""

    @property
    def portada(self) -> Optional[ImagenMaquina]:
        return next((i for i in self.imagenes if i.portada), None)

    @property
    def cuadro_info(self) -> list[dict[str, str]]:
        return self.ficha.filas_cuadro_info()

    def to_document(self) -> dict[str, Any]:
        return {
            "placa": self.placa,
            "slug": self.slug,
            "identidad": {
                "marca": self.marca,
                "modelo": self.modelo,
                "categoria": self.categoria,
            },
            "descripcion": self.descripcion,
            "capacidad": self.capacidad,
            "ficha_tecnica": self.ficha.to_document(),
            "imagenes": [i.to_document() for i in self.imagenes],
            "fuentes": [asdict(f) for f in self.fuentes],
            "nota_verificacion": self.nota_verificacion,
        }

    @staticmethod
    def from_document(doc: dict[str, Any]) -> "MaquinaDocumento":
        identidad = doc["identidad"]
        return MaquinaDocumento(
            placa=doc["placa"],
            slug=doc["slug"],
            marca=identidad["marca"],
            modelo=identidad.get("modelo"),
            categoria=identidad["categoria"],
            descripcion=doc.get("descripcion", ""),
            capacidad=doc.get("capacidad"),
            ficha=FichaTecnicaFactory.desde_documento(doc["ficha_tecnica"]),
            imagenes=[ImagenMaquina.from_document(i) for i in doc.get("imagenes", [])],
            fuentes=[FuenteDato(**f) for f in doc.get("fuentes", [])],
            nota_verificacion=doc.get("nota_verificacion", ""),
        )


class MaquinaDocumentoBuilder:
    """Construye un MaquinaDocumento paso a paso. Reutilizable: build() reinicia."""

    def __init__(self) -> None:
        self._reiniciar()

    def _reiniciar(self) -> None:
        self._identidad: Optional[dict[str, Any]] = None
        self._descripcion = ""
        self._capacidad: Optional[str] = None
        self._ficha: Optional[FichaTecnica] = None
        self._imagenes: list[dict[str, Any]] = []
        self._fuentes: list[FuenteDato] = []
        self._nota = ""

    def con_identidad(
        self,
        placa: str,
        marca: str,
        modelo: Optional[str],
        categoria: str,
        slug: Optional[str] = None,
    ) -> "MaquinaDocumentoBuilder":
        """`slug` identifica al documento y a su carpeta de fotos. Por defecto
        se deriva de marca + modelo + placa; se puede fijar a mano cuando la
        placa todavía no se conoce, para que no cambie al corregirla."""
        self._identidad = {
            "placa": placa.strip(),
            "marca": marca.strip(),
            "modelo": modelo.strip() if modelo else None,
            "categoria": categoria.strip(),
            "slug": slugify(slug) if slug else None,
        }
        return self

    def con_descripcion(
        self, descripcion: str, capacidad: Optional[str] = None
    ) -> "MaquinaDocumentoBuilder":
        self._descripcion = descripcion.strip()
        self._capacidad = capacidad
        return self

    def con_ficha(self, tipo: str, **datos: Any) -> "MaquinaDocumentoBuilder":
        self._ficha = FichaTecnicaFactory.crear(tipo, **datos)
        return self

    def agregar_imagen(
        self,
        origen: str,
        vista: str,
        alt: str,
        portada: bool = False,
        confianza: str = "alta",
    ) -> "MaquinaDocumentoBuilder":
        if any(i["origen"] == origen for i in self._imagenes):
            raise ValueError(f"La imagen '{origen}' ya fue agregada a esta máquina")
        if confianza not in ("alta", "media"):
            raise ValueError("confianza debe ser 'alta' o 'media'")
        self._imagenes.append(
            {"origen": origen, "vista": vista, "alt": alt, "portada": portada, "confianza": confianza}
        )
        return self

    def agregar_fuente(self, descripcion: str, url: str = "") -> "MaquinaDocumentoBuilder":
        self._fuentes.append(FuenteDato(descripcion, url))
        return self

    def con_nota_verificacion(self, nota: str) -> "MaquinaDocumentoBuilder":
        self._nota = nota.strip()
        return self

    def build(self) -> MaquinaDocumento:
        if self._identidad is None:
            raise ValueError("Falta la identidad (placa, marca, modelo, categoría)")
        if not self._imagenes:
            raise ValueError(f"{self._identidad['placa']}: se necesita al menos una imagen")
        portadas = [i for i in self._imagenes if i["portada"]]
        if len(portadas) > 1:
            raise ValueError(f"{self._identidad['placa']}: solo puede haber una portada")

        slug = self._identidad["slug"] or slugify(
            f"{self._identidad['marca']} {self._identidad['modelo'] or ''} {self._identidad['placa']}"
        )
        # La portada siempre es la primera; el resto conserva el orden dado.
        ordenadas = sorted(self._imagenes, key=lambda i: not i["portada"]) if portadas else self._imagenes
        if not portadas:
            ordenadas[0] = {**ordenadas[0], "portada": True}

        imagenes = [
            ImagenMaquina(
                archivo=f"{slug}/{n:02d}.jpg",
                orden=n,
                portada=i["portada"],
                alt=i["alt"],
                vista=i["vista"],
                origen=i["origen"],
                confianza=i["confianza"],
            )
            for n, i in enumerate(ordenadas, start=1)
        ]
        ficha = self._ficha or FichaTecnicaFactory.crear("generica")
        documento = MaquinaDocumento(
            placa=self._identidad["placa"],
            slug=slug,
            marca=self._identidad["marca"],
            modelo=self._identidad["modelo"],
            categoria=self._identidad["categoria"],
            descripcion=self._descripcion,
            capacidad=self._capacidad,
            ficha=ficha,
            imagenes=imagenes,
            fuentes=list(self._fuentes),
            nota_verificacion=self._nota,
        )
        self._reiniciar()
        return documento
