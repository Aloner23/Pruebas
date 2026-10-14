"""Regenera las PNG de docs/ usadas en el README. Uso: python scripts/make_readme_charts.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_analytics import charts, load_raw, synthetic, to_long
from fleet_analytics.metrics import monthly_trend, segment_summary

long = to_long(load_raw("data/raw/canada_2023_flotilla.csv"))
t = monthly_trend(long, by=["ownership", "vehicle_type"])
charts.to_png(
    charts.monthly_by_segment(t, "km", "Datos reales: km mensuales por segmento (Canadá 2023, diésel)", "km"),
    "docs/real_km_mensual.png",
)
s = to_long(synthetic.generate(), source="synthetic")
charts.to_png(
    charts.segment_bars(
        segment_summary(s),
        "co2e_g_per_km",
        "DATOS SINTÉTICOS: intensidad de emisiones (g CO2e/km)",
        "g CO2e/km",
        "{:,.0f}",
    ),
    "docs/sintetico_co2e_por_km.png",
)
