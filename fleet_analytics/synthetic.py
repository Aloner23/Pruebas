"""Generador de datos SINTÉTICOS con el mismo formato que el template real.

Sirve para demostrar el comportamiento del reporte con un año completo y varios
combustibles. Los números NO representan ninguna flotilla real: cada fila generada se
etiqueta con ``source="synthetic"`` al pasar por :func:`fleet_analytics.cleaning.to_long`
y el reporte muestra un aviso visible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fleet_analytics.cleaning import FUEL_PREFIXES, ID_COLUMNS, MONTHS

# (ownership, tipo) -> lista de (combustible, vehículos, km/vehículo/mes, rendimiento, precio USD/unidad)
PROFILES: dict[tuple[str, str], list[tuple[str, int, float, float, float]]] = {
    ("owned, leased or renting", "tractor"): [("diesel", 120, 9000, 2.6, 1.30)],
    ("owned, leased or renting", "route trucks"): [
        ("diesel", 400, 2600, 4.2, 1.30),
        ("cng", 60, 2400, 3.4, 0.75),
        ("electric", 25, 1800, 1.1, 0.12),
    ],
    ("owned, leased or renting", "supervision"): [
        ("gasoline", 150, 2200, 10.5, 1.15),
        ("electric", 20, 2000, 6.0, 0.12),
    ],
    ("owned, leased or renting", "executives"): [("gasoline", 40, 1800, 9.0, 1.15)],
    ("owned, leased or renting", "others"): [("lpg", 30, 1500, 6.5, 0.70)],
    ("Independent Operators", "route trucks"): [("diesel", 1100, 2000, 4.0, 1.32)],
    ("Logistic Operators (3PL)", "tractor"): [("diesel", 860, 3200, 2.25, 1.30)],
}

FUEL_TO_PREFIX = {v: k for k, v in FUEL_PREFIXES.items()}


def generate(year: int = 2023, country: str = "Canada", seed: int = 42) -> pd.DataFrame:
    """Devuelve un DataFrame ANCHO (mismo esquema que el CSV real, sin filas Total)."""
    rng = np.random.default_rng(seed)
    month_names = [m.title() for m in MONTHS]
    columns = list(ID_COLUMNS)
    for prefix in FUEL_PREFIXES:
        vol = "kWh" if prefix == "Electric" else "lt"
        columns += [f"{prefix}_km", f"{prefix}_{vol}", f"{prefix}_$ (US Dlls)", f"{prefix}_Quantity"]

    rows = []
    for m_idx, month in enumerate(month_names, start=1):
        # Estacionalidad suave: más actividad en primavera-otoño, rendimiento peor en invierno.
        activity = 1 + 0.08 * np.sin((m_idx - 3) / 12 * 2 * np.pi)
        winter_penalty = 0.92 if m_idx in (1, 2, 12) else 1.0
        price_drift = 1 + 0.01 * (m_idx - 6)
        for (ownership, vtype), fuels in PROFILES.items():
            row = dict.fromkeys(columns, "")
            row.update(Month=month, Year=str(year), Country=country, Ownership=ownership, Type=vtype)
            fleet = 0
            for fuel, n, km_per_veh, eff, price in fuels:
                prefix = FUEL_TO_PREFIX[fuel]
                vol_col = f"{prefix}_kWh" if fuel == "electric" else f"{prefix}_lt"
                km = n * km_per_veh * activity * rng.normal(1, 0.05)
                e = eff * winter_penalty * rng.normal(1, 0.03)
                if fuel == "electric":
                    e *= 0.85 if winter_penalty < 1 else 1.0  # baterías rinden menos con frío
                volume = km / e
                cost = volume * price * (1 if fuel == "electric" else price_drift) * rng.normal(1, 0.02)
                row[f"{prefix}_km"] = f"{km:.0f}"
                row[vol_col] = f"{volume:.2f}"
                row[f"{prefix}_$ (US Dlls)"] = f"${cost:,.2f}"
                row[f"{prefix}_Quantity"] = str(n)
                fleet += n
            row["Quantity"] = str(fleet)
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
