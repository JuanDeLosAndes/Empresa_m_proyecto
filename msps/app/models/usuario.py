"""
Modelo de Usuario (la M de MVC).

Encapsula todo el acceso a la tabla `usuarios`. Por decisión explícita
del cliente, Administrador NO es una tabla aparte: es un Usuario con
rol = 'administrador'. Los clientes (persona natural) se crean con
rol = 'cliente' desde el formulario público de registro; los
administradores no se auto-registran desde la web (por seguridad) y
se crean con `UsuarioModel.crear_administrador`, pensado para usarse
desde un script/consola de administración.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection
from app.security import hash_password, verify_password

ROL_CLIENTE = "cliente"
ROL_ADMINISTRADOR = "administrador"


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
    def crear_cliente(
        nombre: str,
        contrasena: str,
        cedula: str,
        correo: str,
        telefono: Optional[str] = None,
        id_empresa: Optional[int] = None,
    ) -> Usuario:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO usuarios
                   (nombre, contrasena_hash, cedula, correo, telefono, id_empresa, rol)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (nombre, hash_password(contrasena), cedula, correo, telefono, id_empresa, ROL_CLIENTE),
        )
        conn.commit()
        usuario = UsuarioModel.obtener_por_id(cursor.lastrowid)
        assert usuario is not None
        return usuario

    @staticmethod
    def crear_administrador(nombre: str, contrasena: str) -> Usuario:
        """Pensado para usarse desde un script de consola/seed, nunca
        desde un formulario público."""
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO usuarios (nombre, contrasena_hash, rol)
               VALUES (?, ?, ?)""",
            (nombre, hash_password(contrasena), ROL_ADMINISTRADOR),
        )
        conn.commit()
        usuario = UsuarioModel.obtener_por_id(cursor.lastrowid)
        assert usuario is not None
        return usuario

    @staticmethod
    def obtener_por_id(id_usuario: int) -> Optional[Usuario]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM usuarios WHERE id_usuario = ?", (id_usuario,)
        ).fetchone()
        return Usuario._from_row(fila) if fila else None

    @staticmethod
    def autenticar(identificador: str, contrasena: str) -> Optional[Usuario]:
        """Autentica por nombre, correo o cédula (cubre tanto clientes
        como administradores, que comparten la misma tabla)."""
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM usuarios WHERE nombre = ? OR correo = ? OR cedula = ?",
            (identificador, identificador, identificador),
        ).fetchone()
        if fila and verify_password(contrasena, fila["contrasena_hash"]):
            return Usuario._from_row(fila)
        return None