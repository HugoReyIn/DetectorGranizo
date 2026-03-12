"""
FieldService.py
Application Service — orquesta la lógica de negocio de campos y puntos.
No sabe nada de HTTP; recibe y devuelve objetos de dominio o primitivos.
"""

import json

from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO
from models.Field import Field
from models.Point import Point


class FieldService:

    def __init__(self, field_dao: FieldDAO, point_dao: PointDAO):
        self._field_dao = field_dao
        self._point_dao = point_dao

    # ──────────────────────────────────────────────
    # LECTURA
    # ──────────────────────────────────────────────
    def get_fields_for_user(self, user_id: int) -> list[Field]:
        """Devuelve todos los campos del usuario con su centroide calculado."""
        fields = self._field_dao.getAllFieldsByUser(user_id)
        for field in fields:
            points = self._point_dao.getPointsByField(field.id)
            if points:
                field.lat = sum(p.latitude  for p in points) / len(points)
                field.lon = sum(p.longitude for p in points) / len(points)
            else:
                field.lat = None
                field.lon = None
        return fields

    def get_field_if_owned(self, field_id: int, user_id: int) -> Field | None:
        """Devuelve el campo solo si pertenece al usuario, None en caso contrario."""
        field = self._field_dao.getField(field_id)
        if field and field.user_id == user_id:
            return field
        return None

    def get_points_json(self, field_id: int) -> str:
        """Devuelve los puntos del campo serializados como JSON string."""
        points = self._point_dao.getPointsByField(field_id)
        return json.dumps([{"lat": p.latitude, "lng": p.longitude} for p in points])

    # ──────────────────────────────────────────────
    # CREACIÓN
    # ──────────────────────────────────────────────
    def create_field(
        self,
        user_id: int,
        name: str,
        municipality: str,
        area: str,
        points_json: str,
        crop_type: str = "",
    ) -> Field:
        area_float = float(area.replace(",", "."))
        new_field  = Field(name=name, municipality=municipality, area_m2=area_float)
        new_field.state     = "open"
        new_field.crop_type = crop_type
        field_id = self._field_dao.insertField(new_field, user_id)
        new_field.id = field_id

        self._save_points(json.loads(points_json), field_id)
        return new_field

    # ──────────────────────────────────────────────
    # EDICIÓN
    # ──────────────────────────────────────────────
    def update_field(
        self,
        field: Field,
        name: str,
        municipality: str,
        area: str,
        points_json: str,
        crop_type: str = "",
    ) -> Field:
        field.name         = name
        field.municipality = municipality
        field.area_m2      = float(area.replace(",", "."))
        field.crop_type    = crop_type
        self._field_dao.updateField(field)

        self._point_dao.deletePointsByField(field.id)
        self._save_points(json.loads(points_json), field.id)
        return field

    # ──────────────────────────────────────────────
    # ESTADO (abierto / cerrado)
    # ──────────────────────────────────────────────
    def update_state(self, field: Field, new_state: str) -> Field:
        """Actualiza el estado del campo. Lanza ValueError si el estado es inválido."""
        if new_state not in ("open", "closed"):
            raise ValueError(f"Estado inválido: {new_state!r}")
        field.state = new_state
        self._field_dao.updateField(field)
        return field

    # ──────────────────────────────────────────────
    # ELIMINACIÓN
    # ──────────────────────────────────────────────
    def delete_field(self, field_id: int) -> None:
        self._field_dao.eliminateField(field_id)

    # ──────────────────────────────────────────────
    # HELPER PRIVADO
    # ──────────────────────────────────────────────
    def _save_points(self, points_list: list[dict], field_id: int) -> None:
        for p in points_list:
            point = Point(latitude=p["lat"], longitude=p["lng"])
            self._point_dao.insertPoint(point, field_id)