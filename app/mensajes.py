
from __future__ import annotations

from typing import Mapping, Optional

Mensaje = dict[str, str]


def mensaje_de_inicio(params: Mapping[str, str]) -> Optional[Mensaje]:
    """Mensajes de la portada tras iniciar sesión o fallar un registro."""
    if params.get("login") == "ok":
        return {"tipo": "exito", "texto": "Inicio de sesión exitoso."}
    if params.get("login") == "error":
        return {"tipo": "error", "texto": "Usuario o contraseña incorrectos."}
    if params.get("registro") == "error":
        return {"tipo": "error", "texto": "No se pudo crear la cuenta (verifica los datos)."}
    return None


def mensaje_de_fotos(params: Mapping[str, str]) -> Optional[Mensaje]:
    """Mensajes de la página de fotos del administrador."""
    if params.get("subidas", "").isdigit() and params.get("rechazadas", "").isdigit():
        ok, mal = int(params["subidas"]), int(params["rechazadas"])
        if mal:
            return {
                "tipo": "error",
                "texto": f"Subidas: {ok}. Rechazadas: {mal} (formato no válido, más de 10 MB o galería llena).",
            }
        return {"tipo": "exito", "texto": f"Fotos subidas: {ok}."}
    if params.get("hecho") in {"portada", "eliminada"}:
        texto = "Portada actualizada." if params["hecho"] == "portada" else "Foto eliminada."
        return {"tipo": "exito", "texto": texto}
    if params.get("error") == "mongo":
        return {"tipo": "error", "texto": "MongoDB no respondió. No se hizo ningún cambio; inténtalo de nuevo."}
    return None

