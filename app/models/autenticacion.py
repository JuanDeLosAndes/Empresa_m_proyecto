
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import ERRORES_INTEGRIDAD
from app.models.empresa import ROL_EMPRESA, EmpresaModel
from app.models.usuario import UsuarioModel


@dataclass(frozen=True)
class Credencial:
    tipo: str  # 'persona_natural' | 'administrador' | 'empresa'
    id: int


class AutenticacionModel:
    @staticmethod
    def registrar_persona(cedula: str, usuario: str, correo: str, contrasena: str) -> bool:
        """True si se creó la cuenta; False si ya existe (usuario, correo o cédula repetidos)."""
        try:
            UsuarioModel.crear_persona_natural(
                nombre=usuario, contrasena=contrasena, cedula=cedula, correo=correo
            )
        except ERRORES_INTEGRIDAD:
            return False
        return True

    @staticmethod
    def registrar_empresa(nombre_empresa: str, nit: str, correo: str, contrasena: str) -> bool:
        """True si se creó la cuenta; False si ya existe (NIT o correo repetidos)."""
        try:
            EmpresaModel.crear(nombre=nombre_empresa, nit=nit, correo=correo, contrasena=contrasena)
        except ERRORES_INTEGRIDAD:
            return False
        return True

    @staticmethod
    def autenticar(identificador: str, contrasena: str) -> Optional[Credencial]:
        """Primero busca entre usuarios (personas y administradores) y luego entre empresas."""
        usuario = UsuarioModel.autenticar(identificador, contrasena)
        if usuario:
            return Credencial(tipo=usuario.rol, id=usuario.id_usuario)
        empresa = EmpresaModel.autenticar(identificador, contrasena)
        if empresa:
            return Credencial(tipo=ROL_EMPRESA, id=empresa.id_empresa)
        return None
