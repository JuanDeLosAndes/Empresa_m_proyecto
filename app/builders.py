
from __future__ import annotations

from typing import Any

from app.formularios import AuthFormFactory


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

    def with_category_cards(
        self,
        categorias: list[Any],
        imagenes: dict[str, dict[str, Any]],
        color: str = "#ff7020",
    ) -> "PageContextBuilder":
        # Las tarjetas de la portada (enlace, color e imagen) son datos de VISTA: se
        # arman aquí y no en el controlador. `categorias` vienen de CategoriaModel y
        # `imagenes` del controlador ({nombre: {"url": ..., "foto": ...}}).
        self._context["categories"] = [
            {
                "name": c.nombre_categoria,
                "href": f"/maquinas?categoria={c.nombre_categoria}",
                "image": imagenes.get(c.nombre_categoria, {}).get("url"),
                "image_foto": imagenes.get(c.nombre_categoria, {}).get("foto", False),
                "color": color,
            }
            for c in categorias
        ]
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
