"""
AlertMonitor.py
Scheduler que corre cada hora y comprueba alertas AEMET para cada campo.
Solo envía email cuando un tipo de alerta SUBE de nivel respecto al
último estado conocido (ej: verde → amarillo, amarillo → naranja).

Estado persistido en: alert_state.json
"""

import json
import threading
from pathlib import Path
from datetime import datetime

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO
from services.WeatherService import WeatherService
from services.EmailService import EmailService

# ──────────────────────────────────────────────
# RUTA DEL FICHERO DE ESTADO
# ──────────────────────────────────────────────
STATE_FILE = Path(__file__).parent.parent / "alert_state.json"

LEVEL_ORDER = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}
CHECK_INTERVAL_SECONDS = 3600  # 1 hora


class AlertMonitor:

    def __init__(
        self,
        user_dao:        UserDAO,
        field_dao:       FieldDAO,
        point_dao:       PointDAO,
        weather_service: WeatherService,
        email_service:   EmailService,
    ):
        self._user_dao        = user_dao
        self._field_dao       = field_dao
        self._point_dao       = point_dao
        self._weather_service = weather_service
        self._email_service   = email_service
        self._state           = self._load_state()
        self._timer: threading.Timer | None = None

    # ──────────────────────────────────────────────
    # ARRANQUE / PARADA
    # ──────────────────────────────────────────────
    def start(self) -> None:
        """Lanza la primera comprobación y programa las siguientes cada hora."""
        print(f"[AlertMonitor] Iniciado — comprobación cada {CHECK_INTERVAL_SECONDS // 60} min")
        self._schedule_next()

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        print("[AlertMonitor] Detenido")

    # ──────────────────────────────────────────────
    # LÓGICA PRINCIPAL
    # ──────────────────────────────────────────────
    def _schedule_next(self) -> None:
        self._run_check()
        self._timer = threading.Timer(CHECK_INTERVAL_SECONDS, self._schedule_next)
        self._timer.daemon = True
        self._timer.start()

    def _run_check(self) -> None:
        print(f"[AlertMonitor] Comprobando alertas — {datetime.now().strftime('%H:%M:%S')}")
        try:
            # Iterar sobre todos los usuarios y sus campos
            # Nota: en producción con muchos usuarios conviene paginar
            all_fields = self._field_dao.getAllFields()  # ver nota abajo
            for field in all_fields:
                self._check_field(field)
        except Exception as e:
            print(f"[AlertMonitor] Error en comprobación: {e}")

        self._save_state()

    def _check_field(self, field) -> None:
        # Calcular centroide del campo
        points = self._point_dao.getPointsByField(field.id)
        if not points:
            return

        lat = sum(p.latitude  for p in points) / len(points)
        lon = sum(p.longitude for p in points) / len(points)

        # Obtener alertas actuales de AEMET
        try:
            alerts = self._weather_service.get_aemet_alerts(lat, lon)
        except Exception as e:
            print(f"[AlertMonitor] Error AEMET campo {field.id}: {e}")
            return

        # Comparar con estado anterior
        field_key      = str(field.id)
        previous_state = self._state.get(field_key, {})
        new_state      = {}
        alertas_subida = {}

        for tipo in ("calor", "lluvia", "nieve", "granizo"):
            nivel_actual   = alerts.get(tipo, {}).get("nivel", "verde")
            nivel_anterior = previous_state.get(tipo, "verde")
            new_state[tipo] = nivel_actual

            # Solo notificar si el nivel SUBE
            if LEVEL_ORDER[nivel_actual] > LEVEL_ORDER[nivel_anterior]:
                alertas_subida[tipo] = alerts[tipo]

        self._state[field_key] = new_state

        if not alertas_subida:
            return

        # Obtener email del propietario del campo
        user = self._user_dao.getUser(field.user_id)
        if not user or not user.email:
            return

        print(f"[AlertMonitor] Alerta subida en campo '{field.name}' → notificando a {user.email}")
        self._email_service.send_aemet_alert(
            to         = user.email,
            field_name = field.name,
            alerts     = alertas_subida,
        )

    # ──────────────────────────────────────────────
    # PERSISTENCIA DE ESTADO
    # ──────────────────────────────────────────────
    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_state(self) -> None:
        try:
            STATE_FILE.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[AlertMonitor] Error guardando estado: {e}")