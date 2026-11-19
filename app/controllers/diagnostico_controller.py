from fastapi import APIRouter, Depends

from app.controllers.dependencias import exigir_admin
from app.current_user import SesionActual
from app.models.diagnostico import estado_almacenes

router = APIRouter()


@router.get("/admin/diagnostico")
def diagnostico(_: SesionActual = Depends(exigir_admin)):
    return estado_almacenes()
