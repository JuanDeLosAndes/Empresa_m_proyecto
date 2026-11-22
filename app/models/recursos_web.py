import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class RecursoWebNoDisponible(RuntimeError):
    pass


@dataclass(frozen=True)
class RecursoWeb:
    paquete: str
    tipo: str
    bytes: int
    sha256: str
    original: str

    def comprobar(self, contenido: bytes) -> None:
        if len(contenido) != self.bytes or sha256(contenido).hexdigest() != self.sha256:
            raise RecursoWebNoDisponible(f"El contenido no coincide con {self.paquete}.")


MANIFIESTO_WEB = Path(__file__).resolve().parents[1] / "documentos" / "imagenes_web.json"
RECURSOS = {
    ruta: RecursoWeb(**datos)
    for ruta, datos in json.loads(MANIFIESTO_WEB.read_text(encoding="utf-8")).items()
}