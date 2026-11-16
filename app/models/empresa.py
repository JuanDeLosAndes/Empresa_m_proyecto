
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection
from app.security import hash_password, verify_password
import re

ROL_EMPRESA = "empresa"


@dataclass
class Empresa:
    id_empresa: int
    nit: str
    nombre: str
    correo: str
    direccion: Optional[str]

    @staticmethod
    def _from_row(row) -> "Empresa":
        return Empresa(
            id_empresa=row["id_empresa"],
            nit=row["nit"],
            nombre=row["nombre"],
            correo=row["correo"],
            direccion=row["direccion"],
        )


class EmpresaModel:
    @staticmethod
    def crear(
        nombre: str,
        nit: str,
        correo: str,
        contrasena: str,
        direccion: Optional[str] = None,
    ) -> Empresa:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO empresas (nit, nombre, correo, direccion, contrasena_hash, id_rol)
               VALUES (?, ?, ?, ?, ?, (SELECT id_rol FROM roles WHERE nombre = ?))""",
            (nit, nombre, correo, direccion, hash_password(contrasena), ROL_EMPRESA),
        )
        conn.commit()
        empresa = EmpresaModel.obtener_por_id(cursor.lastrowid)
        assert empresa is not None
        return empresa

    @staticmethod
    def obtener_por_id(id_empresa: int) -> Optional[Empresa]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM empresas WHERE id_empresa = ?", (id_empresa,)
        ).fetchone()
        return Empresa._from_row(fila) if fila else None

    @staticmethod
    def autenticar(identificador: str, contrasena: str) -> Optional[Empresa]:
        """Autentica por correo o NIT."""
        conn = get_connection()
        identificador = identificador.strip()
        nit = identificador.replace(".", "").replace("-", "")
        if re.fullmatch(r"[0-9]{9,10}", nit):
            nit = nit[:9]
        fila = conn.execute(
            """SELECT * FROM empresas WHERE lower(correo) = ? OR nit = ?
               OR substr(replace(replace(nit, '.', ''), '-', ''), 1, 9) = ?""",
            (identificador.lower(), identificador, nit),
        ).fetchone()
        if fila and verify_password(contrasena, fila["contrasena_hash"]):
            return Empresa._from_row(fila)
        return None