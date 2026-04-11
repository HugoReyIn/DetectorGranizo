"""
PointDAO.py
Acceso a datos de puntos geográficos de campos. Usa el pool compartido (db.py).
Cada método obtiene una conexión, la usa y la devuelve al pool automáticamente.
"""

from daos.Db import get_connection
from models.Point import Point


class PointDAO:

    def __init__(self):
        self._ensure_table()

    # ──────────────────────────────────────────────
    # INICIALIZACIÓN
    # ──────────────────────────────────────────────
    def _ensure_table(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS points (
                    id        INT AUTO_INCREMENT PRIMARY KEY,
                    field_id  INT    NOT NULL,
                    latitude  DOUBLE NOT NULL,
                    longitude DOUBLE NOT NULL,
                    FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    # ──────────────────────────────────────────────
    # ESCRITURA
    # ──────────────────────────────────────────────
    def insertPoint(self, point: Point, field_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO points (field_id, latitude, longitude) VALUES (%s, %s, %s)",
                (field_id, point.latitude, point.longitude),
            )
            conn.commit()
            return cursor.lastrowid

    def deletePointsByField(self, field_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM points WHERE field_id=%s", (field_id,))
            conn.commit()
            return cursor.rowcount

    # ──────────────────────────────────────────────
    # LECTURA
    # ──────────────────────────────────────────────
    def getPointsByField(self, field_id: int) -> list[Point]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, latitude, longitude FROM points WHERE field_id=%s",
                (field_id,),
            )
            rows = cursor.fetchall()
        points = []
        for row in rows:
            p           = Point(latitude=row[1], longitude=row[2])
            p.id        = row[0]
            p.field_id  = field_id
            points.append(p)
        return points