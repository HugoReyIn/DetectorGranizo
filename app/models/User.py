from .Wheather import Campo

class Usuario:
    def __init__(self, nombre: str, email: str):
        self.nombre = nombre
        self.email = email
        self.campos: list[Campo] = []

    def agregar_campo(self, campo: Campo):
        self.campos.append(campo)

    def listar_campos(self):
        return self.campos
