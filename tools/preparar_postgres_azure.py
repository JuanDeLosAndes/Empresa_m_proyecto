import os
from getpass import getpass

import certifi
import psycopg
from psycopg import sql


def preparar(conexion, administrador, clave_admin, clave_app):
    # CREATE DATABASE necesita autocommit. Cada paso comprueba lo que ya existe.
    with psycopg.connect(**conexion, dbname="postgres", user=administrador, password=clave_admin,
                         autocommit=True) as admin:
        if not admin.execute("SELECT 1 FROM pg_database WHERE datname='msps'").fetchone():
            admin.execute("CREATE DATABASE msps")
        if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='msps_app'").fetchone():
            verificador = admin.pgconn.encrypt_password(clave_app.encode(), b"msps_app", b"scram-sha-256")
            admin.execute(sql.SQL("CREATE ROLE msps_app LOGIN PASSWORD {}").format(sql.Literal(verificador.decode())))
    with psycopg.connect(**conexion, dbname="msps", user=administrador, password=clave_admin) as db:
        db.execute("GRANT CONNECT ON DATABASE msps TO msps_app")
        db.execute("GRANT USAGE, CREATE ON SCHEMA public TO msps_app")
    with psycopg.connect(**conexion, dbname="msps", user="msps_app", password=clave_app) as app:
        permisos = app.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')").fetchone()[0]
        if not permisos:
            raise RuntimeError("El usuario msps_app requiere permiso para crear las tablas en public.")


def main():
    host = input("Nombre de servidor completo de Azure (.postgres.database.azure.com): ").strip().lower()
    if not host.endswith(".postgres.database.azure.com") or "/" in host or ":" in host:
        raise SystemExit("Copia el nombre de host del servidor PostgreSQL desde Información general.")
    admin = input("Usuario administrador del servidor PostgreSQL: ").strip()
    if not admin or admin == "msps_app":
        raise SystemExit("Usa aquí el administrador que elegiste al crear el servidor.")
    clave_admin = getpass("Contraseña del administrador del servidor: ")
    clave_app = getpass("Contraseña para msps_app (si ya existe, escribe su contraseña actual): ")
    if not clave_app or clave_app != getpass("Repite la contraseña de msps_app: "):
        raise SystemExit("Las contraseñas de msps_app deben coincidir.")
    conexion = dict(host=host, port=5432, connect_timeout=10, sslmode="verify-full",
                    sslrootcert=os.getenv("PGSSLROOTCERT") or certifi.where())
    try:
        preparar(conexion, admin, clave_admin, clave_app)
    except psycopg.Error as error:
        raise SystemExit(f"PostgreSQL: {error}") from None
    print("Conexión comprobada. Base: msps. Usuario de la aplicación: msps_app.")


if __name__ == "__main__":
    main()