from .Wheather import Clima

class Campo:
    def __init__(self, nombre: str, ubicacion: str):
        self.nombre = nombre
        self.ubicacion = ubicacion
        self.techo_activo = False
        self.clima_actual: Clima | None = None  # Puede ser None inicialmente

    def activar_techo(self):
        self.techo_activo = True

    def desactivar_techo(self):
        self.techo_activo = False

    def actualizar_clima(self, clima: Clima):
        self.clima_actual = clima

    def clima_str(self):
        # Devuelve un string seguro para mostrar en HTML
        return str(self.clima_actual) if self.clima_actual else "No disponible"
