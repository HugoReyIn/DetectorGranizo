from fastapi import APIRouter, HTTPException
from services.FieldService import FieldService

router = APIRouter()
campo_service = FieldService()


@router.get("/campos")
def listar_campos():
    return campo_service.listar_campos()


@router.post("/campos/evaluar")
def evaluar_campos():
    return campo_service.evaluar_todos()


@router.post("/campos/{campo_id}/estado")
def cambiar_estado(campo_id: int, estado: str):
    campo = campo_service.cambiar_estado_manual(campo_id, estado)
    if not campo:
        raise HTTPException(status_code=404, detail="Campo no encontrado")
    return campo
