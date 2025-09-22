#!/usr/bin/env python3
"""
Server-less solar quick-quote
Adapted for Colombia (COP)
"""
import os, json, math, requests, datetime as dt
from pvlib import irradiance, location

# ---------- Colombia constants ----------
CUR       = "COP"
PRICE_KWH = 890            # COP / kWh (CREG 2024)
USD_COP   = 4_000          # today´s rate
USD_W     = 0.9            # USD / Wp installed
LOSS      = 0.8            # DC/AC losses
TARGET    = 0.7            # 70 % bill reduction

# ---------- Inputs ----------
LAT   = float(os.getenv("INPUT_LAT"))
LON   = float(os.getenv("INPUT_LON"))
BILL  = float(os.getenv("INPUT_BILL"))

# 1) Monthly kWh from bill
kwh_month = BILL / PRICE_KWH
kwh_70    = kwh_month * TARGET

# 2) Specific yield (kWh/kWp/year) via PVWatts
try:
    resp = requests.get(
        "https://developer.nrel.gov/api/pvwatts/v8.json",
        params={
            "api_key": "DEMO_KEY",   # get yours in 30 s
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
    specific = sum(resp["outputs"]["ac_monthly"]) / 1.0   # kWh/kWp/year
except Exception:
    # fallback Bogotá
    specific = 1350

# 3) kWp required
kwp = (kwh_70 * 12) / specific
panels = math.ceil(kwp / 0.45)          # 450 Wp panels
kwp_real = panels * 0.45

# 4) Price
price_usd = kwp_real * 1000 * USD_W
price_cop = price_usd * USD_COP

# 5) Simple pay-back
ahorro_anual_cop = (BILL * 12 * TARGET)
payback = price_cop / ahorro_anual_cop if ahorro_anual_cop else 99

# 6) Output
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

# Optional: create GitHub issue (kept for compatibility)
import github
g = github.Github(os.getenv("GITHUB_TOKEN"))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
repo.create_issue(
    title=f"Cotización solar {LAT},{LON}",
    body=f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
)
