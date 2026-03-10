import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from models.Field import Field

class FieldDAO:
    def __init__(self):
        self.conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        self.cursor = self.conn.cursor()
        self.createTable()
        self._migrate()

    def createTable(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(50) NOT NULL,
                municipality VARCHAR(50),
                areaM2 FLOAT,
                state VARCHAR(30),
                crop_type VARCHAR(50) DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_name_per_user (user_id, name)
            )
        """)
        self.conn.commit()

    def _migrate(self):
        """Añade crop_type si no existe (migración automática)."""
        try:
            self.cursor.execute("ALTER TABLE fields ADD COLUMN crop_type VARCHAR(50) DEFAULT ''")
            self.conn.commit()
        except Exception:
            pass  # Ya existe

    def insertField(self, field: Field, user_id: int):
        sql = """
            INSERT INTO fields (user_id, name, municipality, areaM2, state, crop_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        self.cursor.execute(sql, (
            user_id,
            field.name,
            field.municipality,
            field.area_m2,
            getattr(field, "state", "open"),
            getattr(field, "crop_type", "")
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def getField(self, field_id: int):
        self.cursor.execute(
            "SELECT id, user_id, name, municipality, areaM2, state, crop_type FROM fields WHERE id=%s",
            (field_id,)
        )
        row = self.cursor.fetchone()
        if row:
            f = Field(name=row[2], municipality=row[3], area_m2=row[4])
            f.state = row[5]
            f.id = row[0]
            f.user_id = row[1]
            f.crop_type = row[6] or ""
            return f
        return None

    def getAllFieldsByUser(self, user_id: int):
        self.cursor.execute(
            "SELECT id, name, municipality, areaM2, state, crop_type FROM fields WHERE user_id=%s",
            (user_id,)
        )
        rows = self.cursor.fetchall()
        fields = []
        for row in rows:
            f = Field(name=row[1], municipality=row[2], area_m2=row[3])
            f.state = row[4]
            f.id = row[0]
            f.user_id = user_id
            f.crop_type = row[5] or ""
            fields.append(f)
        return fields

    def updateField(self, field: Field):
        sql = """
            UPDATE fields 
            SET name=%s, municipality=%s, areaM2=%s, state=%s, crop_type=%s
            WHERE id=%s
        """
        self.cursor.execute(sql, (
            field.name,
            field.municipality,
            field.area_m2,
            getattr(field, "state", "open"),
            getattr(field, "crop_type", ""),
            field.id
        ))
        self.conn.commit()
        return self.cursor.rowcount

    def eliminateField(self, field_id: int):
        sql = "DELETE FROM fields WHERE id=%s"
        self.cursor.execute(sql, (field_id,))
        self.conn.commit()
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()
        self.conn.close()