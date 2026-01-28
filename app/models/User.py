class Usuario:
    def __init__(self, nombre: str, email: str):
        self.nombre = nombre
        self.email = email
        self.campos = []  # Lista de objetos Campo

    def agregar_campo(self, campo):
        self.campos.append(campo)
