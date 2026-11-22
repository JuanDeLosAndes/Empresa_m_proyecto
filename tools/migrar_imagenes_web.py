import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from PIL import Image, ImageOps

from pymongo.errors import PyMongoError

from app.documentos.store import get_mongo_database
from app.models.recursos_web import MANIFIESTO_WEB, RECURSOS, RecursoWeb, RecursoWebNoDisponible
from app.repositories.recurso_web_repository import RecursosWebMongo

RAIZ = Path(__file__).resolve().parents[1]
IMAGENES = Path("app/static/images")


def convertir_original(ruta, datos):
    if ruta == "sin-foto.svg":
        return ruta, "image/svg+xml", datos
    with Image.open(BytesIO(datos)) as imagen:
        if ruta == "logo/logo-msps.png":
            if imagen.format != "PNG":
                raise ValueError("El logo debe ser un PNG.")
            imagen.verify()
            return ruta, "image/png", datos
        foto = ImageOps.exif_transpose(imagen)
        foto.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        salida = BytesIO()
        foto.save(salida, "WEBP", quality=83, method=6)
    return Path(ruta).with_suffix(".webp").as_posix(), "image/webp", salida.getvalue()


def desde_originales(raiz, carpeta_respaldo, manifiesto, repositorio, recursos):
    """Prepara un respaldo externo y publica el catálogo solo después de verificar Mongo."""
    raiz = raiz.resolve()
    carpeta_respaldo = carpeta_respaldo.resolve()
    if carpeta_respaldo.is_relative_to(raiz):
        raise ValueError("Elige una carpeta de respaldo fuera del proyecto.")
    carpeta = raiz / IMAGENES
    presentes = {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}
    if presentes != set(recursos):
        diferencias = ", ".join(sorted(presentes.symmetric_difference(recursos)))
        raise ValueError(f"Revisa los originales antes de migrar. Diferencias: {diferencias}")

    nuevos = {}
    with TemporaryDirectory(dir=carpeta_respaldo) as temporal:
        paquete = Path(temporal) / "imagenes.zip"
        with ZipFile(paquete, "w", ZIP_DEFLATED) as salida:
            for ruta in sorted(presentes):
                archivo = carpeta / ruta
                if archivo.is_symlink() or not archivo.resolve().is_relative_to(carpeta.resolve()):
                    raise ValueError(f"Revisa la ruta del original {ruta}.")
                original = archivo.read_bytes()
                nombre, tipo, datos = convertir_original(ruta, original)
                nuevos[ruta] = RecursoWeb(nombre, tipo, len(datos),
                                          sha256(datos).hexdigest(), sha256(original).hexdigest())
                salida.writestr(nombre, datos)
        catalogo = {ruta: asdict(recurso) for ruta, recurso in nuevos.items()}
        texto = json.dumps(catalogo, indent=2) + "\n"
        version = sha256(texto.encode("utf-8")).hexdigest()[:16]
        respaldo = carpeta_respaldo / f"MSPS_imagenes_{version}.zip"
        importar(paquete, repositorio, nuevos)
        verificar(repositorio, nuevos)
        paquete.replace(respaldo)
        print(f"Respaldo: {respaldo}")
    # El reemplazo es atómico en el mismo volumen y permite reintentar tras un fallo.
    with TemporaryDirectory(dir=manifiesto.parent) as temporal:
        catalogo_nuevo = Path(temporal) / manifiesto.name
        catalogo_nuevo.write_text(texto, encoding="utf-8")
        catalogo_nuevo.replace(manifiesto)
    print("Catálogo local actualizado. Conserva este JSON en Git junto con el código.")


def importar(paquete, repositorio, recursos):
    # Validar el lote completo antes de la primera escritura.
    with ZipFile(paquete) as zip_imagenes:
        contenidos = []
        for recurso in recursos.values():
            info = zip_imagenes.getinfo(recurso.paquete)
            if info.file_size != recurso.bytes:
                raise ValueError(f"Tamaño incorrecto en el ZIP para {recurso.paquete}.")
            contenido = zip_imagenes.read(info)
            recurso.comprobar(contenido)
            contenidos.append((recurso, contenido))
    for recurso, contenido in contenidos:
        repositorio.guardar(recurso, contenido)


def verificar(repositorio, recursos):
    # Cada lectura va directamente a la base y comprueba tipo, longitud y SHA-256.
    for ruta, recurso in recursos.items():
        repositorio.leer(recurso)
        print(f"OK  {ruta}")
    print(f"{len(recursos)}/{len(recursos)} imágenes verificadas en MongoDB.")


def comprobar_originales(raiz, recursos):
    carpeta = raiz / IMAGENES
    presentes = {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}
    adicionales = presentes.difference(recursos)
    if adicionales:
        raise ValueError("Hay imágenes locales fuera del catálogo. Revísalas primero: "
                         + ", ".join(sorted(adicionales)))
    rutas = []
    for ruta in sorted(presentes):
        archivo = carpeta / ruta
        datos = archivo.read_bytes()
        if archivo.is_symlink() or sha256(datos).hexdigest() != recursos[ruta].original:
            raise ValueError(f"Tu original de {ruta} es distinto. Se conserva para revisión.")
        rutas.append(str(IMAGENES / ruta))
    return rutas


def retirar(raiz, repositorio, recursos):
    rutas = comprobar_originales(raiz, recursos)
    verificar(repositorio, recursos)
    if rutas:
        # Git también protege archivos con cambios en el índice. Nunca se usa --force.
        subprocess.run(["git", "rm", "--", *rutas], cwd=raiz, check=True)
    print("Los originales verificados ya están fuera del árbol de trabajo.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("desde-originales").add_argument("carpeta_respaldo", type=Path)
    sub.add_parser("importar").add_argument("paquete", type=Path)
    sub.add_parser("verificar")
    sub.add_parser("retirar")
    args = parser.parse_args()
    if not os.getenv("MONGODB_URI", "").strip() or not os.getenv("MONGODB_DB", "").strip():
        parser.exit(1, "Define MONGODB_URI y MONGODB_DB en el .env de la raíz.\n")
    try:
        base = get_mongo_database()
        print(f"Base de destino: {base.name} / recursos_web")
        repositorio = RecursosWebMongo(base)
        if args.accion == "desde-originales":
            desde_originales(RAIZ, args.carpeta_respaldo, MANIFIESTO_WEB, repositorio, RECURSOS)
        elif args.accion == "retirar":
            retirar(RAIZ, repositorio, RECURSOS)
        else:
            if args.accion == "importar":
                comprobar_originales(RAIZ, RECURSOS)
                importar(args.paquete, repositorio, RECURSOS)
            verificar(repositorio, RECURSOS)
    except PyMongoError as error:
        print(f"MongoDB ({type(error).__name__}): revisa la URI, el usuario y las IP permitidas.",
              file=sys.stderr)
        return 1
    except (KeyError, OSError, BadZipFile, ValueError, RecursoWebNoDisponible,
            subprocess.CalledProcessError) as error:
        print(f"Migración interrumpida. {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())