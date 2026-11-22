import argparse
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.database import ESQUEMA_POSTGRES, motor, preparar_esquema_sqlite, transaccion
from app.models.diagnostico import campos_del_proyecto


# El orden respeta las llaves foráneas. Solo se usan identificadores del esquema del proyecto.
TABLAS = (
    "roles", "empresas", "usuarios", "personas_naturales", "administradores",
    "categorias", "maquinarias", "alquileres", "facturas", "facturas_empresa",
    "solicitudes_empresa", "cotizaciones", "registros_pendientes", "pedidos_pago", "recuperaciones",
)


@contextmanager
def _copia_actualizada(uri):
    with closing(sqlite3.connect(":memory:")) as copia:
        with closing(sqlite3.connect(uri, uri=True)) as origen:
            origen.backup(copia)
        copia.row_factory = sqlite3.Row
        tablas = {f[0] for f in copia.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        if not {"usuarios", "empresas", "maquinarias", "categorias"} <= tablas:
            raise ValueError("Este archivo no contiene las tablas principales de MSPS.")
        if tablas.difference(TABLAS):
            raise ValueError("SQLite contiene tablas adicionales. Revisa su correspondencia antes de importar.")
        preparar_esquema_sqlite(copia)
        yield copia


def importar(archivo: Path) -> dict[str, int]:
    if motor() != "postgresql":
        raise ValueError("Selecciona MSPS_DB_ENGINE=postgresql para esta importación.")
    uri = archivo.resolve(strict=True).as_uri() + "?mode=ro"
    esperados = campos_del_proyecto()
    conteos = {}
    with _copia_actualizada(uri) as fuente, transaccion(serializar="esquema") as destino:
        if fuente.execute("PRAGMA quick_check").fetchone()[0] != "ok" or fuente.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite tiene errores de integridad. Revisa el respaldo antes de importar.")
        existentes = destino.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        ).fetchall()
        if any(f["table_name"] in TABLAS for f in existentes):
            raise ValueError("El destino ya contiene tablas MSPS. Elige una base vacía.")
        destino.execute(ESQUEMA_POSTGRES.read_text(encoding="utf-8"))
        for tabla in TABLAS:
            campos = [f[1] for f in fuente.execute(f"PRAGMA table_info({tabla})")]
            if set(campos) != {c for t, c in esperados if t == tabla}:
                raise ValueError(f"El esquema de {tabla} difiere. Actualiza primero una copia SQLite con la app.")
            columnas = ", ".join(campos)
            marcas = ", ".join("?" for _ in campos)
            insertar = f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})"
            cantidad = 0
            for fila in fuente.execute(f"SELECT {columnas} FROM {tabla}"):
                destino.execute(insertar, fila)
                cantidad += 1
            verificacion = destino.execute(f"SELECT count(*) AS n FROM {tabla}").fetchone()["n"]
            if verificacion != cantidad:
                raise ValueError(f"El conteo de {tabla} no coincide. Se cancela la importación.")
            conteos[tabla] = cantidad
        # AUTOINCREMENT recuerda también IDs que se borraron. Conservar ese máximo
        # evita reutilizar la identidad de una cuenta desaparecida después del traslado.
        maximos_sqlite = dict(fuente.execute("SELECT name, seq FROM sqlite_sequence"))
        identidades = destino.execute(
            """SELECT table_name, column_name FROM information_schema.columns
               WHERE table_schema = current_schema() AND is_identity = 'YES'"""
        ).fetchall()
        for fila in identidades:
            t, c = fila["table_name"], fila["column_name"]
            if (t, c) in esperados:
                destino.execute(
                    f"""SELECT setval(pg_get_serial_sequence(?, ?),
                        GREATEST(COALESCE(MAX({c}), 1), CAST(? AS bigint), 1),
                        count(*) > 0 OR CAST(? AS bigint) > 0) FROM {t}""",
                    (t, c, maximos_sqlite.get(t, 0), maximos_sqlite.get(t, 0)),
                )
    return conteos


def importar_catalogo(archivo: Path) -> dict[str, int]:
    """Copia categorías y máquinas desde SQLite; las fotos de Atlas siguen por placa.

    Acepta una base PostgreSQL recién arrancada: la aplicación puede haber sembrado
    categorías, máquinas de ejemplo y el nuevo administrador antes de la importación.
    """
    if motor() != "postgresql":
        raise ValueError("Selecciona MSPS_DB_ENGINE=postgresql para esta importación.")

    uri = archivo.resolve(strict=True).as_uri() + "?mode=ro"
    with _copia_actualizada(uri) as fuente, transaccion(serializar="catalogo") as destino:
        if (fuente.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                or fuente.execute("PRAGMA foreign_key_check").fetchone()):
            raise ValueError("SQLite tiene errores de integridad. Revisa la base de origen.")

        tablas = {
            fila["table_name"] for fila in destino.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            ).fetchall()
        }
        if not {"categorias", "maquinarias"} <= tablas:
            raise ValueError("Crea las tablas primero: MSPS_DB_ENGINE=postgresql python -c 'from app.database import init_db; init_db()'")

        categorias = fuente.execute(
            "SELECT id_categoria, nombre_categoria FROM categorias ORDER BY id_categoria"
        ).fetchall()
        maquinas = fuente.execute(
            """SELECT m.marca, m.descripcion, m.capacidad, m.modelo, m.costo_por_hora,
                      m.ficha_admin, m.placa, m.disponible, m.eliminada, c.nombre_categoria
               FROM maquinarias m JOIN categorias c ON c.id_categoria = m.id_categoria
               ORDER BY m.id_maquinaria"""
        ).fetchall()
        total_maquinas = fuente.execute("SELECT count(*) FROM maquinarias").fetchone()[0]
        if len(maquinas) != total_maquinas:
            raise ValueError("Hay máquinas sin categoría. Se cancela la importación.")

        for categoria in categorias:
            destino.execute(
                """INSERT INTO categorias (nombre_categoria) VALUES (?)
                   ON CONFLICT (nombre_categoria) DO NOTHING""",
                (categoria["nombre_categoria"],),
            )

        ids = {
            fila["nombre_categoria"]: fila["id_categoria"]
            for fila in destino.execute(
                "SELECT id_categoria, nombre_categoria FROM categorias"
            ).fetchall()
        }
        for maquina in maquinas:
            destino.execute(
                """INSERT INTO maquinarias
                   (marca, descripcion, capacidad, modelo, costo_por_hora, placa,
                    disponible, eliminada, id_categoria, ficha_admin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (placa) DO UPDATE SET
                       ficha_admin = COALESCE(EXCLUDED.ficha_admin, maquinarias.ficha_admin),
                       marca = EXCLUDED.marca,
                       descripcion = EXCLUDED.descripcion,
                       capacidad = EXCLUDED.capacidad,
                       modelo = EXCLUDED.modelo,
                       costo_por_hora = EXCLUDED.costo_por_hora,
                       disponible = EXCLUDED.disponible,
                       eliminada = EXCLUDED.eliminada,
                       id_categoria = EXCLUDED.id_categoria""",
                (maquina["marca"], maquina["descripcion"], maquina["capacidad"],
                 maquina["modelo"], maquina["costo_por_hora"], maquina["placa"],
                 maquina["disponible"], maquina["eliminada"],
                 ids[maquina["nombre_categoria"]], maquina["ficha_admin"]),
            )

        comprobadas = destino.execute(
            "SELECT count(*) AS n FROM maquinarias WHERE placa = ANY(?)",
            ([fila["placa"] for fila in maquinas],),
        ).fetchone()["n"]
        if comprobadas != total_maquinas:
            raise ValueError("No se pudieron verificar todas las placas importadas.")
        return {"categorias": len(categorias), "maquinarias": total_maquinas}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path, help="Ruta verificada de SQLite")
    parser.add_argument(
        "--solo-catalogo", action="store_true",
        help="Copia las categorías y las máquinas; crea cuentas nuevas al iniciar la web.",
    )
    try:
        opciones = parser.parse_args()
        operacion = importar_catalogo if opciones.solo_catalogo else importar
        for tabla, cantidad in operacion(opciones.archivo).items():
            print(f"{tabla}: {cantidad}")
    except (ValueError, FileNotFoundError) as error:
        raise SystemExit(str(error)) from None