import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from models.User import User

class UserDAO:
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

    def createTable(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                name VARCHAR(50) NOT NULL
            )
        """)
        self.conn.commit()

    def insertUser(self, user: User):
        sql = "INSERT INTO users (email, password, name) VALUES (%s, %s, %s)"
        self.cursor.execute(sql, (user.email, user.password, user.name))
        self.conn.commit()
        return self.cursor.lastrowid

    def getUser(self, userId: int):
        self.cursor.execute(
            "SELECT id, email, password, name FROM users WHERE id=%s",
            (userId,)
        )
        row = self.cursor.fetchone()
        if row:
            u = User(email=row[1], password=row[2], name=row[3])
            u.id = row[0]
            return u
        return None

    def getUserByEmail(self, email: str):
        self.cursor.execute(
            "SELECT id, email, password, name FROM users WHERE email=%s",
            (email,)
        )
        row = self.cursor.fetchone()
        if row:
            u = User(email=row[1], password=row[2], name=row[3])
            u.id = row[0]
            return u
        return None

    def updateUser(self, user: User):
        sql = "UPDATE users SET email=%s, password=%s, name=%s WHERE id=%s"
        self.cursor.execute(sql, (user.email, user.password, user.name, user.id))
        self.conn.commit()
        return self.cursor.rowcount

    def eliminateUser(self, userId: int):
        sql = "DELETE FROM users WHERE id=%s"
        self.cursor.execute(sql, (userId,))
        self.conn.commit()
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()
        self.conn.close()
