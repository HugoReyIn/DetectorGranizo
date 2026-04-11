"""
constants.py
Constantes compartidas entre servicios y monitores.
Importar desde aquí para evitar duplicación y posibles inconsistencias.
"""

# Orden numérico de niveles de alerta — cuanto mayor el número, más grave
LEVEL_ORDER: dict[str, int] = {
    "verde":    0,
    "amarillo": 1,
    "naranja":  2,
    "rojo":     3,
}

# Tipos de alerta manejados por el sistema
ALERT_TYPES: tuple[str, ...] = (
    "calor", "lluvia", "nieve", "granizo",
    "viento", "tormenta", "helada", "niebla",
)