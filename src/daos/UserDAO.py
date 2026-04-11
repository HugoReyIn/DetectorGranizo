"""
UserDAO.py
Acceso a datos de usuarios. Usa el pool de conexiones compartido (db.py).
Cada método obtiene una conexión, la usa y la devuelve al pool automáticamente.
"""

from daos.Db import get_connection
from models.User import User


class UserDAO:

    def __init__(self):
        self._ensure_table()

    # ──────────────────────────────────────────────
    # INICIALIZACIÓN
    # ──────────────────────────────────────────────
    def _ensure_table(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id       INT AUTO_INCREMENT PRIMARY KEY,
                    email    VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(100) NOT NULL,
                    name     VARCHAR(50)  NOT NULL
                )
            """)
            conn.commit()

    # ──────────────────────────────────────────────
    # ESCRITURA
    # ──────────────────────────────────────────────
    def insertUser(self, user: User) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password, name) VALUES (%s, %s, %s)",
                (user.email, user.password, user.name),
            )
            conn.commit()
            return cursor.lastrowid

    def updateUser(self, user: User) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET email=%s, password=%s, name=%s WHERE id=%s",
                (user.email, user.password, user.name, user.id),
            )
            conn.commit()
            return cursor.rowcount

    def eliminateUser(self, user_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
            conn.commit()
            return cursor.rowcount

    # ──────────────────────────────────────────────
    # LECTURA
    # ──────────────────────────────────────────────
    def getUser(self, user_id: int) -> User | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, email, password, name FROM users WHERE id=%s",
                (user_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        u = User(email=row[1], password=row[2], name=row[3])
        u.id = row[0]
        return u

    def getUserByEmail(self, email: str) -> User | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, email, password, name FROM users WHERE email=%s",
                (email,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        u = User(email=row[1], password=row[2], name=row[3])
        u.id = row[0]
        return u