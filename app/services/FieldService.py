from models.Field import Field
from services.AemetService import AemetService


class FieldService:

    def __init__(self):
        self.campos = [
            Field(id=1, nombre="Campo 1", ubicacion="Briones", municipio_id="26089", estado="Abierto"),
            Field(id=2, nombre="Campo 2", ubicacion="Haro", municipio_id="26071", estado="Cerrado"),
        ]

    def listar_campos(self):
        return self.campos

    def evaluar_campo(self, campo: Field):
        prediccion = AemetService.get_prediccion_diaria(campo.municipio_id)
        if AemetService.hay_lluvia(prediccion):
            campo.estado = "Cerrado"
        else:
            campo.estado = "Abierto"

        return campo

    def evaluar_todos(self):
        for campo in self.campos:
            self.evaluar_campo(campo)
        return self.campos

    def cambiar_estado_manual(self, campo_id: int, nuevo_estado: str):
        for campo in self.campos:
            if campo.id == campo_id:
                campo.estado = nuevo_estado
                campo.automatico = False
                return campo
        return None
