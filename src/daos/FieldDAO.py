"""
FieldDAO.py
Acceso a datos de campos agrícolas. Usa el pool de conexiones compartido (db.py).
Cada método obtiene una conexión, la usa y la devuelve al pool automáticamente.
"""

from daos.Db import get_connection
from models.Field import Field


class FieldDAO:

    def __init__(self):
        self._ensure_table()

    # ──────────────────────────────────────────────
    # INICIALIZACIÓN Y MIGRACIÓN
    # ──────────────────────────────────────────────
    def _ensure_table(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fields (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    user_id      INT          NOT NULL,
                    name         VARCHAR(50)  NOT NULL,
                    municipality VARCHAR(50),
                    areaM2       FLOAT,
                    state        VARCHAR(30),
                    crop_type    VARCHAR(50)  DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_name_per_user (user_id, name)
                )
            """)
            conn.commit()
            # Migración: añadir crop_type si la tabla ya existía sin ella
            try:
                cursor.execute(
                    "ALTER TABLE fields ADD COLUMN crop_type VARCHAR(50) DEFAULT ''"
                )
                conn.commit()
            except Exception:
                pass  # La columna ya existe

    # ──────────────────────────────────────────────
    # ESCRITURA
    # ──────────────────────────────────────────────
    def insertField(self, field: Field, user_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fields (user_id, name, municipality, areaM2, state, crop_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    field.name,
                    field.municipality,
                    field.area_m2,
                    getattr(field, "state", "open"),
                    getattr(field, "crop_type", ""),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def updateField(self, field: Field) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE fields
                SET name=%s, municipality=%s, areaM2=%s, state=%s, crop_type=%s
                WHERE id=%s
                """,
                (
                    field.name,
                    field.municipality,
                    field.area_m2,
                    getattr(field, "state", "open"),
                    getattr(field, "crop_type", ""),
                    field.id,
                ),
            )
            conn.commit()
            return cursor.rowcount

    def eliminateField(self, field_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fields WHERE id=%s", (field_id,))
            conn.commit()
            return cursor.rowcount

    # ──────────────────────────────────────────────
    # LECTURA
    # ──────────────────────────────────────────────
    def getField(self, field_id: int) -> Field | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, name, municipality, areaM2, state, crop_type FROM fields WHERE id=%s",
                (field_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_field(row)

    def getAllFieldsByUser(self, user_id: int) -> list[Field]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, name, municipality, areaM2, state, crop_type FROM fields WHERE user_id=%s",
                (user_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_field(r) for r in rows]

    def getAllFields(self) -> list[Field]:
        """Devuelve todos los campos de todos los usuarios. Usado por AlertMonitor."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, name, municipality, areaM2, state, crop_type FROM fields"
            )
            rows = cursor.fetchall()
        return [self._row_to_field(r) for r in rows]

    # ──────────────────────────────────────────────
    # HELPER PRIVADO
    # ──────────────────────────────────────────────
    @staticmethod
    def _row_to_field(row) -> Field:
        f           = Field(name=row[2], municipality=row[3], area_m2=row[4])
        f.id        = row[0]
        f.user_id   = row[1]
        f.state     = row[5]
        f.crop_type = row[6] or ""
        return f