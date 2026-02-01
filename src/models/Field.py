class Field:
    def __init__(self, name: str = None, municipality: str = None, area_m2: float = None, state: str = "open", field_id: int = None):
        self.id = field_id
        self.name = name if name else "Campo"
        self.municipality = municipality
        self.area_m2 = area_m2
        self.state = state

    def set_state(self, state: str):
        if state not in ["open", "closed"]:
            raise ValueError("State must be 'open' or 'closed'")
        self.state = state

    def __repr__(self):
        return f"Field(id={self.id}, name='{self.name}', municipality='{self.municipality}', area_m2={self.area_m2}, state='{self.state}')"
