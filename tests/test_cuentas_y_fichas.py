from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import create_app, database
from app.models import recuperacion
from app.models.credenciales import validar_correo, validar_contrasena
from app.models.ficha_admin import AltaMaquina
from app.models.usuario import UsuarioModel
from app.models.empresa import EmpresaModel
from app.services import correo as transporte


@pytest.mark.parametrize("correo", ["andres", "a@b", "a@@example.org", "ana..p@example.org", "a@-msps.co"])
def test_rechaza_correo(correo):
    with pytest.raises(ValueError):
        validar_correo(correo)


@pytest.mark.parametrize("clave", ["Ab2!", "todoenminuscula8!", "SinSimbolo8", "Con espacio 8", "Corta1!", "12345678abc!", "12345678Abc"])
def test_rechaza_clave(clave):
    with pytest.raises(ValueError):
        validar_contrasena(clave)


def test_clave_de_ocho_caracteres_sin_numeros():
    validar_contrasena("Maquina!")


@pytest.mark.parametrize("telefono", ["3g15", "tres", "315 001", "１２３", "+", "1" * 41])
def test_telefono_invalido_impide_enviar_correo(telefono):
    from app.models.credenciales import CampoInvalido
    from app.models.registro_verificado import solicitar

    enviar = Mock()
    with pytest.raises(CampoInvalido) as error:
        solicitar("persona", "Ana", "ana@example.org", "Maquina!", "123456", telefono=telefono, enviar=enviar)
    assert error.value.campo == "telefono"
    enviar.assert_not_called()


def test_telefono_opcional_conserva_ceros():
    from app.models.credenciales import validar_telefono

    assert validar_telefono("") is None
    assert validar_telefono("0315551234") == "0315551234"


def test_ficha_requerida():
    base = dict(marca="MSPS", placa="M1", costo_por_hora=10, id_categoria=1)
    for ficha in [None, {}, {" ": "15"}, {"Peso": " "}]:
        with pytest.raises(ValidationError):
            AltaMaquina(**base, ficha_tecnica=ficha)
    assert AltaMaquina(**base, ficha_tecnica={"Peso": "15 t"}).ficha_tecnica == {"Peso": "15 t"}


@pytest.mark.parametrize("tipo", ["persona", "empresa"])
def test_enlace_un_uso_y_caducidad(motor_sql, tipo, monkeypatch):
    correo = "cuenta@example.org"
    if tipo == "persona":
        UsuarioModel.crear_persona_natural("Ana", "Inicial812345678!", "31415", correo)
        autenticar = UsuarioModel.autenticar
    else:
        EmpresaModel.crear(nombre="Empresa", nit="900123456", correo=correo, contrasena="Inicial812345678!")
        autenticar = EmpresaModel.autenticar
    enviar = Mock()
    recuperacion.solicitar("ausente@example.org", enviar)
    enviar.assert_not_called()
    recuperacion.solicitar(correo, enviar)
    recuperacion.solicitar(correo, enviar)
    assert enviar.call_count == 1
    token = enviar.call_args.args[1]
    with pytest.raises(ValueError):
        recuperacion.confirmar(token, "debil")
    recuperacion.confirmar(token, "OtraClave812345678!")
    assert autenticar(correo, "OtraClave812345678!") and not autenticar(correo, "Inicial812345678!")
    with pytest.raises(ValueError):
        recuperacion.confirmar(token, "OtraMas812345678!")
    recuperacion.solicitar(correo, enviar)
    monkeypatch.setattr(recuperacion.time, "time", lambda: 4000000000)
    with pytest.raises(ValueError):
        recuperacion.confirmar(enviar.call_args.args[1], "Expirada812345678!")


def test_modal_y_rutas(motor_sql):
    cliente = TestClient(create_app())
    respuesta = cliente.post("/login", headers={"Accept": "application/json"},
                             data={"identificador": "ausente", "contrasena": "x"})
    assert respuesta.status_code == 401 and "incorrectos" in respuesta.json()["mensaje"]
    for ruta in ["/", "/maquinas", "/maquina/1"]:
        texto = cliente.get(ruta).text
        assert 'data-auth-panel="login"' in texto and "data-tema" in texto
    esquema = cliente.get("/openapi.json").json()["paths"]
    assert cliente.get("/maquina/999999").status_code == 404
    assert "post" in esquema["/admin/maquinas"]
    assert {"put", "delete"} <= esquema["/admin/maquinas/{id_maquinaria}"].keys()
    assert any("patch" in v for v in esquema.values())


def test_transporte_construye_enlaces_separados(monkeypatch):
    smtp = Mock()
    conexion = Mock()
    conexion.__enter__ = Mock(return_value=conexion)
    conexion.__exit__ = Mock(return_value=False)
    smtp.return_value = conexion
    monkeypatch.setattr(transporte.smtplib, "SMTP", smtp)
    for k, v in {"SMTP_HOST":"smtp.example.org", "SMTP_USER":"salida@example.org",
                 "SMTP_PASSWORD":"prueba", "SMTP_PORT":"587", "PUBLIC_BASE_URL":"https://msps.example.org"}.items():
        monkeypatch.setenv(k, v)
    for enviar, ruta in [(transporte.enviar_verificacion, "verificar-correo"),
                         (transporte.enviar_recuperacion, "restablecer")]:
        enviar("entrada@example.org", "prueba-token")
        mensaje = conexion.send_message.call_args.args[0]
        assert mensaje["To"] == "entrada@example.org"
        assert f"https://msps.example.org/{ruta}?token=prueba-token" in mensaje.get_body(preferencelist=("plain",)).get_content()
        html = mensaje.get_body(preferencelist=("html",)).get_content()
        assert "<h1>" in html and f'href="https://msps.example.org/{ruta}?token=prueba-token"' in html
    assert conexion.starttls.call_count == conexion.login.call_count == 2


def test_entrega_fallida_permite_reintento(motor_sql):
    correo = "reintento@example.org"
    UsuarioModel.crear_persona_natural("Reintento", "Prueba12345678!", "31212", correo)
    with pytest.raises(transporte.CorreoNoDisponible):
        recuperacion.solicitar(correo, Mock(side_effect=transporte.CorreoNoDisponible()))
    enviar = Mock()
    recuperacion.solicitar(correo, enviar)
    enviar.assert_called_once()


def test_token_de_registro_no_restablece_clave(motor_sql):
    from app.models import registro_verificado
    enviar = Mock()
    registro_verificado.solicitar("persona", "Ana", "ana@example.org", "Prueba12345678!", "22299", enviar=enviar)
    token = enviar.call_args.args[1]
    with pytest.raises(ValueError):
        recuperacion.confirmar(token, "Nueva12345678!")
    registro_verificado.confirmar(token)
    with pytest.raises(ValueError):
        registro_verificado.confirmar(token)


@pytest.mark.parametrize("cedula", ["123a567", "ABC", "123.456", "１２３４", "12345678901", "", "00000"])
def test_cedula_invalida_impide_solicitar_correo(cedula):
    from app.models.registro_verificado import solicitar
    from app.models.credenciales import CampoInvalido

    enviar = Mock()
    with pytest.raises(CampoInvalido) as error:
        solicitar("persona", "Ana", "ana@example.org", "Prueba12345678!", cedula, enviar=enviar)
    assert error.value.campo == "cedula"
    enviar.assert_not_called()


@pytest.mark.parametrize("cedula", ["12345", "12345678", "1020304050"])
def test_cedula_numerica_se_conserva(cedula):
    from app.models.credenciales import validar_cedula

    assert validar_cedula(cedula) == cedula