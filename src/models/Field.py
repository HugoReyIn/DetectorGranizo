from models.Point import Point

class Field:
    def __init__(self, name: str, points=None, municipality: str = None, area_m2: float = None):
        self.name = name
        self.points = points if points else []
        self.municipality = municipality
        self.area_m2 = area_m2

    def add_point(self, point: Point):
        self.points.append(point)

    def set_municipality(self, municipality: str):
        self.municipality = municipality

    def set_area(self, area: float):
        self.area_m2 = area

    def __repr__(self):
        return (
            f"Field(name='{self.name}', "
            f"municipality='{self.municipality}', "
            f"points={len(self.points)}, "
            f"area_m2={self.area_m2})"
        )
