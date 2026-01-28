from .Wheather import Clima

class Campo:
    def __init__(self, nombre: str, ubicacion: str):
        self.nombre = nombre
        self.ubicacion = ubicacion
        self.techo_activo = False
        self.clima_actual = None  # Objeto Clima

    def activar_techo(self):
        self.techo_activo = True

    def desactivar_techo(self):
        self.techo_activo = False

    def actualizar_clima(self, clima):
        self.clima_actual = clima
