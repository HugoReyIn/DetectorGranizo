"""
logging_config.py
Configuración centralizada del sistema de logging.
Llamar a setup_logging() una sola vez al arrancar la app en Main.py.

Niveles:
  - DEBUG:   detalles internos de cálculo (alertas, cachés, índices)
  - INFO:    eventos normales del ciclo de vida (inicio, parada, emails)
  - WARNING: situaciones inesperadas pero recuperables
  - ERROR:   fallos que impiden completar una operación

En producción cambiar level=logging.INFO → level=logging.WARNING
para reducir el volumen de logs.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configura el logger raíz con formato legible y salida a stdout.
    Llamar una sola vez al inicio de Main.py:

        from logging_config import setup_logging
        setup_logging()
    """
    logging.basicConfig(
        level   = level,
        stream  = sys.stdout,
        format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S",
    )