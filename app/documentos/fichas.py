"""
Fichas técnicas de maquinaria: el "cuadro de información" de cada máquina.

Patrón creacional aplicado: FACTORY METHOD.
Cada tipo de equipo describe cosas distintas: una excavadora tiene
profundidad de excavación y capacidad de cuchara; un minicargador tiene
capacidad operativa y tipo de elevación. `FichaTecnicaFactory.crear()`
recibe el tipo y devuelve la ficha correcta, así que ni el Builder, ni
el repositorio, ni las plantillas necesitan saber qué campos tiene cada
tipo.

Principios SOLID:
- SRP: cada ficha sabe únicamente qué campos tiene y cómo mostrarlos.
- OCP: para soportar un tipo nuevo (p. ej. una volqueta) se crea una
  clase y se registra con @registrar_ficha; no se modifica nada existente.
- LSP: todas las fichas son intercambiables: la plantilla recorre
  `filas_cuadro_info()` sin importar de qué subclase venga.
"""
from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar

# (clave del campo, etiqueta que ve el usuario, unidad si el valor es numérico)
Campo = tuple[str, str, str]


def _formatear_numero(valor: float) -> str:
    """Formato colombiano: punto para miles y coma para decimales."""
    if float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
    entero, _, decimales = texto.partition(".")
    return entero.replace(",", ".") + (f",{decimales}" if decimales else "")


class FichaTecnica(ABC):
    """Producto abstracto de la fábrica.

    Regla de formato: un valor numérico se muestra con su unidad
    ("20.788 kg"); un texto se muestra tal cual, porque ya trae su
    unidad o su rango ("12.380 – 12.740 kg").
    """

    tipo: ClassVar[str]
    CAMPOS: ClassVar[tuple[Campo, ...]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "tipo") or not hasattr(cls, "CAMPOS"):
            raise TypeError(f"{cls.__name__} debe definir 'tipo' y 'CAMPOS'")

    def __init__(self, **datos: Any) -> None:
        validos = {clave for clave, _, _ in self.CAMPOS}
        desconocidos = set(datos) - validos
        if desconocidos:
            raise ValueError(
                f"Campos no válidos para una ficha '{self.tipo}': {sorted(desconocidos)}"
            )
        # Los datos que no se conocen simplemente no se guardan: el cuadro
        # de información nunca muestra filas vacías ni valores inventados.
        self._datos = {k: v for k, v in datos.items() if v not in (None, "")}

    @property
    def datos(self) -> dict[str, Any]:
        return dict(self._datos)

    def to_document(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "datos": dict(self._datos)}

    def filas_cuadro_info(self) -> list[dict[str, str]]:
        filas: list[dict[str, str]] = []
        for clave, etiqueta, unidad in self.CAMPOS:
            if clave not in self._datos:
                continue
            valor = self._datos[clave]
            if isinstance(valor, (int, float)):
                texto = _formatear_numero(valor) + (f" {unidad}" if unidad else "")
            else:
                texto = str(valor)
            filas.append({"etiqueta": etiqueta, "valor": texto})
        return filas


class FichaTecnicaFactory:
    """Creador: decide qué subclase de FichaTecnica instanciar."""

    _registro: ClassVar[dict[str, type[FichaTecnica]]] = {}

    @classmethod
    def registrar(cls, clase: type[FichaTecnica]) -> type[FichaTecnica]:
        cls._registro[clase.tipo] = clase
        return clase

    @classmethod
    def crear(cls, tipo: str, **datos: Any) -> FichaTecnica:
        try:
            clase = cls._registro[tipo]
        except KeyError:
            raise ValueError(
                f"Tipo de ficha no soportado: {tipo!r}. Disponibles: {sorted(cls._registro)}"
            ) from None
        return clase(**datos)

    @classmethod
    def desde_documento(cls, documento: dict[str, Any]) -> FichaTecnica:
        """Reconstruye la ficha a partir de lo que guardó la base de datos."""
        return cls.crear(documento["tipo"], **documento.get("datos", {}))


registrar_ficha = FichaTecnicaFactory.registrar


@registrar_ficha
class FichaExcavadora(FichaTecnica):
    tipo = "excavadora"
    CAMPOS = (
        ("motor", "Motor", ""),
        ("potencia_neta", "Potencia neta", ""),
        ("peso_operativo", "Peso operativo", "kg"),
        ("capacidad_cuchara", "Capacidad de cuchara", "m³"),
        ("profundidad_max_excavacion", "Profundidad máx. de excavación", "m"),
        ("alcance_max_suelo", "Alcance máx. a nivel del suelo", "m"),
        ("fuerza_excavacion_cuchara", "Fuerza de excavación (cuchara)", "kN"),
        ("capacidad_combustible", "Tanque de combustible", "L"),
    )


@registrar_ficha
class FichaMinicargador(FichaTecnica):
    tipo = "minicargador"
    CAMPOS = (
        ("motor", "Motor", ""),
        ("potencia_neta", "Potencia neta", ""),
        ("capacidad_operativa", "Capacidad operativa nominal", "kg"),
        ("capacidad_operativa_contrapeso", "Con contrapeso opcional", "kg"),
        ("peso_operativo", "Peso operativo", "kg"),
        ("tipo_elevacion", "Tipo de elevación", ""),
    )


@registrar_ficha
class FichaGenerica(FichaTecnica):
    """Ficha mínima para equipos cuyo tipo todavía no tiene ficha propia."""

    tipo = "generica"
    CAMPOS = (
        ("motor", "Motor", ""),
        ("potencia_neta", "Potencia neta", ""),
        ("peso_operativo", "Peso operativo", "kg"),
    )
