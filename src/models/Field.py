from models.Point import Point

class Field:
    def __init__(self, name: str, points=None, municipality: str = None):
        self.name = name
        self.points = points if points else []
        self.municipality = municipality

    def add_point(self, point: Point):
        self.points.append(point)

    def set_municipality(self, municipality: str):
        self.municipality = municipality

    def __repr__(self):
        return (
            f"Field(name='{self.name}', "
            f"municipality='{self.municipality}', "
            f"points={len(self.points)})"
        )
