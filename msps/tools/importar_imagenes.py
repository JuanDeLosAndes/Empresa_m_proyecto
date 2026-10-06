"""
Importa las fotos originales al sitio según el catálogo.

Uso (desde la carpeta msps/):
    python -m tools.importar_imagenes --origen "ruta/a/las/fotos"

Para cada imagen de app/catalogo_maquinas.py busca el archivo original
en --origen y lo guarda como app/seed_data/imagenes_maquinas/<slug>/NN.jpg
(el mismo nombre que quedó registrado en el documento). Al arrancar la app,
el seed sube esas fotos a MongoDB (GridFS); desde ahí las sirve el sitio.

Además:
- Corrige la orientación y ELIMINA los metadatos EXIF (incluye GPS).
- Reduce a 1400 px de lado mayor (las fotos de celular pesan 1-3 MB).
- Avisa de fotos en --origen que el catálogo no usa (posibles máquinas
  nuevas por agregar o fotos repetidas).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

from app.catalogo_maquinas import construir_catalogo

DESTINO = Path(__file__).resolve().parent.parent / "app" / "seed_data" / "imagenes_maquinas"
LADO_MAXIMO = 1400
CALIDAD_JPEG = 82

# Recortes (izq, arriba, der, abajo) como fracción 0-1 de la imagen original.
# La foto del Komatsu PC60 trae estampada la dirección y la fecha de captura
# (marca de agua de la cámara) en la esquina inferior; se recorta para no
# publicar una ubicación.
RECORTES: dict[str, tuple[float, float, float, float]] = {
    "WhatsApp Image 2026-09-23 at 9.23.53 AM.jpeg": (0.0, 0.0, 1.0, 0.78),
}


def procesar(origen: Path, destino: Path, recorte: tuple[float, float, float, float] | None) -> None:
    with Image.open(origen) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        if recorte:
            ancho, alto = img.size
            l, t, r, b = recorte
            img = img.crop((int(l * ancho), int(t * alto), int(r * ancho), int(b * alto)))
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Sin exif=...: no se escribe ningún metadato.
        img.save(destino, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen", required=True, type=Path, help="Carpeta con las fotos originales")
    args = parser.parse_args()

    usadas: set[str] = set()
    faltantes: list[str] = []
    total = 0
    for doc in construir_catalogo():
        for imagen in doc.imagenes:
            fuente = args.origen / imagen.origen
            if not fuente.exists():
                faltantes.append(imagen.origen)
                continue
            procesar(fuente, DESTINO / imagen.archivo, RECORTES.get(imagen.origen))
            usadas.add(imagen.origen)
            total += 1

    sin_usar = sorted(
        p.name for p in args.origen.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and p.name not in usadas
    )
    print(f"Imágenes procesadas: {total}")
    if sin_usar:
        print("Fotos de la carpeta que el catálogo NO usa:", *sin_usar, sep="\n  - ")
    if faltantes:
        print("No se encontraron estos archivos:", *faltantes, sep="\n  - ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
