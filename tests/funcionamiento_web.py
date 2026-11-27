import asyncio
import os
import re
import socket
from threading import Thread
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from app import create_app, database
from app.controllers import auth_controller
from app.models.usuario import UsuarioModel


CORREO = "cliente.qa@example.org"
CLAVE = "MaquinaQA12345678!"


@pytest.fixture(scope="module")
def navegador():
    with sync_playwright() as motor:
        visible = os.getenv("MSPS_QA_VISIBLE") == "1"
        browser = motor.chromium.launch(headless=not visible, slow_mo=350 if visible else 0)
        yield browser
        browser.close()


@pytest.fixture
def pagina(navegador, tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "funcionamiento.db")
    monkeypatch.setattr(database.Database, "_instance", None)
    app = create_app()
    with socket.socket() as puerto:
        puerto.bind(("127.0.0.1", 0))
        puerto.listen()
        servidor = uvicorn.Server(uvicorn.Config(
            app,
            log_level="error",
            timeout_keep_alive=1,
            timeout_graceful_shutdown=3,
        ))

        def ejecutar_servidor():
            # Este bucle pertenece solo al servidor HTTP del hilo.
            # Playwright conserva el bucle que necesita para su propio proceso.
            asyncio.run(
                servidor.serve(sockets=[puerto]),
                loop_factory=asyncio.SelectorEventLoop,
            )

        hilo = Thread(target=ejecutar_servidor, daemon=True)
        hilo.start()
        try:
            url = f"http://127.0.0.1:{puerto.getsockname()[1]}"
            with navegador.new_context(base_url=url) as contexto:
                yield contexto.new_page()
        finally:
            servidor.should_exit = True
            hilo.join(timeout=10)
            if hilo.is_alive():
                servidor.force_exit = True
                hilo.join(timeout=5)
            assert not hilo.is_alive(), "El servidor de pruebas sigue abierto después del cierre."


def crear_cliente():
    UsuarioModel.crear_persona_natural("Cliente QA", CLAVE, "1020304050", CORREO)


def ingresar(pagina, clave):
    panel = pagina.locator('[data-auth-panel="login"]')
    if not panel.is_visible():
        pagina.get_by_role("navigation").get_by_role("button", name="Iniciar sesión").click()
    panel.locator('[name="identificador"]').fill(CORREO)
    panel.locator('[name="contrasena"]').fill(clave)
    panel.get_by_role("button", name="Ingresar").click()


def abrir_excavadora(pagina):
    pagina.goto("/maquinas")
    pagina.get_by_placeholder("Buscar máquina...").fill("320D")
    pagina.locator(".maquinas-card").filter(has_text="Caterpillar 320D").click()
    expect(pagina.get_by_role("button", name="Agregar al carrito")).to_be_visible()


def test_registro_confirmacion_y_primer_ingreso(pagina, monkeypatch):
    correo = Mock()
    monkeypatch.setattr(auth_controller, "enviar_verificacion", correo)
    pagina.goto("/")
    pagina.get_by_role("navigation").get_by_role("button", name="Registrarse").click()
    pagina.get_by_role("button", name="Persona natural").click()
    form = pagina.locator('form[action="/registro/persona"]')
    for campo, valor in dict(cedula="1020304050", usuario="Cliente QA", correo=CORREO, contrasena=CLAVE).items():
        form.locator(f'[name="{campo}"]').fill(valor)
    form.get_by_role("button", name="Crear cuenta").click()
    expect(pagina.locator("#aviso-correo")).to_be_visible()
    correo.assert_called_once()
    destinatario, token = correo.call_args.args
    assert destinatario == CORREO
    pagina.goto("/verificar-correo?" + urlencode({"token": token}))
    pagina.get_by_role("button", name="Confirmar mi correo").click()
    expect(pagina.get_by_text("Cuenta creada. Ya puedes iniciar sesión.")).to_be_visible()
    ingresar(pagina, CLAVE)
    expect(pagina.get_by_text("Hola, Cliente QA")).to_be_visible()


def test_login_incorrecto_reintento_y_cierre_de_sesion(pagina):
    crear_cliente()
    pagina.goto("/maquinas")
    ingresar(pagina, "Equivocada!")
    expect(pagina.locator('[data-auth-panel="login"] [data-estado]')).to_have_text("Usuario o contraseña incorrectos.")
    assert pagina.request.get("/api/verificar-login").json() == {"logueado": False}
    ingresar(pagina, CLAVE)
    expect(pagina.get_by_text("Hola, Cliente QA")).to_be_visible()
    pagina.once("dialog", lambda dialogo: dialogo.accept())
    pagina.get_by_role("button", name="Cerrar sesión").click()
    expect(pagina.get_by_role("navigation").get_by_role("button", name="Iniciar sesión")).to_be_visible()
    assert pagina.request.get("/api/verificar-login").json() == {"logueado": False}


def test_visitante_necesita_login_para_agregar(pagina):
    abrir_excavadora(pagina)
    detalle = pagina.url
    pagina.get_by_role("button", name="Agregar al carrito").click()
    expect(pagina.locator('[data-auth-panel="login"]')).to_be_visible()
    expect(pagina).to_have_url(detalle)
    assert pagina.request.get("/api/carrito/cantidad").json()["cantidad"] == 0


def test_carrito_agregar_por_dia_editar_horas_y_eliminar(pagina):
    crear_cliente()
    abrir_excavadora(pagina)
    ingresar(pagina, CLAVE)
    expect(pagina.get_by_text("Hola, Cliente QA")).to_be_visible()
    pagina.locator(".detalle-cantidad .unidad-alquiler").select_option("24")
    pagina.get_by_role("button", name="Agregar al carrito").click()
    linea = pagina.locator(".carrito-item")
    expect(linea).to_have_count(1)
    expect(linea).to_contain_text("Caterpillar 320D")
    expect(linea.locator(".unidad-alquiler")).to_have_value("24")
    expect(linea.locator(".horas-input")).to_have_value("1")
    # La máquina de demostración cuesta 85.000 COP/h; un día son 2.040.000 COP.
    expect(pagina.locator("#subtotal")).to_have_text(re.compile(r"^\$2[.,]040[.,]000$"))
    linea.locator(".unidad-alquiler").select_option("1")
    expect(pagina.locator("#estado-carrito")).to_contain_text("1 h.")
    horas = linea.locator(".horas-input")
    horas.fill("3")
    horas.press("Tab")
    expect(pagina.locator("#estado-carrito")).to_contain_text("3 h.")
    expect(pagina.locator("#total")).to_have_text(re.compile(r"^\$303[.,]450$"))
    pagina.reload()
    expect(linea.locator(".horas-input")).to_have_value("3")
    pagina.once("dialog", lambda dialogo: dialogo.accept())
    linea.get_by_role("button", name="Eliminar").click()
    expect(pagina.get_by_text("Tu carrito está vacío")).to_be_visible()
    assert pagina.request.get("/api/carrito/cantidad").json()["cantidad"] == 0


def test_recuperar_clave_y_volver_a_ingresar(pagina, monkeypatch):
    crear_cliente()
    correo = Mock()
    monkeypatch.setattr(auth_controller, "enviar_recuperacion", correo)
    pagina.goto("/")
    pagina.get_by_role("navigation").get_by_role("button", name="Iniciar sesión").click()
    pagina.get_by_role("link", name="¿Olvidaste tu contraseña?").click()
    form = pagina.locator('form[action="/recuperar"]')
    form.locator('[name="correo"]').fill(CORREO)
    form.get_by_role("button", name="Enviar enlace").click()
    expect(pagina.locator("#aviso-correo")).to_be_visible()
    correo.assert_called_once()
    destinatario, token = correo.call_args.args
    assert destinatario == CORREO
    pagina.goto("/restablecer?" + urlencode({"token": token}))
    nueva = "NuevaClaveQA!"
    pagina.get_by_label("Nueva contraseña").fill(nueva)
    pagina.get_by_role("button", name="Guardar contraseña").click()
    expect(pagina.get_by_role("status").filter(has_text="Tu contraseña se actualizó")).to_be_visible()
    ingresar(pagina, CLAVE)
    expect(pagina.locator('[data-auth-panel="login"] [data-estado]')).to_contain_text("incorrectos")
    ingresar(pagina, nueva)
    expect(pagina.get_by_text("Hola, Cliente QA")).to_be_visible()


def test_ficha_nocturna_y_login_sin_recarga_en_movil(pagina):
    pagina.set_viewport_size({"width": 390, "height": 844})
    pagina.emulate_media(color_scheme="light")
    abrir_excavadora(pagina)
    raiz = pagina.locator("html")
    pagina.get_by_role("button", name="Modo noche").click()
    expect(raiz).to_have_attribute("data-tema", "noche")
    pagina.reload()
    expect(raiz).to_have_attribute("data-tema", "noche")

    celda = pagina.locator(".ficha-tabla td").first
    expect(celda).to_be_visible()
    fondo, tinta = celda.evaluate("""elemento => {
        const estilo = getComputedStyle(elemento);
        return [estilo.backgroundColor, estilo.color];
    }""")
    # En la ficha nocturna se espera una superficie oscura opaca y un texto claro.
    assert fondo.startswith("rgb(") and max(map(int, re.findall(r"\d+", fondo))) < 128, fondo
    assert min(map(int, re.findall(r"\d+", tinta))) > 180, tinta
    assert raiz.evaluate("el => el.scrollWidth <= window.innerWidth")

    # El mismo objeto JS solo existe mientras siga abierto el documento original.
    documento = pagina.evaluate_handle("document")
    pagina.get_by_role("button", name="Agregar al carrito").click()
    expect(pagina.locator('[data-auth-panel="login"]')).to_be_visible()
    assert documento.evaluate("anterior => anterior === document")