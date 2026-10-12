"""Migración de UNA SOLA VEZ: sube a MongoDB las fotos que hoy viajan dentro del repo.

Uso (desde la raíz del proyecto, con MONGODB_URI apuntando a la base destino):
    python -m tools.migrar_fotos_a_mongo

Después de correrlo (y de comprobar que las fotos se ven en el sitio) la carpeta
app/seed_data/imagenes_maquinas ya no hace falta y se puede borrar del repo.

No pisa el trabajo del administrador: si una máquina ya tiene fotos en MongoDB,
se omite (usa --forzar para reemplazarlas por las del repo).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.catalogo_maquinas import construir_catalogo
from app.factories import crear_imagenes_repositorio, crear_maquina_documentos_repositorio

RUTA_FOTOS = Path(__file__).resolve().parent.parent / "app" / "seed_data" / "imagenes_maquinas"


def migrar(forzar: bool = False, ruta: Path = RUTA_FOTOS) -> tuple[int, int]:
    documentos = crear_maquina_documentos_repositorio()
    almacen = crear_imagenes_repositorio()
    documentos.asegurar_indices()
    migradas = omitidas = 0
    for doc in construir_catalogo():
        actual = documentos.obtener_por_placa(doc.placa)
        if actual is not None and actual.imagenes and not forzar:
            print(f"= {doc.placa}: ya tiene {len(actual.imagenes)} fotos en MongoDB, se omite")
            omitidas += 1
            continue
        for imagen in doc.imagenes:
            almacen.guardar(imagen.archivo, (ruta / imagen.archivo).read_bytes())
        documentos.guardar(doc)  # el documento va después de sus fotos
        print(f"+ {doc.placa}: {len(doc.imagenes)} fotos subidas")
        migradas += 1
    return migradas, omitidas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--forzar", action="store_true", help="Reemplaza las fotos aunque la máquina ya tenga")
    args = parser.parse_args()
    migradas, omitidas = migrar(forzar=args.forzar)
    print(f"Máquinas migradas: {migradas} · omitidas: {omitidas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())