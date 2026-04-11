"""
AlertMonitor.py
Scheduler que corre cada hora y comprueba alertas para cada campo.
Envía email cuando un tipo de alerta SUBE de nivel (ej: verde → amarillo)
o BAJA de nivel (ej: amarillo → verde = desactivación).

Estado persistido en: ruta definida en config.py → ALERT_STATE_FILE

Mejoras de rendimiento:
  - Los campos se procesan en paralelo con ThreadPoolExecutor (max 8 workers).
    Cada campo requiere llamadas de red a Open-Meteo; procesar en paralelo
    reduce el tiempo de comprobación de N×t a t (siendo t el tiempo de la
    llamada más lenta).
  - La ruta del fichero de estado viene de config.py en lugar de calcularse
    con __file__, lo que evita rutas relativas frágiles.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

from daos.UserDAO import UserDAO
from daos.FieldDAO import FieldDAO
from daos.PointDAO import PointDAO
from services.WeatherService import WeatherService
from services.EmailService import EmailService
from config import ALERT_STATE_FILE

LEVEL_ORDER            = {"verde": 0, "amarillo": 1, "naranja": 2, "rojo": 3}
CHECK_INTERVAL_SECONDS = 3600   # 1 hora
_MAX_WORKERS           = 8      # llamadas paralelas a Open-Meteo

STATE_FILE = Path(ALERT_STATE_FILE)


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
        self._state_lock      = threading.Lock()   # protege _state en escrituras paralelas
        self._timer: threading.Timer | None = None

    # ──────────────────────────────────────────────
    # ARRANQUE / PARADA
    # ──────────────────────────────────────────────
    def start(self) -> None:
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
            all_fields = self._field_dao.getAllFields()
            # Procesar todos los campos en paralelo
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
                futures = {executor.submit(self._check_field, field): field for field in all_fields}
                for future in as_completed(futures):
                    field = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        print(f"[AlertMonitor] Error procesando campo '{field.name}': {e}")
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

        # Obtener alertas actuales
        try:
            alerts = self._weather_service.get_aemet_alerts(lat, lon)
        except Exception as e:
            print(f"[AlertMonitor] Error alertas campo {field.id}: {e}")
            return

        # Comparar con estado anterior
        field_key      = str(field.id)
        with self._state_lock:
            previous_state = self._state.get(field_key, {})

        new_state      = {}
        alertas_subida = {}
        alertas_bajada = {}

        for tipo in ("calor", "lluvia", "nieve", "granizo", "viento",
                     "tormenta", "helada", "niebla"):
            nivel_actual   = alerts.get(tipo, {}).get("nivel", "verde")
            nivel_anterior = previous_state.get(tipo, "verde")
            new_state[tipo] = nivel_actual

            if LEVEL_ORDER[nivel_actual] > LEVEL_ORDER[nivel_anterior]:
                alertas_subida[tipo] = alerts[tipo]
            elif LEVEL_ORDER[nivel_actual] < LEVEL_ORDER[nivel_anterior]:
                alertas_bajada[tipo] = {
                    "nivel_anterior": nivel_anterior,
                    "nivel_actual":   nivel_actual,
                    "valor":          alerts.get(tipo, {}).get("valor"),
                }

        with self._state_lock:
            self._state[field_key] = new_state

        if not alertas_subida and not alertas_bajada:
            return

        # Obtener email del propietario
        user = self._user_dao.getUser(field.user_id)
        if not user or not user.email:
            return

        if alertas_subida:
            print(f"[AlertMonitor] Alerta SUBIDA en '{field.name}' → {user.email}")
            self._email_service.send_aemet_alert(
                to         = user.email,
                field_name = field.name,
                alerts     = alertas_subida,
            )

        if alertas_bajada:
            print(f"[AlertMonitor] Alerta BAJADA en '{field.name}' → {user.email}")
            self._email_service.send_alert_deactivated(
                to         = user.email,
                field_name = field.name,
                alerts     = alertas_bajada,
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
            with self._state_lock:
                snapshot = dict(self._state)
            STATE_FILE.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[AlertMonitor] Error guardando estado: {e}")