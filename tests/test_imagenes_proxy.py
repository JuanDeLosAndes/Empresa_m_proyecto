"""Pruebas del Proxy con caché delante de la base de imágenes."""
from app.repositories.imagen_maquina_repository import ImagenBinaria
from app.repositories.imagen_proxy_repository import ImagenesProxyConCache


class AlmacenFalso:
    """Imita a ImagenesGridFS y cuenta cuántas veces se le pide algo."""

    def __init__(self):
        self.fotos = {}
        self.lecturas = 0

    def obtener(self, archivo):
        self.lecturas += 1
        contenido = self.fotos.get(archivo)
        return None if contenido is None else ImagenBinaria(contenido, "image/jpeg", "h-" + archivo)

    def guardar(self, archivo, contenido, tipo_contenido="image/jpeg"):
        self.fotos[archivo] = contenido
        return True

    def eliminar(self, archivo):
        self.fotos.pop(archivo, None)


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _proxy(**kw):
    real = AlmacenFalso()
    return real, ImagenesProxyConCache(real, **kw)


def test_segunda_lectura_sale_de_la_cache():
    real, proxy = _proxy()
    real.fotos["a.jpg"] = b"x" * 100
    assert proxy.obtener("a.jpg").contenido == b"x" * 100
    assert proxy.obtener("a.jpg").contenido == b"x" * 100
    assert real.lecturas == 1


def test_lo_que_no_existe_no_se_cachea():
    real, proxy = _proxy()
    assert proxy.obtener("no.jpg") is None
    real.fotos["no.jpg"] = b"ya existe"
    assert proxy.obtener("no.jpg").contenido == b"ya existe"


def test_guardar_y_eliminar_invalidan_la_cache():
    real, proxy = _proxy()
    proxy.guardar("a.jpg", b"v1")
    assert proxy.obtener("a.jpg").contenido == b"v1"
    proxy.guardar("a.jpg", b"v2")
    assert proxy.obtener("a.jpg").contenido == b"v2"
    proxy.eliminar("a.jpg")
    assert proxy.obtener("a.jpg") is None


def test_la_cache_expira_con_el_ttl():
    reloj = Reloj()
    real, proxy = _proxy(ttl_segundos=10, reloj=reloj)
    real.fotos["a.jpg"] = b"x"
    proxy.obtener("a.jpg")
    reloj.t = 5
    proxy.obtener("a.jpg")
    assert real.lecturas == 1
    reloj.t = 11
    proxy.obtener("a.jpg")
    assert real.lecturas == 2


def test_expulsa_la_menos_usada_al_llenarse():
    real, proxy = _proxy(max_bytes=250)
    for nombre in ("a", "b", "c"):
        real.fotos[nombre] = b"x" * 100
    proxy.obtener("a")
    proxy.obtener("b")
    proxy.obtener("a")  # "a" se usó hace poco; "b" es la menos usada
    proxy.obtener("c")  # no cabe: se expulsa "b"
    assert proxy.bytes_en_cache == 200 and len(proxy) == 2
    real.lecturas = 0
    proxy.obtener("a")
    proxy.obtener("c")
    assert real.lecturas == 0
    proxy.obtener("b")
    assert real.lecturas == 1


def test_una_foto_mas_grande_que_toda_la_cache_no_se_guarda():
    real, proxy = _proxy(max_bytes=50)
    real.fotos["grande"] = b"x" * 100
    proxy.obtener("grande")
    assert len(proxy) == 0 and proxy.bytes_en_cache == 0


def test_la_fabrica_entrega_siempre_el_mismo_proxy():
    from app.factories import crear_imagenes_repositorio

    assert crear_imagenes_repositorio() is crear_imagenes_repositorio()