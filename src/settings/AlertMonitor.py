"""
AlertMonitor.py
Scheduler que corre cada hora y comprueba alertas para cada campo.

Funcionalidades:
  1. Envía email cuando una alerta SUBE o BAJA de nivel.
  2. Cierra el techo automáticamente si el riesgo de granizo >= 35%.
  3. Reabre el techo automáticamente si el riesgo baja del 35%
     Y fue el sistema quien lo cerró (no el agricultor manualmente).

El umbral del 35% es el mismo que usa el frontend (agro.js / field.js).
El cierre/apertura se registra en el estado persistido para distinguir
cierres automáticos de cierres manuales.
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
_MAX_WORKERS           = 8
HAIL_CLOSE_THRESHOLD   = 35.0   # % — mismo umbral que el frontend

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
        self._state_lock      = threading.Lock()
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
        points = self._point_dao.getPointsByField(field.id)
        if not points:
            return

        lat = sum(p.latitude  for p in points) / len(points)
        lon = sum(p.longitude for p in points) / len(points)

        # ── 1. Alertas meteorológicas ──
        try:
            alerts = self._weather_service.get_aemet_alerts(lat, lon)
        except Exception as e:
            print(f"[AlertMonitor] Error alertas campo {field.id}: {e}")
            return

        field_key = str(field.id)
        with self._state_lock:
            previous_state = self._state.get(field_key, {})

        new_state      = {}
        alertas_subida = {}
        alertas_bajada = {}

        for tipo in ("calor", "lluvia", "nieve", "granizo", "viento",
                     "tormenta", "helada", "niebla"):
            nivel_actual   = alerts.get(tipo, {}).get("nivel", "verde")
            valor_actual   = alerts.get(tipo, {}).get("valor")
            nivel_anterior = previous_state.get(tipo, {}).get("nivel", "verde") \
                             if isinstance(previous_state.get(tipo), dict) \
                             else previous_state.get(tipo, "verde")

            # Guardar como dict {nivel, valor} en lugar de solo el string de nivel
            new_state[tipo] = {"nivel": nivel_actual, "valor": valor_actual}

            if LEVEL_ORDER[nivel_actual] > LEVEL_ORDER[nivel_anterior]:
                alertas_subida[tipo] = alerts[tipo]
            elif LEVEL_ORDER[nivel_actual] < LEVEL_ORDER[nivel_anterior]:
                alertas_bajada[tipo] = {
                    "nivel_anterior": nivel_anterior,
                    "nivel_actual":   nivel_actual,
                    "valor":          valor_actual,
                }

        # ── 2. Control automático del techo por granizo ──
        self._check_hail_roof(field, lat, lon, previous_state, new_state)

        with self._state_lock:
            self._state[field_key] = new_state

        if not alertas_subida and not alertas_bajada:
            return

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
    # CONTROL AUTOMÁTICO DEL TECHO
    # ──────────────────────────────────────────────
    def _check_hail_roof(self, field, lat: float, lon: float,
                         previous_state: dict, new_state: dict) -> None:
        """
        Cierra el techo si el riesgo de granizo >= 35% en las próximas 6h.
        Lo reabre si baja del 35% Y fue el sistema quien lo cerró.
        El estado 'auto_closed' se persiste en new_state para distinguirlo
        de un cierre manual por el agricultor.
        """
        try:
            hail_prediction = self._weather_service.get_hail_prediction(lat, lon)
        except Exception as e:
            print(f"[AlertMonitor] Error predicción granizo campo {field.id}: {e}")
            return

        # Calcular riesgo máximo próximas 6h
        now   = datetime.now()
        in_6h = now.timestamp() + 6 * 3600
        probs = [
            p["hail_probability"]
            for p in hail_prediction
            if datetime.fromisoformat(p["time"]).timestamp() <= in_6h
        ]
        hail_max = max(probs) if probs else 0.0

        # Recuperar si el sistema cerró este campo anteriormente
        auto_closed = previous_state.get("auto_closed", False)

        # Propagar el flag al nuevo estado por defecto
        new_state["auto_closed"] = auto_closed
        new_state["hail_max_6h"] = round(hail_max, 1)

        current_state = field.state  # "open" o "closed"

        if hail_max >= HAIL_CLOSE_THRESHOLD:
            # Cerrar si está abierto y no está ya cerrado
            if current_state != "closed":
                print(f"[AlertMonitor] 🧊 Granizo {hail_max:.0f}% — cerrando techo '{field.name}'")
                field.state = "closed"
                self._field_dao.updateField(field)
                new_state["auto_closed"] = True

                # Notificar al usuario
                user = self._user_dao.getUser(field.user_id)
                if user and user.email:
                    self._email_service.send_aemet_alert(
                        to         = user.email,
                        field_name = field.name,
                        alerts     = {"granizo": {
                            "nivel": "rojo",
                            "valor": f"IA: {hail_max:.0f}% riesgo — techo cerrado automáticamente",
                        }},
                    )
            else:
                print(f"[AlertMonitor] 🧊 Granizo {hail_max:.0f}% en '{field.name}' — techo ya cerrado")

        else:
            # Reabrir solo si fue el sistema quien lo cerró
            if current_state == "closed" and auto_closed:
                print(f"[AlertMonitor] ✅ Granizo {hail_max:.0f}% — reabriendo techo '{field.name}'")
                field.state = "open"
                self._field_dao.updateField(field)
                new_state["auto_closed"] = False

                user = self._user_dao.getUser(field.user_id)
                if user and user.email:
                    self._email_service.send_alert_deactivated(
                        to         = user.email,
                        field_name = field.name,
                        alerts     = {"granizo": {
                            "nivel_anterior": "rojo",
                            "nivel_actual":   "verde",
                            "valor":          f"Riesgo reducido a {hail_max:.0f}% — techo reabierto automáticamente",
                        }},
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