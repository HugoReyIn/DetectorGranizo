class Clima:
    def __init__(self, temperatura: float = None, lluvia: float = None, granizo_prob: float = None):
        self.temperatura = temperatura
        self.lluvia = lluvia
        self.granizo_prob = granizo_prob

    def __str__(self):
        # Maneja valores None de forma segura
        temp = f"{self.temperatura}°C" if self.temperatura is not None else "No disponible"
        lluvia = f"{self.lluvia}mm" if self.lluvia is not None else "No disponible"
        granizo = f"{self.granizo_prob}%" if self.granizo_prob is not None else "No disponible"
        return f"Temp: {temp}, Lluvia: {lluvia}, Prob. granizo: {granizo}"
