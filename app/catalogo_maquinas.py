"""
Catálogo real de maquinaria de MSPS (datos + Director del Builder).

Cada entrada de `_MAQUINAS` describe UNA máquina física y las fotos que
le corresponden. Las 22 fotos enviadas se agruparon por máquina física
(placa visible en el equipo, mismo sitio de obra, mismo modelo y mismo
momento de captura) y cada foto aparece exactamente una vez.

Patrón creacional: `CatalogoDirector` es el Director del patrón Builder:
conoce el orden de los pasos y los ejecuta sobre un MaquinaDocumentoBuilder
sin saber cómo se guarda ni cómo se muestra el resultado.

IMPORTANTE sobre los datos:
- Las fichas técnicas salen de fabricante/distribuidor (ver `fuentes`).
  Cuando una máquina existe en varias versiones (p. ej. Kobelco SK140LC -8
  y -10) se muestran rangos, no un valor inventado.
- `confianza="media"` en una imagen significa que corresponde al modelo,
  pero no se pudo confirmar que sea la misma unidad (la placa no se ve).
- Las tarifas NO se inventaron: complete TARIFAS_COP_POR_HORA. Mientras
  una máquina no tenga tarifa, el sitio muestra "Tarifa por cotizar".
"""
from __future__ import annotations

from typing import Any, Callable

from app.documentos.maquina_documento import MaquinaDocumento, MaquinaDocumentoBuilder

# placa -> costo por hora en COP. Ej.: {"MC770043": 150000}
TARIFAS_COP_POR_HORA: dict[str, float] = {}


def _wa(hora: str) -> str:
    """Nombre del archivo original de WhatsApp (todas son del 2026-09-23)."""
    return f"WhatsApp Image 2026-09-23 at {hora}.jpeg"


# Foto: (origen, vista, texto alternativo[, {"portada": True, "confianza": "media"}])
_MAQUINAS: list[dict[str, Any]] = [
    {
        "placa": "MC112258",
        "marca": "Komatsu",
        "modelo": "PC60",
        "categoria": "Excavadora",
        "descripcion": "Miniexcavadora hidráulica de orugas de la clase de 6 toneladas, "
        "ideal para obras urbanas, zanjas y espacios reducidos.",
        "capacidad": "0,25 – 0,37 m³",
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "Komatsu SAA4D95LE-5, 3,26 L, turbo",
            "potencia_neta": "40,7 kW (≈ 55 hp)",
            "peso_operativo": "≈ 6.180 kg",
            "capacidad_cuchara": "0,25 – 0,37 m³",
            "fuerza_excavacion_cuchara": 54.8,
            "capacidad_combustible": 130,
        },
        "imagenes": [
            (_wa("9.23.53 AM"), "Lateral, sobre cama baja", "Komatsu PC60 transportada sobre cama baja", {"portada": True}),
        ],
        "fuentes": [
            ("Especificaciones Komatsu PC60-8 (FridayParts)", "https://www.fridayparts.com/blog/komatsu-pc60-8-excavator-info-part-numbers-lookup"),
            ("Komatsu PC60 (Mascus)", "https://mascus.es/construccion/mini-excavadoras---7t/komatsu-pc-60/6kas9ths.html"),
        ],
        "nota": "En la foto se lee 'PC60'; la ficha corresponde a la serie PC60-8.",
    },
    {
        "placa": "PENDIENTE-PC130",
        "slug": "komatsu-pc130",
        "marca": "Komatsu",
        "modelo": "PC130",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 13 toneladas para movimiento de "
        "tierras y excavación en obras civiles.",
        "capacidad": "0,18 – 0,60 m³",
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "Komatsu SAA4D95LE-5, 3,26 L, turbo",
            "potencia_neta": "68,4 kW (91,7 hp) a 2.200 rpm",
            "peso_operativo": "12.380 – 12.740 kg",
            "capacidad_cuchara": "0,18 – 0,60 m³",
            "profundidad_max_excavacion": 5.52,
            "capacidad_combustible": 247,
        },
        "imagenes": [
            (_wa("9.24.02 AM (3)"), "Cabina y contrapeso", "Komatsu PC130, vista de cabina y contrapeso", {"portada": True}),
            (_wa("9.24.02 AM (2)"), "Brazo y cabina", "Komatsu PC130, vista del brazo y la cabina"),
        ],
        "fuentes": [
            ("Folleto oficial Komatsu PC130-8", "https://komatsu.jp/en/worldwide/PDF/PC130-8.pdf"),
            ("Komatsu PC130-8 (komatsu.com)", "https://www.komatsu.com/en-nz/products/equipment/excavators/mid-size-excavators/pc130-8"),
            ("Tanque de combustible (Construction Equipment Guide)", "https://www.constructionequipmentguide.com/charts/excavators/komatsu/pc130-8/21825"),
        ],
        "nota": "La placa no es legible en las fotos: reemplazar PENDIENTE-PC130 por la placa real "
        "(y borrar el registro SQL antiguo si ya se cargó). La ficha corresponde a la serie PC130-8.",
    },
    {
        "placa": "MC752233",
        "marca": "John Deere",
        "modelo": "160G LC",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 18 toneladas con tren de rodaje largo (LC), "
        "para movimiento de tierras, vías y obras de infraestructura.",
        "capacidad": None,
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "John Deere PowerTech, 4,5 L",
            "potencia_neta": "90 kW (122 hp)",
            "peso_operativo": 17945,
            "profundidad_max_excavacion": 6.49,
        },
        "imagenes": [
            (_wa("9.23.58 AM"), "Lateral", "John Deere 160G LC, vista lateral con cabina", {"portada": True}),
            (_wa("9.24.01 AM"), "Frontal y orugas", "John Deere 160G LC, vista frontal y orugas"),
        ],
        "fuentes": [
            ("John Deere 160G (Dobbs Equipment)", "https://dobbsequipment.com/Site-Development-Excavators/160g-excavator"),
            ("Cilindrada del motor (Boom & Bucket)", "https://www.boomandbucket.com/for-sale/2016-john-deere-160g-lc-excavators/b3678430"),
        ],
        "nota": "Placa MC752233 visible en el brazo. La foto 9.24.01 AM comparte decal y cielo con la lateral.",
    },
    {
        "placa": "MC770043",
        "marca": "John Deere",
        "modelo": "200G",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 21 toneladas con motor John Deere PowerTech, "
        "para excavación y cargue de material en obras civiles y canteras.",
        "capacidad": "0,42 – 1,02 m³",
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "John Deere PowerTech, 4 cilindros, 4,5 L",
            "potencia_neta": "108 kW (145 hp)",
            "peso_operativo": 20788,
            "capacidad_cuchara": "0,42 – 1,02 m³",
            "profundidad_max_excavacion": 7.07,
            "alcance_max_suelo": 9.79,
            "fuerza_excavacion_cuchara": 128,
        },
        "imagenes": [
            (_wa("9.24.01 AM (2)"), "Frontal con cuchara", "John Deere 200G, vista frontal con la cuchara al frente", {"portada": True}),
            (_wa("9.24.01 AM (1)"), "Cuchara y brazo", "John Deere 200G, cuchara en primer plano"),
            (_wa("9.23.56 AM"), "En operación", "John Deere 200G excavando material en obra"),
            (_wa("9.24.00 AM (1)"), "En operación", "John Deere 200G cargando material"),
            (_wa("9.24.04 AM (1)"), "Sobre cama baja", "John Deere 200G transportada sobre cama baja"),
            (_wa("9.24.02 AM"), "Posterior", "John Deere 200G, vista posterior del contrapeso", {"confianza": "media"}),
        ],
        "fuentes": [
            ("John Deere 200G (Deere Equipment)", "https://deerequipment.com/new_equipment/200g-mid-size-excavator"),
            ("Capacidad de cucharas (Construction Equipment)", "https://www.constructionequipment.com/john-deere-200g-excavator"),
        ],
        "nota": "Placa MC770043 visible en el brazo (fotos 9.23.56, 9.24.01 (1) y 9.24.04 (1)). "
        "La vista posterior (9.24.02 AM) no muestra placa: confirmar que es esta unidad.",
    },
    {
        "placa": "MC109248",
        "marca": "Link-Belt",
        "modelo": "210 X3",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 22 toneladas con motor Isuzu, "
        "para movimiento de tierras y cargue de volquetas.",
        "capacidad": "hasta 1,0 m³",
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "Isuzu AM-4HK1X",
            "potencia_neta": "160 hp (≈ 119 kW)",
            "peso_operativo": "≈ 21.700 kg (47.840 lb)",
            "capacidad_cuchara": "hasta 1,0 m³ (1,31 yd³)",
            "profundidad_max_excavacion": 6.65,
            "alcance_max_suelo": "≈ 9,9 m (32 ft 6 in)",
            "capacidad_combustible": 400,
        },
        "imagenes": [
            (_wa("9.23.54 AM"), "Lateral", "Link-Belt 210 X3, vista lateral con orugas", {"portada": True}),
            (_wa("9.24.05 AM (1)"), "Cabina y brazo", "Link-Belt 210 X3, cabina y brazo rojo"),
            (_wa("9.24.05 AM"), "En obra", "Link-Belt 210 X3 trabajando en talud", {"confianza": "media"}),
        ],
        "fuentes": [
            ("Link-Belt 210 X3 (For Construction Pros)", "https://www.forconstructionpros.com/equipment/earthmoving/product/10711373/linkbelt-excavators-linkbelt-210-x3-series-excavator"),
            ("Motor y combustible (Boom & Bucket)", "https://www.boomandbucket.com/for-sale/2017-link-belt-210-x3-excavators/a4118312"),
        ],
        "nota": "Placa MC109248 visible en la foto lateral y en la de cabina. La foto en talud (9.24.05 AM) "
        "no muestra placa. Pesos y alcances convertidos de unidades imperiales.",
    },
    {
        "placa": "MC758262",
        "marca": "Hitachi",
        "modelo": "ZAXIS 75",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 8 toneladas con radio de giro trasero reducido, "
        "ideal para obras en espacios estrechos.",
        "capacidad": None,
        "tipo_ficha": "excavadora",
        "ficha": {
            "motor": "Yanmar 4TNV98",
            "potencia_neta": "39,5 – 47,5 kW (53 – 63,7 hp)",
            "peso_operativo": "8.088 – 8.418 kg",
            "profundidad_max_excavacion": "4,61 – 4,65 m",
            "alcance_max_suelo": "6,87 – 6,92 m",
        },
        "imagenes": [
            (_wa("9.24.02 AM (1)"), "Lateral", "Hitachi ZAXIS 75 en terreno de obra", {"portada": True}),
            (_wa("9.24.04 AM (2)"), "Frontal con cuchara", "Hitachi ZAXIS 75, vista frontal con la cuchara"),
        ],
        "fuentes": [
            ("Hitachi ZX75US-5N", "https://hitachicm.com/us/en/products/excavators/compact/product.zx75us-5n"),
            ("Hitachi ZX75US-7", "https://hitachicm.com/us/en/products/excavators/compact/product.zx75us-7"),
            ("Motor Yanmar (Wajax)", "https://wajax.com/?p=19364"),
        ],
        "nota": "Placa MC758262 visible. En la máquina se lee 'ZAXIS 75'; la ficha es de la serie ZX75US "
        "(rangos entre sus versiones -5N y -7): confirmar el sufijo exacto.",
    },
    {
        "placa": "MC662589",
        "marca": "Kobelco",
        "modelo": "SK140LC",
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas de 14 toneladas para movimiento de tierras, "
        "excavación de zanjas y cargue de material.",
        "capacidad": "0,5 – 0,7 m³",
        "tipo_ficha": "excavadora",
        "ficha": {
            "potencia_neta": "74 – 79 kW (≈ 101 – 105 hp)",
            "peso_operativo": "13.200 – 14.300 kg",
            "capacidad_cuchara": "0,5 – 0,7 m³",
            "profundidad_max_excavacion": "≈ 5,5 m",
        },
        "imagenes": [
            (_wa("9.24.03 AM (1)"), "En operación", "Kobelco SK140LC excavando en obra", {"portada": True}),
            (_wa("9.24.03 AM"), "Posterior y brazo", "Kobelco SK140LC, vista posterior con la inscripción SK140 LC", {"confianza": "media"}),
        ],
        "fuentes": [
            ("Kobelco SK140LC (Mascus)", "https://www.mascus.es/construccion/excavadoras-de-cadenas/kobelco-sk-140/ilcqds7s.html"),
            ("Kobelco SK140 (Mascus)", "https://www.mascus.nl/bouw/rupsgraafmachines/kobelco-sk-140/gdofrprm.html"),
        ],
        "nota": "Placa MC662589 visible en el brazo (foto 9.24.03 AM (1)). Los rangos cubren las series -8 y -10; "
        "ajustar cuando se confirme la serie.",
    },
    {
        "placa": "MC753714",
        "marca": "Caterpillar",
        "modelo": "236D3",
        "categoria": "Minicargador",
        "descripcion": "Minicargador de dirección deslizante (skid steer) con elevación radial, "
        "para cargue, nivelación y manejo de materiales.",
        "capacidad": "825 kg (carga operativa)",
        "tipo_ficha": "minicargador",
        "ficha": {
            "motor": "Cat C3.3B, turbo diésel (Tier 4 Final / Stage V)",
            "potencia_neta": "73,2 hp (≈ 54,6 kW)",
            "capacidad_operativa": 825,
            "capacidad_operativa_contrapeso": 910,
            "peso_operativo": 2972,
            "tipo_elevacion": "Radial",
        },
        "imagenes": [
            (_wa("9.24.04 AM"), "Frontal con cuchara", "Caterpillar 236D3, vista frontal con la cuchara", {"portada": True, "confianza": "media"}),
            (_wa("9.24.03 AM (2)"), "Cabina y brazos de elevación", "Caterpillar 236D3, cabina y brazos"),
            (_wa("9.24.03 AM (3)"), "Cabina y brazos de elevación", "Caterpillar 236D3, vista alterna de cabina y brazos"),
        ],
        "fuentes": [
            ("Cat 236D3 (cat.com)", "https://www.cat.com/en_MX/products/new/equipment/skid-steer-and-compact-track-loaders/skid-steer-loaders/15970089.html"),
            ("Potencia neta (Wheeler Cat)", "https://wheelercat.com/?p=1255"),
        ],
        "nota": "Placa MC753714 visible en el brazo de las fotos 9.24.03 AM (2) y (3). La foto frontal "
        "(9.24.04 AM) no muestra placa: confirmar que es la misma unidad. Capacidad con la configuración estándar.",
    },
    {
        "placa": "PENDIENTE-SHANTUI",
        "slug": "shantui-excavadora",
        "marca": "Shantui",
        "modelo": None,
        "categoria": "Excavadora",
        "descripcion": "Excavadora hidráulica de orugas Shantui. Ficha técnica en revisión: "
        "el modelo exacto se confirmará.",
        "capacidad": None,
        "tipo_ficha": "excavadora",
        "ficha": {},
        "imagenes": [
            (_wa("9.24.00 AM"), "Brazo y cabina", "Excavadora Shantui sobre cama baja", {"portada": True}),
        ],
        "fuentes": [],
        "nota": "No se ve ni el modelo ni la placa en la foto, por eso no se publicaron datos técnicos. "
        "Completar modelo, placa (reemplazar PENDIENTE-SHANTUI) y ficha.",
    },
]


class CatalogoDirector:
    """Director del Builder: dicta el orden de construcción de cada documento."""

    def __init__(self, fabrica_builder: Callable[[], MaquinaDocumentoBuilder] = MaquinaDocumentoBuilder):
        self._fabrica_builder = fabrica_builder

    def construir(self, spec: dict[str, Any]) -> MaquinaDocumento:
        builder = self._fabrica_builder()
        builder.con_identidad(
            spec["placa"], spec["marca"], spec["modelo"], spec["categoria"], spec.get("slug")
        )
        builder.con_descripcion(spec["descripcion"], spec["capacidad"])
        builder.con_ficha(spec["tipo_ficha"], **spec["ficha"])
        for origen, vista, alt, *extra in spec["imagenes"]:
            opciones = extra[0] if extra else {}
            builder.agregar_imagen(origen, vista, alt, **opciones)
        for descripcion, url in spec["fuentes"]:
            builder.agregar_fuente(descripcion, url)
        builder.con_nota_verificacion(spec["nota"])
        return builder.build()

    def construir_todo(self) -> list[MaquinaDocumento]:
        return [self.construir(spec) for spec in _MAQUINAS]


def construir_catalogo() -> list[MaquinaDocumento]:
    return CatalogoDirector().construir_todo()
