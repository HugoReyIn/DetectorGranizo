"""
db.py
Pool de conexiones MySQL compartido por todos los DAOs.

Uso en cada método DAO:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(...)
        conn.commit()          # solo en escrituras
        return cursor.fetchall()

El pool crea las conexiones bajo demanda (hasta pool_size=5) y las
reutiliza automáticamente. Si MySQL cierra una conexión por inactividad,
el pool la reemplaza de forma transparente gracias a reconnect=True.

Instalar dependencia (ya incluida con mysql-connector-python):
    pip install mysql-connector-python
"""

from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


# ──────────────────────────────────────────────
# POOL GLOBAL — se crea una sola vez al importar el módulo
# ──────────────────────────────────────────────
_pool = pooling.MySQLConnectionPool(
    pool_name    = "agro_pool",
    pool_size    = 5,          # conexiones simultáneas máximas
    pool_reset_session = True, # limpia el estado de sesión al devolver
    host         = DB_HOST,
    port         = DB_PORT,
    user         = DB_USER,
    password     = DB_PASSWORD,
    database     = DB_NAME,
    autocommit   = False,
    connection_timeout = 10,
)


@contextmanager
def get_connection():
    """
    Context manager que obtiene una conexión del pool y la devuelve
    al salir del bloque with, tanto en caso de éxito como de excepción.

    Ejemplo:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    """
    conn = _pool.get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()   # devuelve la conexión al pool, no la cierra realmente