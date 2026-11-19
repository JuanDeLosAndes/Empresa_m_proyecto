
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import transaccion
from app.security import hash_password, verify_password

ROL_PERSONA_NATURAL = "persona_natural"
ROL_ADMINISTRADOR = "administrador"


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

        with transaccion() as conn:
            cursor = conn.execute(
                """INSERT INTO usuarios (nombre, contrasena_hash, id_empresa, id_rol)
                   VALUES (?, ?, ?, (SELECT id_rol FROM roles WHERE nombre = ?)) RETURNING id_usuario""",
                (nombre, hash_password(contrasena), id_empresa, ROL_PERSONA_NATURAL),
            )
            id_usuario = cursor.fetchone()["id_usuario"]
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
        with transaccion() as conn:
            cursor = conn.execute(
                """INSERT INTO usuarios (nombre, contrasena_hash, id_rol)
                   VALUES (?, ?, (SELECT id_rol FROM roles WHERE nombre = ?)) RETURNING id_usuario""",
                (nombre, hash_password(contrasena), ROL_ADMINISTRADOR),
            )
            id_usuario = cursor.fetchone()["id_usuario"]
            conn.execute(
                "INSERT INTO administradores (id_usuario) VALUES (?)",
                (id_usuario,),
            )
        usuario = UsuarioModel.obtener_por_id(id_usuario)
        assert usuario is not None
        return usuario

    @staticmethod
    def obtener_por_id(id_usuario: int) -> Optional[Usuario]:
        with transaccion() as conn:
            fila = conn.execute(
                _SELECT_USUARIO + " WHERE u.id_usuario = ?", (id_usuario,)
            ).fetchone()
            return Usuario._from_row(fila) if fila else None

    @staticmethod
    def autenticar(identificador: str, contrasena: str) -> Optional[Usuario]:
        """Autentica por nombre, correo o cédula (cubre tanto personas
        naturales como administradores)."""
        identificador = identificador.strip()
        with transaccion() as conn:
            fila = conn.execute(
                _SELECT_USUARIO + " WHERE u.nombre = ? OR lower(p.correo) = ? OR p.cedula = ?",
                (identificador, identificador.lower(), identificador),
            ).fetchone()
            if fila and verify_password(contrasena, fila["contrasena_hash"]):
                return Usuario._from_row(fila)
            return None
