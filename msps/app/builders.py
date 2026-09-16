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

    def with_auth_forms(self) -> "PageContextBuilder":
        self._context["login_fields"] = AuthFormFactory.build_login_fields()
        self._context["persona_fields"] = AuthFormFactory.build_register_fields("persona_natural")
        self._context["empresa_fields"] = AuthFormFactory.build_register_fields("empresa")
        return self

    def with_categories(self, categories: list[dict[str, Any]] | None = None) -> "PageContextBuilder":
        self._context["categories"] = categories or [
            {
                "name": "Retroexcavadora",
                "href": "/maquinas?categoria=retroexcavadora",
                "image": None,
                "color": "#2f3b4c",
            },
            {
                "name": "Excavadora",
                "href": "/maquinas?categoria=excavadora",
                "image": "/static/images/hero/hero-excavadora.png",
                "color": "#f5383a",
            },
            {
                "name": "Volqueta",
                "href": "/maquinas?categoria=volqueta",
                "image": None,
                "color": "#ff7020",
            },
        ]
        return self

    def build(self) -> dict[str, Any]:
        return self._context