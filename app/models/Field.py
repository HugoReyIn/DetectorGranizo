from pydantic import BaseModel
from typing import Optional


class Field(BaseModel):
    id: int
    nombre: str
    ubicacion: str
    municipio_id: str
    estado: str
    automatico: bool = True


class FieldStatusResponse(BaseModel):
    campo_id: int
    estado: str
    mensaje: Optional[str] = None
