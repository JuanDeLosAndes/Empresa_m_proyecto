"""
Modelo de Usuario (la M de MVC).

`usuarios` es la cuenta base (nombre + contraseña + rol). Según el rol,
los datos propios viven en otra tabla:
  - rol 'persona_natural' -> tabla `personas_naturales` (cédula, correo, teléfono)
  - rol 'administrador'   -> tabla `administradores`
Los roles disponibles están en la tabla `roles` (empresa, administrador,
persona_natural). Las empresas tienen su propia tabla y su propio login
(ver app/models/empresa.py).

Los administradores no se auto-registran desde la web (por seguridad) y
se crean con `UsuarioModel.crear_administrador`, pensado para usarse
desde un script/consola de administración.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection
from app.security import hash_password, verify_password

ROL_PERSONA_NATURAL = "persona_natural"
ROL_ADMINISTRADOR = "administrador"

# Consulta base: une la cuenta con su rol y, si es persona natural, con
# sus datos personales (para administradores cédula/correo/teléfono = NULL).
_SELECT_USUARIO = """
    SELECT u.id_usuario, u.nombre, u.contrasena_hash, u.id_empresa,
           r.nombre AS rol,
           p.cedula, p.correo, p.telefono
    FROM usuarios u
    JOIN roles r ON r.id_rol = u.id_rol
    LEFT JOIN personas_naturales p ON p.id_usuario = u.id_usuario
"""


@dataclass
class Usuario:
    id_usuario: int
    nombre: str
    cedula: Optional[str]
    correo: Optional[str]
    telefono: Optional[str]
    id_empresa: Optional[int]
    rol: str

    @staticmethod
    def _from_row(row) -> "Usuario":
        return Usuario(
            id_usuario=row["id_usuario"],
            nombre=row["nombre"],
            cedula=row["cedula"],
            correo=row["correo"],
            telefono=row["telefono"],
            id_empresa=row["id_empresa"],
            rol=row["rol"],
        )

    @property
    def es_administrador(self) -> bool:
        return self.rol == ROL_ADMINISTRADOR


class UsuarioModel:
    @staticmethod
    def crear_persona_natural(
        nombre: str,
        contrasena: str,
        cedula: str,
        correo: str,
        telefono: Optional[str] = None,
        id_empresa: Optional[int] = None,
    ) -> Usuario:
        """Crea la cuenta (usuarios) y sus datos (personas_naturales) en
        una sola transacción: si la cédula o el correo ya existen se
        lanza sqlite3.IntegrityError y no queda nada a medias."""
        conn = get_connection()
        with conn:
            cursor = conn.execute(
                """INSERT INTO usuarios (nombre, contrasena_hash, id_empresa, id_rol)
                   VALUES (?, ?, ?, (SELECT id_rol FROM roles WHERE nombre = ?))""",
                (nombre, hash_password(contrasena), id_empresa, ROL_PERSONA_NATURAL),
            )
            id_usuario = cursor.lastrowid
            conn.execute(
                """INSERT INTO personas_naturales (id_usuario, cedula, correo, telefono)
                   VALUES (?, ?, ?, ?)""",
                (id_usuario, cedula, correo, telefono),
            )
        usuario = UsuarioModel.obtener_por_id(id_usuario)
        assert usuario is not None
        return usuario

    @staticmethod
    def crear_administrador(nombre: str, contrasena: str) -> Usuario:
        """Pensado para usarse desde un script de consola/seed, nunca
        desde un formulario público."""
        conn = get_connection()
        with conn:
            cursor = conn.execute(
                """INSERT INTO usuarios (nombre, contrasena_hash, id_rol)
                   VALUES (?, ?, (SELECT id_rol FROM roles WHERE nombre = ?))""",
                (nombre, hash_password(contrasena), ROL_ADMINISTRADOR),
            )
            id_usuario = cursor.lastrowid
            conn.execute(
                "INSERT INTO administradores (id_usuario) VALUES (?)",
                (id_usuario,),
            )
        usuario = UsuarioModel.obtener_por_id(id_usuario)
        assert usuario is not None
        return usuario

    @staticmethod
    def obtener_por_id(id_usuario: int) -> Optional[Usuario]:
        conn = get_connection()
        fila = conn.execute(
            _SELECT_USUARIO + " WHERE u.id_usuario = ?", (id_usuario,)
        ).fetchone()
        return Usuario._from_row(fila) if fila else None

    @staticmethod
    def autenticar(identificador: str, contrasena: str) -> Optional[Usuario]:
        """Autentica por nombre, correo o cédula (cubre tanto personas
        naturales como administradores)."""
        conn = get_connection()
        fila = conn.execute(
            _SELECT_USUARIO + " WHERE u.nombre = ? OR p.correo = ? OR p.cedula = ?",
            (identificador, identificador, identificador),
        ).fetchone()
        if fila and verify_password(contrasena, fila["contrasena_hash"]):
            return Usuario._from_row(fila)
        return None