"""Reglas de validación con severidad explícita.

Severidades:

* ``error``   - el dato es inconsistente y las métricas que lo usan no son confiables.
* ``warning`` - el dato es posible pero cae fuera de rangos típicos; revisar con la fuente.
* ``info``    - patrón relevante para interpretar los datos (p. ej. valores estimados).

Reglas (identificador -> descripción):

* ``R1_negative``        Valores negativos en km, volumen, costo o vehículos (error).
* ``R2_incomplete``      Hay km sin volumen, volumen sin km o costo sin volumen (error).
* ``R3_efficiency``      Rendimiento (km/L o km/kWh) fuera del rango plausible del combustible (warning).
* ``R4_unit_cost``       Costo por litro/kWh fuera del rango plausible (warning).
* ``R5_km_per_vehicle``  km por vehículo al mes fuera de [100, 25 000] (warning).
* ``R6_constant_ratio``  Rendimiento o precio idéntico en todos los meses: sugiere valores
                         derivados con un factor fijo en lugar de medidos (info).
* ``R7_fleet_quantity``  Columna general ``Quantity`` vacía aunque el combustible reporta vehículos (info).
* ``R8_reconciliation``  Suma de los meses no coincide con la fila ``Total`` del archivo (warning).
* ``R9_coverage``        Segmento sin datos en todo el año o con meses faltantes (info).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from fleet_analytics.cleaning import split_totals, to_long, totals_to_long
from fleet_analytics.metrics import safe_div

#: Rangos plausibles de rendimiento (km por unidad reportada) para flotillas comerciales.
#: Amplios a propósito: cubren desde tractocamiones cargados (~1.5-3 km/L diésel) hasta
#: vehículos ligeros (~10-20 km/L gasolina). Eléctrico: de camiones (~0.5 km/kWh) a autos (~8).
EFFICIENCY_RANGES: dict[str, tuple[float, float]] = {
    "gasoline": (3.0, 25.0),
    "diesel": (1.5, 20.0),
    "ethanol": (2.0, 20.0),
    "lpg": (2.0, 15.0),
    "cng": (0.5, 15.0),
    "electric": (0.3, 10.0),
}

#: Rangos plausibles de costo unitario en USD (por L o por kWh) para Norteamérica 2020-2024.
UNIT_COST_RANGES: dict[str, tuple[float, float]] = {
    "gasoline": (0.5, 3.0),
    "diesel": (0.5, 3.0),
    "ethanol": (0.4, 3.0),
    "lpg": (0.2, 2.5),
    "cng": (0.1, 2.5),
    "electric": (0.03, 0.8),
}

KM_PER_VEHICLE_RANGE = (100.0, 25_000.0)
RECONCILIATION_TOLERANCE = 1e-4  # diferencia relativa tolerada (0.01 %)


@dataclass(frozen=True)
class Issue:
    severity: str
    rule: str
    segment: str
    month: str
    message: str


def _segment(row) -> str:
    return f"{row['ownership']} | {row['vehicle_type']} | {row['fuel']}"


def _row_rules(long: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    for _, r in long.iterrows():
        seg, month = _segment(r), str(r["month_name"])
        vals = {k: r[k] for k in ("km", "volume", "cost_usd", "vehicles")}
        neg = [k for k, v in vals.items() if pd.notna(v) and v < 0]
        if neg:
            issues.append(Issue("error", "R1_negative", seg, month, f"Valores negativos en {neg}"))
        km, vol, cost = (vals["km"] or 0), (vals["volume"] or 0), (vals["cost_usd"] or 0)
        km, vol, cost = (0 if pd.isna(x) else x for x in (km, vol, cost))
        if (km > 0) != (vol > 0) or (cost > 0 and vol <= 0):
            issues.append(
                Issue(
                    "error",
                    "R2_incomplete",
                    seg,
                    month,
                    f"Registro incompleto: km={km:,.0f}, volumen={vol:,.0f}, USD={cost:,.0f}",
                )
            )
            continue
        if km > 0 and vol > 0:
            eff = km / vol
            lo, hi = EFFICIENCY_RANGES[r["fuel"]]
            if not lo <= eff <= hi:
                issues.append(
                    Issue(
                        "warning",
                        "R3_efficiency",
                        seg,
                        month,
                        f"Rendimiento {eff:.2f} km/{r['unit']} fuera de [{lo}, {hi}]",
                    )
                )
        if cost > 0 and vol > 0:
            unit_cost = cost / vol
            lo, hi = UNIT_COST_RANGES[r["fuel"]]
            if not lo <= unit_cost <= hi:
                issues.append(
                    Issue(
                        "warning",
                        "R4_unit_cost",
                        seg,
                        month,
                        f"Costo {unit_cost:.3f} USD/{r['unit']} fuera de [{lo}, {hi}]",
                    )
                )
        veh = vals["vehicles"]
        if km > 0 and pd.notna(veh) and veh > 0:
            kpv = km / veh
            lo, hi = KM_PER_VEHICLE_RANGE
            if not lo <= kpv <= hi:
                issues.append(
                    Issue(
                        "warning",
                        "R5_km_per_vehicle",
                        seg,
                        month,
                        f"{kpv:,.0f} km/vehículo/mes fuera de [{lo:,.0f}, {hi:,.0f}]",
                    )
                )
        if pd.notna(veh) and veh > 0 and pd.isna(r["fleet_quantity"]):
            issues.append(
                Issue(
                    "info",
                    "R7_fleet_quantity",
                    seg,
                    month,
                    f"Quantity general vacío; el combustible reporta {veh:,.0f} vehículos",
                )
            )
    return issues


def _constant_ratio_rules(long: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    for keys, g in long.groupby(["ownership", "vehicle_type", "fuel"]):
        if len(g) < 3:
            continue
        seg = " | ".join(keys)
        for label, ratio, unit in (
            ("Rendimiento", safe_div(g["km"], g["volume"]), "km/" + g["unit"].iloc[0]),
            ("Costo unitario", safe_div(g["cost_usd"], g["volume"]), "USD/" + g["unit"].iloc[0]),
        ):
            ratio = ratio.dropna()
            if len(ratio) >= 3 and ratio.round(4).nunique() == 1:
                issues.append(
                    Issue(
                        "info",
                        "R6_constant_ratio",
                        seg,
                        "todos",
                        f"{label} idéntico en {len(ratio)} meses ({ratio.iloc[0]:.4f} {unit}): "
                        "probablemente derivado con un factor fijo, no medido",
                    )
                )
    return issues


def _reconciliation_rules(raw: pd.DataFrame, long: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    totals = totals_to_long(raw)
    if totals.empty:
        return issues
    sums = long.groupby(["ownership", "vehicle_type", "fuel"])[["km", "volume", "cost_usd"]].sum()
    for _, t in totals.iterrows():
        key = (t["ownership"], t["vehicle_type"], t["fuel"])
        for col in ("km", "volume", "cost_usd"):
            expected = 0.0 if pd.isna(t[col]) else float(t[col])
            actual = float(sums.loc[key, col]) if key in sums.index else 0.0
            diff = actual - expected
            if abs(diff) > max(RECONCILIATION_TOLERANCE * abs(expected), 0.01):
                issues.append(
                    Issue(
                        "warning",
                        "R8_reconciliation",
                        " | ".join(key),
                        "Total",
                        f"{col}: suma mensual {actual:,.2f} vs Total {expected:,.2f} (diferencia {diff:+,.2f})",
                    )
                )
    return issues


def _coverage_rules(raw: pd.DataFrame, long: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    monthly, _ = split_totals(raw)
    all_segments = monthly[["Ownership", "Type"]].drop_duplicates()
    months_in_file = sorted(monthly["Month"].str.title().unique(), key=lambda m: pd.Timestamp(f"1 {m} 2000"))
    for _, s in all_segments.iterrows():
        g = long[(long["ownership"] == s["Ownership"]) & (long["vehicle_type"] == s["Type"])]
        seg = f"{s['Ownership']} | {s['Type']}"
        if g.empty:
            issues.append(Issue("info", "R9_coverage", seg, "todos", "Segmento sin ningún dato en el año"))
            continue
        missing = [m for m in months_in_file if m not in set(g["month_name"])]
        if missing:
            issues.append(
                Issue(
                    "info",
                    "R9_coverage",
                    seg,
                    ", ".join(missing),
                    f"Sin datos en {len(missing)} de {len(months_in_file)} meses",
                )
            )
    return issues


def validate(raw: pd.DataFrame, long: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ejecuta todas las reglas y devuelve un DataFrame de hallazgos ordenado por severidad."""
    long = to_long(raw) if long is None else long
    issues = (
        _row_rules(long) + _constant_ratio_rules(long) + _reconciliation_rules(raw, long) + _coverage_rules(raw, long)
    )
    df = pd.DataFrame([asdict(i) for i in issues], columns=["severity", "rule", "segment", "month", "message"])
    order = {"error": 0, "warning": 1, "info": 2}
    return df.sort_values(["severity", "rule"], key=lambda s: s.map(order) if s.name == "severity" else s).reset_index(
        drop=True
    )
