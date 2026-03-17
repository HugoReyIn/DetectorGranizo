"""
EmailService.py
Responsabilidad única: enviar emails via Gmail SMTP.
No conoce nada de AEMET ni de campos — solo recibe asunto y cuerpo.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM


class EmailService:

    def send(self, to: str, subject: str, body_html: str) -> bool:
        """
        Envía un email HTML.

        Returns:
            True si se envió correctamente, False si falló.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"]      = to
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to, msg.as_string())

            print(f"[EmailService] Email enviado a {to}: {subject}")
            return True

        except Exception as e:
            print(f"[EmailService] Error enviando email a {to}: {e}")
            return False

    def send_aemet_alert(self, to: str, field_name: str, alerts: dict) -> bool:
        """
        Envía un email de alerta AEMET formateado para un campo concreto.

        alerts: dict con claves calor/lluvia/nieve/granizo,
                cada una con {"nivel": "amarillo"|"naranja"|"rojo", "valor": ...}
        """
        NIVEL_COLOR = {
            "amarillo": "#F59E0B",
            "naranja":  "#EA580C",
            "rojo":     "#DC2626",
        }
        NIVEL_EMOJI = {
            "amarillo": "⚠️",
            "naranja":  "🔶",
            "rojo":     "🚨",
        }
        TIPO_LABEL = {
            "calor":   "Calor",
            "lluvia":  "Lluvia / Tormentas",
            "nieve":   "Nieve",
            "granizo": "Granizo",
        }

        # Solo incluir alertas que no sean verdes
        alertas_activas = {
            tipo: info for tipo, info in alerts.items()
            if tipo != "ticker" and info.get("nivel", "verde") != "verde"
        }

        if not alertas_activas:
            return False

        nivel_maximo = max(
            alertas_activas.values(),
            key=lambda x: {"amarillo": 1, "naranja": 2, "rojo": 3}.get(x["nivel"], 0)
        )["nivel"]

        color_cabecera = NIVEL_COLOR.get(nivel_maximo, "#F59E0B")
        emoji_cabecera = NIVEL_EMOJI.get(nivel_maximo, "⚠️")

        filas_alertas = ""
        for tipo, info in alertas_activas.items():
            nivel  = info["nivel"]
            color  = NIVEL_COLOR.get(nivel, "#F59E0B")
            emoji  = NIVEL_EMOJI.get(nivel, "⚠️")
            valor  = f" — {info['valor']}" if info.get("valor") else ""
            filas_alertas += f"""
            <tr>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;">
                    {emoji} <strong>{TIPO_LABEL.get(tipo, tipo.capitalize())}</strong>
                </td>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;">
                    <span style="
                        background:{color};color:#fff;
                        padding:3px 10px;border-radius:20px;
                        font-size:12px;font-weight:700;
                    ">{nivel.upper()}</span>
                    <span style="color:#666;font-size:13px;">{valor}</span>
                </td>
            </tr>"""

        body_html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;padding:0;background:#F2ECD8;font-family:'Segoe UI',Arial,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2ECD8;padding:32px 0;">
                <tr><td align="center">
                    <table width="520" cellpadding="0" cellspacing="0"
                           style="background:#fff;border-radius:16px;overflow:hidden;
                                  box-shadow:0 4px 20px rgba(0,0,0,0.10);">

                        <!-- Cabecera -->
                        <tr>
                            <td style="background:{color_cabecera};padding:28px 32px;text-align:center;">
                                <div style="font-size:36px;margin-bottom:8px;">{emoji_cabecera}</div>
                                <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">
                                    Alerta meteorológica
                                </h1>
                                <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">
                                    Campo: <strong>{field_name}</strong>
                                </p>
                            </td>
                        </tr>

                        <!-- Cuerpo -->
                        <tr>
                            <td style="padding:28px 32px;">
                                <p style="margin:0 0 20px;color:#444;font-size:14px;line-height:1.6;">
                                    AEMET ha emitido nuevas alertas para tu campo
                                    <strong>{field_name}</strong>. Revisa los niveles de alerta
                                    activos y toma las medidas necesarias.
                                </p>

                                <table width="100%" cellpadding="0" cellspacing="0"
                                       style="border:1px solid #e8e0cc;border-radius:10px;
                                              overflow:hidden;font-size:14px;">
                                    <thead>
                                        <tr style="background:#FAF3E0;">
                                            <th style="padding:10px 14px;text-align:left;
                                                       color:#2D4A22;font-size:11px;
                                                       text-transform:uppercase;letter-spacing:0.6px;">
                                                Tipo
                                            </th>
                                            <th style="padding:10px 14px;text-align:left;
                                                       color:#2D4A22;font-size:11px;
                                                       text-transform:uppercase;letter-spacing:0.6px;">
                                                Nivel
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>{filas_alertas}</tbody>
                                </table>

                                <p style="margin:24px 0 0;color:#888;font-size:12px;text-align:center;">
                                    DetectorGranizo · Gestión agrícola inteligente
                                </p>
                            </td>
                        </tr>

                    </table>
                </td></tr>
            </table>
        </body>
        </html>
        """

        nivel_txt = nivel_maximo.capitalize()
        subject   = f"{emoji_cabecera} Alerta {nivel_txt} AEMET — {field_name}"
        return self.send(to, subject, body_html)

    def send_alert_deactivated(self, to: str, field_name: str, alerts: dict) -> bool:
        """
        Envía un email informando de que una o varias alertas han bajado de nivel
        (desactivación total o mejora de nivel).

        alerts: dict con clave = tipo_alerta, valor = {nivel_anterior, nivel_actual, valor}
        """
        NIVEL_COLOR = {
            "amarillo": "#F59E0B",
            "naranja":  "#EA580C",
            "rojo":     "#DC2626",
            "verde":    "#4A7C3F",
        }
        TIPO_LABEL = {
            "calor":    "Calor",
            "lluvia":   "Lluvia / Tormentas",
            "nieve":    "Nieve",
            "granizo":  "Granizo",
            "viento":   "Viento fuerte",
            "tormenta": "Tormenta",
            "helada":   "Helada",
            "niebla":   "Niebla",
        }
        NIVEL_ARROW = {
            "verde":    "✅ Sin alerta",
            "amarillo": "⚠️ Amarillo",
            "naranja":  "🔶 Naranja",
            "rojo":     "🚨 Rojo",
        }

        filas = ""
        for tipo, info in alerts.items():
            ant   = info["nivel_anterior"]
            act   = info["nivel_actual"]
            valor = f" ({info['valor']})" if info.get("valor") else ""
            filas += f"""
            <tr>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;">
                    <strong>{TIPO_LABEL.get(tipo, tipo.capitalize())}</strong>
                </td>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;">
                    <span style="
                        background:{NIVEL_COLOR.get(ant,'#ccc')};color:#fff;
                        padding:3px 10px;border-radius:20px;
                        font-size:12px;font-weight:700;
                    ">{ant.upper()}</span>
                </td>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;
                           color:#555;font-size:18px;text-align:center;">→</td>
                <td style="padding:10px 14px;border-bottom:1px solid #f0ece0;">
                    <span style="
                        background:{NIVEL_COLOR.get(act,'#4A7C3F')};color:#fff;
                        padding:3px 10px;border-radius:20px;
                        font-size:12px;font-weight:700;
                    ">{act.upper()}</span>
                    <span style="color:#666;font-size:12px;">{valor}</span>
                </td>
            </tr>"""

        body_html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <body style="margin:0;padding:0;background:#F2ECD8;font-family:'Segoe UI',Arial,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2ECD8;padding:32px 0;">
                <tr><td align="center">
                    <table width="560" cellpadding="0" cellspacing="0"
                           style="background:#fff;border-radius:16px;overflow:hidden;
                                  box-shadow:0 4px 20px rgba(0,0,0,0.10);">

                        <!-- Cabecera verde -->
                        <tr>
                            <td style="background:#4A7C3F;padding:28px 32px;text-align:center;">
                                <div style="font-size:36px;margin-bottom:8px;">✅</div>
                                <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">
                                    Mejora en alertas meteorológicas
                                </h1>
                                <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">
                                    Campo: <strong>{field_name}</strong>
                                </p>
                            </td>
                        </tr>

                        <!-- Cuerpo -->
                        <tr>
                            <td style="padding:28px 32px;">
                                <p style="margin:0 0 20px;color:#444;font-size:14px;line-height:1.6;">
                                    Las siguientes alertas han <strong>bajado de nivel</strong>
                                    o han sido <strong>desactivadas</strong> para el campo
                                    <strong>{field_name}</strong>.
                                </p>

                                <table width="100%" cellpadding="0" cellspacing="0"
                                       style="border:1px solid #e8e0cc;border-radius:10px;
                                              overflow:hidden;font-size:14px;">
                                    <thead>
                                        <tr style="background:#FAF3E0;">
                                            <th style="padding:10px 14px;text-align:left;color:#2D4A22;
                                                font-size:11px;text-transform:uppercase;letter-spacing:0.6px;">
                                                Tipo
                                            </th>
                                            <th style="padding:10px 14px;text-align:left;color:#2D4A22;
                                                font-size:11px;text-transform:uppercase;letter-spacing:0.6px;">
                                                Antes
                                            </th>
                                            <th style="padding:4px;"></th>
                                            <th style="padding:10px 14px;text-align:left;color:#2D4A22;
                                                font-size:11px;text-transform:uppercase;letter-spacing:0.6px;">
                                                Ahora
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>{filas}</tbody>
                                </table>

                                <p style="margin:24px 0 0;color:#888;font-size:12px;text-align:center;">
                                    DetectorGranizo · Gestión agrícola inteligente
                                </p>
                            </td>
                        </tr>

                    </table>
                </td></tr>
            </table>
        </body>
        </html>
        """

        subject = f"✅ Mejora de alertas AEMET — {field_name}"
        return self.send(to, subject, body_html)