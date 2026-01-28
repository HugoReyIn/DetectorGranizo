class Clima:
    def __init__(self, temperatura: float = None, lluvia: float = None, granizo_prob: float = None):
        self.temperatura = temperatura
        self.lluvia = lluvia
        self.granizo_prob = granizo_prob

    def __str__(self):
        return f"Temp: {self.temperatura}°C, Lluvia: {self.lluvia}mm, Prob. granizo: {self.granizo_prob}%"
