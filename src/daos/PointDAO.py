import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from models.Point import Point

class PointDAO:
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

    # Crear tabla points
    def createTable(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS points (
                id INT AUTO_INCREMENT PRIMARY KEY,
                field_id INT NOT NULL,
                latitude DOUBLE NOT NULL,
                longitude DOUBLE NOT NULL,
                FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    # Insertar un punto asociado a un field_id
    def insertPoint(self, point: Point, field_id: int):
        sql = "INSERT INTO points (field_id, latitude, longitude) VALUES (%s, %s, %s)"
        self.cursor.execute(sql, (field_id, point.latitude, point.longitude))
        self.conn.commit()
        return self.cursor.lastrowid

    # Obtener un punto por su ID
    def getPoint(self, point_id: int):
        self.cursor.execute(
            "SELECT id, field_id, latitude, longitude FROM points WHERE id=%s",
            (point_id,)
        )
        row = self.cursor.fetchone()
        if row:
            p = Point(latitude=row[2], longitude=row[3])
            p.id = row[0]
            p.field_id = row[1]
            return p
        return None

    # Obtener todos los puntos de un campo (field_id)
    def getPointsByField(self, field_id: int):
        self.cursor.execute(
            "SELECT id, latitude, longitude FROM points WHERE field_id=%s",
            (field_id,)
        )
        rows = self.cursor.fetchall()
        points = []
        for row in rows:
            p = Point(latitude=row[1], longitude=row[2])
            p.id = row[0]
            p.field_id = field_id
            points.append(p)
        return points

    # Actualizar un punto existente
    def updatePoint(self, point: Point):
        sql = "UPDATE points SET latitude=%s, longitude=%s WHERE id=%s"
        self.cursor.execute(sql, (point.latitude, point.longitude, point.id))
        self.conn.commit()
        return self.cursor.rowcount

    # Eliminar un punto
    def deletePoint(self, point_id: int):
        sql = "DELETE FROM points WHERE id=%s"
        self.cursor.execute(sql, (point_id,))
        self.conn.commit()
        return self.cursor.rowcount

    # Cerrar conexión
    def close(self):
        self.cursor.close()
        self.conn.close()
