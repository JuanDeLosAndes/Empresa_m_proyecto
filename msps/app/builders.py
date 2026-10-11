# ======================================================================
# QUÉ HACE
#   Arma el diccionario `context` que recibe cada plantilla: título, menú de
#   navegación, campos de los formularios de login y registro, texto de la portada,
#   categorías, sesión y mensajes.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo ensambla datos. No consulta bases de datos: el controlador le entrega lo que
#   ya consultó.
# ======================================================================
"""
Builder del contexto de renderizado de las páginas de MSPS.

Patrón creacional aplicado: BUILDER.
Arma paso a paso (con una interfaz fluida) el diccionario de contexto
que reciben las plantillas: título, ítem de navegación activo, copy del
hero y formularios de autenticación. Evita que el controlador construya
"a mano" un diccionario grande y propenso a errores, y deja explícito
qué partes de la página se están armando.
"""
from __future__ import annotations

from typing import Any

from app.factories import AuthFormFactory


class PageContextBuilder:
    def __init__(self) -> None:
        self._context: dict[str, Any] = {
            "nav_items": [
                {"label": "Inicio", "href": "/", "active": False},
                {"label": "Buscar Maquina", "href": "/maquinas", "active": False},
            ],
            # El navbar (compartido por TODAS las páginas vía base.html)
            # necesita estos tres campos para dibujar los formularios de
            # login/registro, así que se llenan siempre acá y no como un
            # paso opcional aparte: si una página nueva se olvidara de
            # pedirlos, los formularios quedarían vacíos en silencio.
            "login_fields": AuthFormFactory.build_login_fields(),
            "persona_fields": AuthFormFactory.build_register_fields("persona_natural"),
            "empresa_fields": AuthFormFactory.build_register_fields("empresa"),
            # True solo justo después de registrarse: el panel de registro
            # del navbar se abre mostrando el mensaje de éxito.
            "registro_ok": False,
        }

    def with_title(self, title: str) -> "PageContextBuilder":
        self._context["title"] = title
        return self

    def with_active_nav(self, label: str) -> "PageContextBuilder":
        for item in self._context["nav_items"]:
            item["active"] = item["label"] == label
        return self

    def with_hero(self, headline_lines: list[str], subtitle: str) -> "PageContextBuilder":
        self._context["hero"] = {
            "headline_lines": headline_lines,
            "subtitle": subtitle,
        }
        return self

    def with_categories(self, categories: list[dict[str, Any]]) -> "PageContextBuilder":
        # Las categorías ya no viven "a mano" acá: el Controlador las
        # obtiene de CategoriaModel (base de datos) y se las pasa a
        # este método. El Builder solo arma el contexto, no inventa datos.
        self._context["categories"] = categories
        return self

    def with_sesion(self, sesion: dict[str, Any] | None) -> "PageContextBuilder":
        self._context["sesion"] = sesion
        return self

    def with_mensaje(self, mensaje: dict[str, str] | None) -> "PageContextBuilder":
        self._context["mensaje"] = mensaje
        return self

    def with_registro_ok(self, registro_ok: bool) -> "PageContextBuilder":
        self._context["registro_ok"] = registro_ok
        return self

    def build(self) -> dict[str, Any]:
        return self._context

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - Patrón Builder: PageContextBuilder() nace con el menú y los campos de
#     login/registro ya listos (se los pide a AuthFormFactory).
#   - Cada método with_title, with_active_nav, with_hero, with_categories,
#     with_sesion, with_mensaje y with_registro_ok guarda un dato y devuelve `self`,
#     por eso se encadenan con puntos.
#   - build() devuelve el diccionario final.
# USA
#   app/factories.py (AuthFormFactory).
# DÓNDE SE LLAMA
#   controllers/home_controller.py: home, buscar_maquinas, detalle_maquina.
#   controllers/carrito_controller.py: ver_carrito y checkout.
# ======================================================================