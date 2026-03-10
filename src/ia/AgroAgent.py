"""
AgroAgent.py — Agente agronómico local
Genera interpretaciones específicas por cultivo para los 8 indicadores del dashboard.
Sin API externa, sin coste, respuesta instantánea.
"""

from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# BASE DE CONOCIMIENTO POR CULTIVO
# Cada cultivo define umbrales y mensajes para los 8 indicadores
# ─────────────────────────────────────────────────────────────────────────────

CROP_PROFILES = {
    "trigo": {
        "nombre": "trigo",
        "et0": {
            "umbrales": [
                (0,   1.5, "ok",      "💧 ET₀ baja — el trigo no requiere riego ahora"),
                (1.5, 3.5, "ok",      "💧 ET₀ moderada — humedad suficiente para el cereal"),
                (3.5, 5.0, "warning", "⚠️ ET₀ alta — vigila humedad en encañado"),
                (5.0, 99,  "danger",  "🚨 ET₀ muy alta — riego urgente, riesgo de aborto de espiga"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — condiciones óptimas para aplicar fungicidas"),
                (3,  6,  "ok",      "☀️ UV moderado — fotosíntesis activa en trigo"),
                (6,  8,  "warning", "⚠️ UV alto — evita tratamientos en horas centrales"),
                (8,  99, "danger",  "🔥 UV muy alto — aplica tratamientos antes de las 10h"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — riesgo de tormenta, protege del encamado"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, vigila roya y mildiu"),
                (1005, 1020, "ok",      "🌤️ Presión normal — condiciones estables para el trigo"),
                (1020, 9999, "ok",      "☀️ Presión alta — tiempo seco, ideal para recolección"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   150, "warning", "☁️ Radiación baja — fotosíntesis limitada, puede retrasar espigazón"),
                (150, 400, "ok",      "🌤️ Radiación moderada — buena actividad fotosintética"),
                (400, 700, "ok",      "☀️ Radiación alta — llenado de grano óptimo"),
                (700, 9999,"warning", "🔆 Radiación máxima — posible estrés térmico en grano lechoso"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.15, "danger",  "🏜️ Suelo muy seco — riesgo de esterilidad en espiga"),
                (0.15,0.30, "warning", "⚠️ Humedad baja — regar si está en encañado o floración"),
                (0.30,0.60, "ok",      "✅ Humedad óptima para el trigo"),
                (0.60,1.0,  "warning", "💦 Suelo saturado — riesgo de enfermedades de pie"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   4,  "warning", "❄️ Suelo frío — germinación lenta, espera para sembrar"),
                (4,   12, "ok",      "🌱 Temperatura adecuada — germinación activa del trigo"),
                (12,  22, "ok",      "✅ Temperatura óptima — máxima actividad radicular"),
                (22,  99, "warning", "🔥 Suelo cálido — posible estrés en raíces superficiales"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "warning", "⚠️ Pocas horas de frío — riesgo de vernalización incompleta"),
                (2,  6,  "ok",      "🌡️ Horas de frío moderadas — vernalización en curso"),
                (6,  10, "ok",      "✅ Buena acumulación de frío — desarrollo correcto"),
                (10, 99, "ok",      "❄️ Muchas horas de frío — vernalización completa"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Riesgo mínimo de granizo"),
                (20, 50, "warning", "⚠️ Riesgo moderado — puede dañar espigas en formación"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo puede destruir la cosecha"),
                (75, 100,"danger",  "🚨 Riesgo crítico — activa el seguro agrario ahora"),
            ]
        },
    },

    "maiz": {
        "nombre": "maíz",
        "et0": {
            "umbrales": [
                (0,   3,   "ok",      "💧 ET₀ baja — el maíz no necesita riego aún"),
                (3,   5,   "warning", "💧 ET₀ moderada — programa riego en próximas 48h"),
                (5,   7,   "warning", "⚠️ ET₀ alta — el maíz exige riego diario en verano"),
                (7,   99,  "danger",  "🚨 ET₀ crítica — riego urgente, evita aborto de mazorca"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — ideal para labores de campo"),
                (3,  7,  "ok",      "☀️ UV moderado — buena fotosíntesis en maíz"),
                (7,  9,  "warning", "⚠️ UV alto — máxima actividad, evita herbicidas"),
                (9,  99, "danger",  "🔥 UV extremo — posible quemadura en hojas jóvenes"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — tormenta probable, riesgo de encamado"),
                (990,  1005, "warning", "🌧️ Presión baja — lluvia probable, suspende herbicidas"),
                (1005, 1020, "ok",      "🌤️ Presión normal — condiciones estables"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, ideal para recolección"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — crecimiento lento, el maíz necesita sol"),
                (200, 500, "ok",      "🌤️ Radiación moderada — desarrollo normal"),
                (500, 800, "ok",      "☀️ Radiación alta — fotosíntesis máxima en maíz"),
                (800, 9999,"warning", "🔆 Radiación extrema — estrés hídrico si no riega"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.15, "danger",  "🏜️ Suelo muy seco — aborto de mazorca inminente"),
                (0.15,0.30, "warning", "⚠️ Humedad insuficiente — riego urgente en fase de seda"),
                (0.30,0.65, "ok",      "✅ Humedad óptima para el maíz"),
                (0.65,1.0,  "warning", "💦 Suelo saturado — riesgo de podredumbre de raíz"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   8,  "danger",  "❄️ Suelo muy frío — no siembres, germinación imposible"),
                (8,   12, "warning", "🌡️ Suelo frío — germinación lenta, riesgo de damping-off"),
                (12,  30, "ok",      "✅ Temperatura óptima — máximo desarrollo radicular"),
                (30,  99, "warning", "🔥 Suelo muy caliente — estrés en plántulas jóvenes"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal para cultivo de verano"),
                (2,  6,  "warning", "⚠️ Temperatura baja acumulada — vigila heladas tardías"),
                (6,  10, "danger",  "❄️ Muchas horas de frío — daños posibles en plántula"),
                (10, 99, "danger",  "🚨 Frío acumulado crítico — protege el cultivo"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo significativo"),
                (20, 50, "warning", "⚠️ Granizo moderado — puede dañar hojas y tallos"),
                (50, 75, "danger",  "🧊 Riesgo alto — el granizo destroza el follaje del maíz"),
                (75, 100,"danger",  "🚨 Granizo inminente — pérdida total de cosecha probable"),
            ]
        },
    },

    "vid": {
        "nombre": "vid",
        "et0": {
            "umbrales": [
                (0,   2,   "ok",      "💧 ET₀ baja — la vid tolera bien la sequía moderada"),
                (2,   4,   "ok",      "💧 ET₀ moderada — estrés hídrico controlado, mejora calidad"),
                (4,   6,   "warning", "⚠️ ET₀ alta — riego de apoyo en envero para calidad"),
                (6,   99,  "danger",  "🚨 ET₀ muy alta — deshidratación de racimos en riesgo"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — condiciones para tratamientos fungicidas"),
                (3,  6,  "ok",      "☀️ UV moderado — maduración activa de la uva"),
                (6,  9,  "warning", "⚠️ UV alto — evita azufre, riesgo de fitotoxicidad"),
                (9,  99, "danger",  "🔥 UV extremo — no apliques cobre ni azufre hoy"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — tormenta, riesgo de botrytis"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, vigila mildiu y oídio"),
                (1005, 1020, "ok",      "🌤️ Presión normal — condiciones favorables"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, ideal para vendimia"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   150, "warning", "☁️ Radiación baja — maduración lenta, vigila botrytis"),
                (150, 400, "ok",      "🌤️ Radiación moderada — buena síntesis de azúcares"),
                (400, 700, "ok",      "☀️ Radiación alta — maduración óptima del racimo"),
                (700, 9999,"warning", "🔆 Radiación extrema — posible quemadura de uva"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.10, "warning", "🏜️ Suelo muy seco — estrés hídrico mejora taninos"),
                (0.10,0.25, "ok",      "✅ Humedad controlada — calidad enológica óptima"),
                (0.25,0.50, "ok",      "💧 Buena humedad — crecimiento vegetativo activo"),
                (0.50,1.0,  "warning", "💦 Suelo húmedo — riesgo de dilución y enfermedades"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   8,  "warning", "❄️ Suelo frío — brotación retrasada, vigila heladas"),
                (8,   15, "ok",      "🌱 Temperatura adecuada — inicio de brotación en vid"),
                (15,  25, "ok",      "✅ Temperatura óptima — máxima actividad radicular"),
                (25,  99, "warning", "🔥 Suelo caliente — riego para refrescar la zona radicular"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  3,  "warning", "⚠️ Pocas horas de frío — riesgo de brotación irregular"),
                (3,  7,  "ok",      "🌡️ Horas de frío correctas — reposo invernal en curso"),
                (7,  12, "ok",      "✅ Buena acumulación — brotación uniforme garantizada"),
                (12, 99, "ok",      "❄️ Frío suficiente — excelente reposo vegetativo"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo relevante"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar racimos en cuajado"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo destruye uva y madera joven"),
                (75, 100,"danger",  "🚨 Granizo inminente — activa red antigranizo ahora"),
            ]
        },
    },

    "tomate": {
        "nombre": "tomate",
        "et0": {
            "umbrales": [
                (0,   2,   "ok",      "💧 ET₀ baja — el tomate no necesita riego adicional"),
                (2,   4,   "ok",      "💧 ET₀ moderada — riego regular cada 2-3 días"),
                (4,   6,   "warning", "⚠️ ET₀ alta — riega diariamente para evitar blossom end rot"),
                (6,   99,  "danger",  "🚨 ET₀ crítica — riego urgente, riesgo de caída de flor"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — aplica tratamientos preventivos"),
                (3,  6,  "ok",      "☀️ UV moderado — maduración activa del fruto"),
                (6,  9,  "warning", "⚠️ UV alto — cubre plantas jóvenes, evita quemaduras"),
                (9,  99, "danger",  "🔥 UV extremo — usa malla de sombreo para proteger frutos"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — humedad alta, alerta por Botrytis"),
                (990,  1005, "warning", "🌧️ Presión baja — vigila mildiu y alternaria"),
                (1005, 1020, "ok",      "🌤️ Condiciones normales para el tomate"),
                (1020, 9999, "ok",      "☀️ Alta presión — condiciones secas, vigila araña roja"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — maduración lenta, sabor reducido"),
                (200, 500, "ok",      "🌤️ Radiación moderada — cuajado correcto"),
                (500, 750, "ok",      "☀️ Radiación alta — máxima producción de licopeno"),
                (750, 9999,"warning", "🔆 Radiación extrema — quemadura solar en frutos posible"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.15, "danger",  "🏜️ Suelo seco — podredumbre apical inminente"),
                (0.15,0.35, "warning", "⚠️ Humedad baja — riego urgente para evitar rajado"),
                (0.35,0.65, "ok",      "✅ Humedad óptima para el tomate"),
                (0.65,1.0,  "warning", "💦 Exceso de agua — riesgo de asfixia y Fusarium"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   10, "danger",  "❄️ Suelo muy frío — no trasplantes, raíces bloqueadas"),
                (10,  15, "warning", "🌡️ Suelo frío — trasplante posible pero crecimiento lento"),
                (15,  28, "ok",      "✅ Temperatura óptima — máximo desarrollo del tomate"),
                (28,  99, "warning", "🔥 Suelo caliente — mulching para proteger raíces"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal para cultivo de verano"),
                (2,  5,  "warning", "⚠️ Temperatura baja — vigila desarrollo nocturno"),
                (5,  8,  "danger",  "❄️ Frío acumulado — riesgo de daños en fruto"),
                (8,  99, "danger",  "🚨 Frío excesivo — protege con túneles o acolchado"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede marcar y dañar frutos"),
                (50, 75, "danger",  "🧊 Riesgo alto — el granizo destroza frutos y tallos"),
                (75, 100,"danger",  "🚨 Granizo crítico — instala protección urgente"),
            ]
        },
    },

    "olivo": {
        "nombre": "olivo",
        "et0": {
            "umbrales": [
                (0,   1.5, "ok",      "💧 ET₀ baja — el olivo no necesita riego"),
                (1.5, 3.5, "ok",      "💧 ET₀ moderada — riego cada 10-15 días suficiente"),
                (3.5, 5.5, "warning", "⚠️ ET₀ alta — riego de apoyo en cuajado de aceituna"),
                (5.5, 99,  "danger",  "🚨 ET₀ muy alta — riego urgente, caída de fruto posible"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — buen momento para tratamientos con cobre"),
                (3,  7,  "ok",      "☀️ UV moderado — maduración activa de la aceituna"),
                (7,  9,  "warning", "⚠️ UV alto — evita tratamientos en horas centrales"),
                (9,  99, "danger",  "🔥 UV extremo — no apliques fitosanitarios hoy"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — tormenta, vigila repilo y antracnosis"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, riesgo de repilo"),
                (1005, 1020, "ok",      "🌤️ Condiciones estables para el olivar"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, ideal para recolección"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   150, "warning", "☁️ Radiación baja — maduración lenta de la aceituna"),
                (150, 400, "ok",      "🌤️ Radiación adecuada para el olivo"),
                (400, 700, "ok",      "☀️ Radiación alta — acumulación óptima de aceite"),
                (700, 9999,"ok",      "🔆 Radiación máxima — el olivo tolera bien la insolación"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.08, "warning", "🏜️ Suelo muy seco — el olivo aguanta, pero vigila en verano"),
                (0.08,0.20, "ok",      "✅ Humedad adecuada — el olivo está en condiciones óptimas"),
                (0.20,0.45, "ok",      "💧 Buena humedad — crecimiento vegetativo correcto"),
                (0.45,1.0,  "warning", "💦 Suelo saturado — el olivo no tolera el encharcamiento"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   5,  "warning", "❄️ Suelo frío — actividad radicular mínima en olivo"),
                (5,   15, "ok",      "🌱 Temperatura adecuada — inicio de actividad primaveral"),
                (15,  28, "ok",      "✅ Temperatura óptima para el desarrollo del olivo"),
                (28,  99, "warning", "🔥 Suelo caliente — mulching orgánico recomendado"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  3,  "warning", "⚠️ Pocas horas de frío — floración puede ser irregular"),
                (3,  7,  "ok",      "🌡️ Horas de frío moderadas — inducción floral en curso"),
                (7,  12, "ok",      "✅ Buena acumulación — floración uniforme esperada"),
                (12, 99, "ok",      "❄️ Frío suficiente — excelente inducción floral"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo relevante"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar frutos en crecimiento"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo puede destruir la cosecha de aceituna"),
                (75, 100,"danger",  "🚨 Granizo inminente — pérdidas graves en olivar posibles"),
            ]
        },
    },

    "patata": {
        "nombre": "patata",
        "et0": {
            "umbrales": [
                (0,   2,   "ok",      "💧 ET₀ baja — la patata no necesita riego"),
                (2,   4,   "ok",      "💧 ET₀ moderada — riego cada 5-7 días recomendado"),
                (4,   5.5, "warning", "⚠️ ET₀ alta — riego frecuente en tuberización"),
                (5.5, 99,  "danger",  "🚨 ET₀ crítica — riego urgente para evitar costra en tubérculo"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — aplica tratamientos contra mildiu"),
                (3,  6,  "ok",      "☀️ UV moderado — desarrollo normal del cultivo"),
                (6,  9,  "warning", "⚠️ UV alto — evita fitosanitarios en horas centrales"),
                (9,  99, "danger",  "🔥 UV extremo — riesgo de quemadura en hojas"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión muy baja — alerta máxima por Phytophthora"),
                (990,  1005, "warning", "🌧️ Presión baja — condiciones perfectas para mildiu"),
                (1005, 1020, "ok",      "🌤️ Presión normal — condiciones favorables"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, menor riesgo fúngico"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — tuberización más lenta"),
                (200, 500, "ok",      "🌤️ Radiación moderada — crecimiento correcto"),
                (500, 750, "ok",      "☀️ Radiación alta — producción de almidón óptima"),
                (750, 9999,"warning", "🔆 Radiación extrema — estrés hídrico si no riega"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.15, "danger",  "🏜️ Suelo muy seco — tubérculos deformes y rajados"),
                (0.15,0.35, "warning", "⚠️ Humedad baja — riesgo de costra en patata"),
                (0.35,0.65, "ok",      "✅ Humedad óptima para tuberización"),
                (0.65,1.0,  "warning", "💦 Exceso de agua — riesgo de podredumbre en tubérculo"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   7,  "danger",  "❄️ Suelo frío — no plantes, tubérculos no brotan"),
                (7,   12, "warning", "🌡️ Suelo fresco — brotación lenta pero posible"),
                (12,  22, "ok",      "✅ Temperatura óptima — máxima tuberización"),
                (22,  99, "warning", "🔥 Suelo caliente — tuberización reducida, riega"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal en primavera/verano"),
                (2,  5,  "warning", "⚠️ Frío acumulado — vigila brotación de tubérculos"),
                (5,  8,  "danger",  "❄️ Frío excesivo — daños en hojas posibles"),
                (8,  99, "danger",  "🚨 Frío crítico — protege con acolchado plástico"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar follaje"),
                (50, 75, "danger",  "🧊 Riesgo alto — defoliación masiva posible"),
                (75, 100,"danger",  "🚨 Granizo inminente — pérdida total de follaje probable"),
            ]
        },
    },

    "alfalfa": {
        "nombre": "alfalfa",
        "et0": {
            "umbrales": [
                (0,   3,   "ok",      "💧 ET₀ baja — la alfalfa no requiere riego urgente"),
                (3,   5,   "warning", "💧 ET₀ moderada — riego regular para máxima producción"),
                (5,   7,   "warning", "⚠️ ET₀ alta — riego frecuente, la alfalfa consume mucha agua"),
                (7,   99,  "danger",  "🚨 ET₀ crítica — riego urgente, riesgo de pérdida de corte"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — buenas condiciones para siegas"),
                (3,  6,  "ok",      "☀️ UV moderado — secado correcto tras siega"),
                (6,  9,  "warning", "⚠️ UV alto — secado rápido, voltea el heno"),
                (9,  99, "warning", "🔥 UV extremo — heno puede perder calidad nutritiva"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión baja — no siegues, lluvia arruinará el heno"),
                (990,  1005, "warning", "🌧️ Presión baja — espera para segar"),
                (1005, 1020, "ok",      "🌤️ Condiciones normales para alfalfa"),
                (1020, 9999, "ok",      "☀️ Alta presión — momento ideal para segar y henificar"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — secado lento del heno"),
                (200, 500, "ok",      "🌤️ Radiación moderada — crecimiento correcto"),
                (500, 800, "ok",      "☀️ Radiación alta — máxima producción de biomasa"),
                (800, 9999,"ok",      "🔆 Radiación máxima — secado ultrarrápido tras siega"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.15, "danger",  "🏜️ Suelo muy seco — riego urgente, afecta rebrote"),
                (0.15,0.35, "warning", "⚠️ Humedad baja — riega antes del próximo corte"),
                (0.35,0.70, "ok",      "✅ Humedad óptima para la alfalfa"),
                (0.70,1.0,  "warning", "💦 Suelo saturado — riesgo de podredumbre de corona"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   5,  "warning", "❄️ Suelo frío — crecimiento paralizado en alfalfa"),
                (5,   12, "ok",      "🌱 Temperatura adecuada — rebrote tras corte posible"),
                (12,  28, "ok",      "✅ Temperatura óptima — máxima velocidad de rebrote"),
                (28,  99, "warning", "🔥 Suelo caliente — riega para refrescar el sistema radicular"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal en temporada de cortes"),
                (2,  6,  "ok",      "❄️ Horas de frío moderadas — alfalfa en reposo"),
                (6,  10, "ok",      "✅ Buen reposo invernal — rebrote vigoroso en primavera"),
                (10, 99, "ok",      "❄️ Mucho frío acumulado — excelente vernalización"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar el corte en campo"),
                (50, 75, "danger",  "🧊 Riesgo alto — no siegues si hay granizo previsto"),
                (75, 100,"danger",  "🚨 Granizo inminente — daños severos en tallos y hojas"),
            ]
        },
    },

    "girasol": {
        "nombre": "girasol",
        "et0": {
            "umbrales": [
                (0,   2,   "ok",      "💧 ET₀ baja — el girasol no necesita riego"),
                (2,   4,   "ok",      "💧 ET₀ moderada — tolerante a la sequía moderada"),
                (4,   6,   "warning", "⚠️ ET₀ alta — riego de apoyo en floración recomendado"),
                (6,   99,  "danger",  "🚨 ET₀ crítica — riego urgente para llenado de pipa"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — aplica herbicidas en buenas condiciones"),
                (3,  7,  "ok",      "☀️ UV moderado — floración activa, buen desarrollo"),
                (7,  9,  "warning", "⚠️ UV alto — evita tratamientos en horas centrales"),
                (9,  99, "danger",  "🔥 UV extremo — posible quemadura en capítulo"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión baja — riesgo de Sclerotinia con humedad"),
                (990,  1005, "warning", "🌧️ Presión baja — vigila enfermedades fúngicas"),
                (1005, 1020, "ok",      "🌤️ Condiciones estables para girasol"),
                (1020, 9999, "ok",      "☀️ Alta presión — condiciones secas, ideal para cosecha"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — el girasol necesita mucho sol"),
                (200, 500, "ok",      "🌤️ Radiación moderada — heliotropismo activo"),
                (500, 800, "ok",      "☀️ Radiación alta — máxima síntesis de aceite en pipa"),
                (800, 9999,"ok",      "🔆 Radiación máxima — el girasol aprovecha al máximo"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.10, "warning", "🏜️ Suelo seco — el girasol aguanta, vigila en floración"),
                (0.10,0.30, "ok",      "✅ Humedad adecuada para el girasol"),
                (0.30,0.60, "ok",      "💧 Buena humedad — desarrollo vegetativo correcto"),
                (0.60,1.0,  "warning", "💦 Suelo saturado — riesgo de Sclerotinia y Phoma"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   8,  "danger",  "❄️ Suelo frío — no siembres, germinación muy lenta"),
                (8,   12, "warning", "🌡️ Suelo fresco — siembra posible pero lenta"),
                (12,  28, "ok",      "✅ Temperatura óptima para el girasol"),
                (28,  99, "warning", "🔥 Suelo caliente — riego para proteger la nascencia"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal en primavera/verano"),
                (2,  5,  "warning", "⚠️ Frío acumulado — vigila plantas jóvenes"),
                (5,  8,  "danger",  "❄️ Frío excesivo — daños en plántulas posibles"),
                (8,  99, "danger",  "🚨 Frío crítico — protege con acolchado"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo significativo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar el capítulo"),
                (50, 75, "danger",  "🧊 Riesgo alto — pérdidas en llenado de pipa"),
                (75, 100,"danger",  "🚨 Granizo inminente — pérdida total de cosecha posible"),
            ]
        },
    },

    "cebada": {
        "nombre": "cebada",
        "et0": {
            "umbrales": [
                (0,   1.5, "ok",      "💧 ET₀ baja — la cebada no requiere riego"),
                (1.5, 3.5, "ok",      "💧 ET₀ moderada — humedad suficiente para cereal"),
                (3.5, 5.0, "warning", "⚠️ ET₀ alta — riego de apoyo en espigado recomendado"),
                (5.0, 99,  "danger",  "🚨 ET₀ muy alta — riego urgente, evita esterilidad en espiga"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — buenas condiciones para tratamientos"),
                (3,  6,  "ok",      "☀️ UV moderado — fotosíntesis activa"),
                (6,  9,  "warning", "⚠️ UV alto — evita fungicidas en horas centrales"),
                (9,  99, "danger",  "🔥 UV extremo — aplica antes del amanecer"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión baja — riesgo de tormenta y encamado"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, vigila roya"),
                (1005, 1020, "ok",      "🌤️ Condiciones estables para la cebada"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, ideal para cosecha"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   150, "warning", "☁️ Radiación baja — llenado de grano más lento"),
                (150, 400, "ok",      "🌤️ Radiación moderada — desarrollo correcto"),
                (400, 700, "ok",      "☀️ Radiación alta — llenado de grano óptimo"),
                (700, 9999,"warning", "🔆 Radiación muy alta — posible madurez precoz"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.12, "danger",  "🏜️ Suelo muy seco — riesgo de esterilidad en cebada"),
                (0.12,0.28, "warning", "⚠️ Humedad baja — riego si está en espigado"),
                (0.28,0.58, "ok",      "✅ Humedad óptima para la cebada"),
                (0.58,1.0,  "warning", "💦 Suelo saturado — riesgo de enfermedades de pie"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   3,  "warning", "❄️ Suelo frío — germinación paralizada"),
                (3,   10, "ok",      "🌱 Temperatura adecuada — germinación activa"),
                (10,  22, "ok",      "✅ Temperatura óptima — desarrollo radicular máximo"),
                (22,  99, "warning", "🔥 Suelo cálido — estrés posible en raíces"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "warning", "⚠️ Pocas horas de frío — vernalización insuficiente"),
                (2,  6,  "ok",      "🌡️ Horas de frío moderadas — vernalización en curso"),
                (6,  10, "ok",      "✅ Buena acumulación de frío — espigado uniforme"),
                (10, 99, "ok",      "❄️ Frío suficiente — excelente vernalización"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Riesgo mínimo de granizo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar espigas"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo puede destruir la cosecha"),
                (75, 100,"danger",  "🚨 Riesgo crítico — activa el seguro agrario"),
            ]
        },
    },

    "almendro": {
        "nombre": "almendro",
        "et0": {
            "umbrales": [
                (0,   1.5, "ok",      "💧 ET₀ baja — el almendro no necesita riego"),
                (1.5, 3.5, "ok",      "💧 ET₀ moderada — riego cada 10-12 días en verano"),
                (3.5, 5.5, "warning", "⚠️ ET₀ alta — riego de apoyo en llenado de almendra"),
                (5.5, 99,  "danger",  "🚨 ET₀ muy alta — riesgo de caída de fruto por estrés"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — aplica tratamientos fungicidas preventivos"),
                (3,  7,  "ok",      "☀️ UV moderado — floración y fructificación activa"),
                (7,  9,  "warning", "⚠️ UV alto — evita azufre, riesgo de fitotoxicidad"),
                (9,  99, "danger",  "🔥 UV extremo — no apliques ningún fitosanitario"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión baja — tormenta probable, vigila monilia"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, riesgo de monilia"),
                (1005, 1020, "ok",      "🌤️ Condiciones estables para el almendro"),
                (1020, 9999, "ok",      "☀️ Alta presión — condiciones secas óptimas"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   150, "warning", "☁️ Radiación baja — maduración lenta de la almendra"),
                (150, 400, "ok",      "🌤️ Radiación moderada — cuajado correcto"),
                (400, 700, "ok",      "☀️ Radiación alta — llenado óptimo del fruto"),
                (700, 9999,"ok",      "🔆 Radiación máxima — el almendro tolera alta insolación"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.08, "warning", "🏜️ Suelo muy seco — el almendro aguanta, pero en fructificación riega"),
                (0.08,0.22, "ok",      "✅ Humedad adecuada — condiciones óptimas"),
                (0.22,0.45, "ok",      "💧 Buena humedad — crecimiento vegetativo correcto"),
                (0.45,1.0,  "warning", "💦 Suelo saturado — el almendro no tolera encharcamiento"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   5,  "warning", "❄️ Suelo frío — raíces poco activas"),
                (5,   14, "ok",      "🌱 Temperatura adecuada — inicio de actividad primaveral"),
                (14,  28, "ok",      "✅ Temperatura óptima para el almendro"),
                (28,  99, "warning", "🔥 Suelo caliente — mulching para conservar humedad"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  3,  "warning", "⚠️ Pocas horas de frío — riesgo de floración irregular"),
                (3,  7,  "ok",      "🌡️ Horas de frío moderadas — reposo invernal correcto"),
                (7,  12, "ok",      "✅ Buena acumulación — floración uniforme esperada"),
                (12, 99, "ok",      "❄️ Frío suficiente — excelente reposo vegetativo"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo relevante"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar flores y frutos jóvenes"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo destruye la cosecha de almendra"),
                (75, 100,"danger",  "🚨 Granizo inminente — activa red antigranizo urgente"),
            ]
        },
    },

    "arroz": {
        "nombre": "arroz",
        "et0": {
            "umbrales": [
                (0,   3,   "ok",      "💧 ET₀ baja — lámina de agua suficiente"),
                (3,   5,   "ok",      "💧 ET₀ moderada — mantén la lámina constante"),
                (5,   7,   "warning", "⚠️ ET₀ alta — recarga el caudal de riego"),
                (7,   99,  "danger",  "🚨 ET₀ crítica — riesgo de desecación de la parcela"),
            ]
        },
        "uv": {
            "umbrales": [
                (0,  3,  "ok",      "☀️ UV bajo — aplica herbicidas en buenas condiciones"),
                (3,  6,  "ok",      "☀️ UV moderado — espigado activo del arroz"),
                (6,  9,  "warning", "⚠️ UV alto — evita tratamientos en horas centrales"),
                (9,  99, "danger",  "🔥 UV extremo — riesgo de quemadura en hoja bandera"),
            ]
        },
        "pressure": {
            "umbrales": [
                (0,    990,  "danger",  "⛈️ Presión baja — tormenta, riesgo de pyricularia"),
                (990,  1005, "warning", "🌧️ Presión baja — humedad alta, vigila enfermedades"),
                (1005, 1020, "ok",      "🌤️ Condiciones estables para el arroz"),
                (1020, 9999, "ok",      "☀️ Alta presión — tiempo seco, bueno para cosecha"),
            ]
        },
        "radiation": {
            "umbrales": [
                (0,   200, "warning", "☁️ Radiación baja — llenado de grano más lento"),
                (200, 500, "ok",      "🌤️ Radiación moderada — desarrollo correcto"),
                (500, 800, "ok",      "☀️ Radiación alta — máxima producción de arroz"),
                (800, 9999,"ok",      "🔆 Radiación máxima — excelente llenado de grano"),
            ]
        },
        "soil_moisture": {
            "umbrales": [
                (0,   0.50, "danger",  "🏜️ Suelo seco — el arroz necesita inundación"),
                (0.50,0.75, "warning", "⚠️ Humedad insuficiente — repone la lámina de agua"),
                (0.75,1.0,  "ok",      "✅ Suelo saturado — condición óptima para el arroz"),
                (1.0, 9999, "ok",      "💧 Inundación — condición ideal del cultivo"),
            ]
        },
        "soil_temp": {
            "umbrales": [
                (0,   13, "danger",  "❄️ Suelo muy frío — no trasplantes, daño irreversible"),
                (13,  18, "warning", "🌡️ Suelo fresco — trasplante posible pero lento"),
                (18,  32, "ok",      "✅ Temperatura óptima — máximo desarrollo del arroz"),
                (32,  99, "warning", "🔥 Suelo muy caliente — esterilidad polínica posible"),
            ]
        },
        "cold_hours": {
            "umbrales": [
                (0,  2,  "ok",      "🌡️ Pocas horas frías — normal para cultivo de verano"),
                (2,  4,  "warning", "⚠️ Frío acumulado — vigila la nascencia"),
                (4,  8,  "danger",  "❄️ Frío excesivo — daños en plántulas posibles"),
                (8,  99, "danger",  "🚨 Frío crítico — protege urgente"),
            ]
        },
        "hail": {
            "umbrales": [
                (0,  20, "ok",      "✅ Sin riesgo de granizo significativo"),
                (20, 50, "warning", "⚠️ Granizo posible — puede dañar panícula en floración"),
                (50, 75, "danger",  "🧊 Riesgo alto — granizo puede destruir la cosecha"),
                (75, 100,"danger",  "🚨 Granizo inminente — pérdidas severas en arroz"),
            ]
        },
    },
}

# Perfil genérico para cultivos no definidos
GENERIC_PROFILE = {
    "nombre": "cultivo",
    "et0": {
        "umbrales": [
            (0,   2,   "ok",      "💧 ET₀ baja — demanda hídrica mínima"),
            (2,   4,   "ok",      "💧 ET₀ moderada — demanda hídrica normal"),
            (4,   6,   "warning", "⚠️ ET₀ alta — considera riego de apoyo"),
            (6,   99,  "danger",  "🚨 ET₀ muy alta — riego urgente recomendado"),
        ]
    },
    "uv": {
        "umbrales": [
            (0,  3,  "ok",      "☀️ UV bajo — condiciones aptas para trabajos"),
            (3,  6,  "ok",      "☀️ UV moderado — fotosíntesis activa"),
            (6,  9,  "warning", "⚠️ UV alto — evita tratamientos en horas centrales"),
            (9,  99, "danger",  "🔥 UV extremo — aplica solo en horas frescas"),
        ]
    },
    "pressure": {
        "umbrales": [
            (0,    990,  "danger",  "⛈️ Presión muy baja — frente activo, tormenta probable"),
            (990,  1005, "warning", "🌧️ Presión baja — posible inestabilidad meteorológica"),
            (1005, 1020, "ok",      "🌤️ Presión normal — condiciones estables"),
            (1020, 9999, "ok",      "☀️ Presión alta — tiempo estable y seco"),
        ]
    },
    "radiation": {
        "umbrales": [
            (0,   150, "warning", "☁️ Radiación baja — fotosíntesis limitada"),
            (150, 400, "ok",      "🌤️ Radiación moderada — desarrollo normal"),
            (400, 700, "ok",      "☀️ Radiación alta — fotosíntesis máxima"),
            (700, 9999,"warning", "🔆 Radiación extrema — posible estrés térmico"),
        ]
    },
    "soil_moisture": {
        "umbrales": [
            (0,   0.15, "danger",  "🏜️ Suelo muy seco — riego urgente necesario"),
            (0.15,0.35, "warning", "⚠️ Humedad baja — monitoriza y riega pronto"),
            (0.35,0.65, "ok",      "✅ Humedad del suelo óptima"),
            (0.65,1.0,  "warning", "💦 Suelo saturado — riesgo de asfixia radicular"),
        ]
    },
    "soil_temp": {
        "umbrales": [
            (0,   5,  "warning", "❄️ Suelo frío — actividad biológica baja"),
            (5,   15, "ok",      "🌱 Temperatura adecuada para germinación"),
            (15,  28, "ok",      "✅ Temperatura óptima para actividad microbiana"),
            (28,  99, "warning", "🔥 Suelo muy caliente — estrés térmico posible"),
        ]
    },
    "cold_hours": {
        "umbrales": [
            (0,  2,  "warning", "⚠️ Pocas horas de frío — vernalización insuficiente"),
            (2,  6,  "ok",      "🌡️ Horas de frío moderadas"),
            (6,  10, "ok",      "✅ Buena acumulación de frío invernal"),
            (10, 99, "ok",      "❄️ Muchas horas de frío acumuladas"),
        ]
    },
    "hail": {
        "umbrales": [
            (0,  20, "ok",      "✅ Riesgo mínimo de granizo"),
            (20, 50, "warning", "⚠️ Riesgo moderado de granizo"),
            (50, 75, "danger",  "🧊 Riesgo alto de granizo — protege el cultivo"),
            (75, 100,"danger",  "🚨 Riesgo crítico de granizo"),
        ]
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DEL AGENTE
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate(value, umbrales):
    """Busca el umbral que corresponde al valor y devuelve (level, text)."""
    if value is None:
        return "info", "— Dato no disponible"
    for low, high, level, text in umbrales:
        if low <= value < high:
            return level, text
    # Fallback al último
    return umbrales[-1][1], umbrales[-1][2]


def get_card_insights(data: dict, crop_type: str) -> dict:
    """
    Genera los 8 textos interpretativos específicos para el cultivo dado.

    Args:
        data: dict con los datos agronómicos del endpoint /get-agronomic-data
        crop_type: nombre del cultivo (trigo, maiz, vid, etc.)

    Returns:
        dict con claves: et0, uv, pressure, radiation, soil, soiltemp, coldhours, hail
    """
    crop_key = (crop_type or "").lower().strip()
    # Normalización de aliases
    aliases = {
        "maíz": "maiz", "vid": "vid", "uva": "vid", "viña": "vid",
        "almendra": "almendro", "oliva": "olivo", "alfalfa": "alfalfa",
        "brocoli": "generico", "brocóli": "generico", "peral": "generico",
        "pera": "generico", "manzano": "generico", "manzana": "generico",
    }
    crop_key = aliases.get(crop_key, crop_key)
    profile = CROP_PROFILES.get(crop_key, GENERIC_PROFILE)

    # Extraer valores del payload
    et0      = data.get("et0_today")
    uv       = data.get("uv_index") or data.get("uv_max_today")
    pressure = data.get("pressure")
    radiation= data.get("solar_radiation")
    soil_m   = data.get("soil_moisture_0")
    soil_t   = data.get("soil_temp_surface")
    cold_h   = data.get("cold_hours_24h")
    hail_r   = data.get("hail_risk_6h", 0)

    # Humedad suelo de 0-1 a porcentaje
    if soil_m is not None and soil_m <= 1.0:
        soil_m_pct = soil_m  # ya la evaluamos en escala 0-1

    _, et0_text      = _evaluate(et0,      profile["et0"]["umbrales"])
    _, uv_text       = _evaluate(uv,       profile["uv"]["umbrales"])
    _, press_text    = _evaluate(pressure, profile["pressure"]["umbrales"])
    _, rad_text      = _evaluate(radiation,profile["radiation"]["umbrales"])
    _, soil_text     = _evaluate(soil_m,   profile["soil_moisture"]["umbrales"])
    _, stemp_text    = _evaluate(soil_t,   profile["soil_temp"]["umbrales"])
    _, cold_text     = _evaluate(cold_h,   profile["cold_hours"]["umbrales"])
    _, hail_text     = _evaluate(hail_r,   profile["hail"]["umbrales"])

    return {
        "et0":       et0_text,
        "uv":        uv_text,
        "pressure":  press_text,
        "radiation": rad_text,
        "soil":      soil_text,
        "soiltemp":  stemp_text,
        "coldhours": cold_text,
        "hail":      hail_text,
    }