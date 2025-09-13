#!/usr/bin/env python3
"""
Backend serverless – Cotizador solar rápido
Adaptado para Colombia (COP)
"""
import os
import json
import math
import requests
import datetime as dt
from pvlib import irradiance, location

# ---------- PARÁMETROS COLOMBIA ----------
CUR       = "COP"          # moneda local
PRICE_KWH = 890            # COP/kWh promedio residencial (CREG 2024)
USD_COP   = 4_000          # tasa de cambio hoy (ajustar si fluctúa)
USD_W     = 0.9            # USD/W instalado (referencia)
LOSS      = 0.8            # pérdidas totales DC/AC
TARGET    = 0.7            # 70 % de ahorro deseado
# -----------------------------------------

LAT   = float(os.getenv("INPUT_LAT"))
LON   = float(os.getenv("INPUT_LON"))
BILL  = float(os.getenv("INPUT_BILL"))

# 1) kWh mensuales que paga el usuario
kwh_month = BILL / PRICE_KWH
kwh_70    = kwh_month * TARGET

# 2) Producción específica anual (kWh/kWp) con PVWatts
try:
    resp = requests.get(
        "https://developer.nrel.gov/api/pvwatts/v8.json",
        params={
            "api_key": "DEMO_KEY",  # pide tu propia key en 30 s
            "lat": LAT,
            "lon": LON,
            "system_capacity": 1,
            "azimuth": 180,
            "tilt": abs(LAT),
            "array_type": 1,
            "module_type": 0,
            "losses": 14,
            "timeframe": "monthly"
        },
        timeout=10
    ).json()
    specific = sum(resp["outputs"]["ac_monthly"]) / 1.0  # kWh/kWp/año
except Exception:
    # Fallback Open-Meteo
    meteo = requests.get(
        f"https://archive-api.open-meteo.com/v1/era5?"
        f"latitude={LAT}&longitude={LON}&start_date=2022-01-01&end_date=2022-12-31"
        f"&daily=shortwave_radiation_sum&timezone=auto"
    ).json()
    ghi_day = sum(meteo["daily"]["shortwave_radiation_sum"]) / 365  # Wh/m²/day
    specific = ghi_day * 0.365 * LOSS * 0.2  # 0.2 rendimiento panel

# 3) kWp necesarios
kwp = (kwh_70 * 12) / specific
panels = math.ceil(kwp / 0.45)  # 450 Wp por panel
kwp_real = panels * 0.45

# 4) Precio
price_usd   = kwp_real * 1000 * USD_W
price_cop   = price_usd * USD_COP

# 5) Payback simple
ahorro_anual_usd = (BILL * 12 * TARGET) / USD_COP
payback = price_usd / ahorro_anual_usd if ahorro_anual_usd else 99

# 6) Salida
result = {
    "kwh_month_total": round(kwh_month, 0),
    "kwh_month_target": round(kwh_70, 0),
    "kwp": round(kwp_real, 2),
    "panels": panels,
    "price_usd": round(price_usd, 0),
    "price_cop": round(price_cop, 0),
    "currency": CUR,
    "payback_years": round(payback, 1)
}

with open("quote.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False)

# (Opcional) crear Issue con la cotización
import github
g = github.Github(os.getenv("GITHUB_TOKEN"))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
repo.create_issue(
    title=f"Cotización solar {LAT},{LON}",
    body=f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
)