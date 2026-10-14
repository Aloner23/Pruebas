"""Métricas sobre el formato largo producido por :func:`fleet_analytics.cleaning.to_long`.

Definiciones (todas con división segura: NaN si el denominador es 0 o falta):

* ``efficiency``      = km / volumen          (km/L para combustibles líquidos, km/kWh eléctrico)
* ``l_per_100km``     = 100 * volumen / km    (sólo combustibles en litros)
* ``cost_per_km``     = USD / km
* ``cost_per_unit``   = USD / volumen          (USD/L o USD/kWh)
* ``km_per_vehicle``  = km / vehículos
* ``co2e_kg``         = volumen * factor de emisión (ver :mod:`fleet_analytics.emissions`)
* ``co2e_g_per_km``   = 1000 * co2e_kg / km
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fleet_analytics.emissions import EMISSION_FACTORS_KG_PER_UNIT

SUM_COLUMNS = ["km", "volume", "cost_usd", "co2e_kg"]


def safe_div(numerator, denominator):
    """División elemento a elemento que devuelve NaN cuando el denominador es 0 o NaN."""
    num = pd.to_numeric(pd.Series(numerator), errors="coerce").astype(float)
    den = pd.to_numeric(pd.Series(denominator), errors="coerce").astype(float)
    den = den.where(den != 0)
    out = num.to_numpy() / den.to_numpy()
    if np.ndim(numerator) == 0 and np.ndim(denominator) == 0:
        return float(out[0])
    index = numerator.index if isinstance(numerator, pd.Series) else None
    return pd.Series(out, index=index)


def add_co2e(long: pd.DataFrame, factors: dict[str, float] | None = None) -> pd.DataFrame:
    """Agrega ``co2e_kg`` = volumen x factor del combustible."""
    factors = factors or EMISSION_FACTORS_KG_PER_UNIT
    out = long.copy()
    unknown = set(out["fuel"]) - set(factors)
    if unknown:
        raise KeyError(f"Sin factor de emisión para: {sorted(unknown)}")
    out["co2e_kg"] = out["volume"] * out["fuel"].map(factors)
    return out


def _ratios(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["efficiency"] = safe_div(out["km"], out["volume"]).to_numpy()
    liquid = out["unit"].eq("L") if "unit" in out else True
    out["l_per_100km"] = np.where(liquid, 100 * safe_div(out["volume"], out["km"]), np.nan)
    out["cost_per_km"] = safe_div(out["cost_usd"], out["km"]).to_numpy()
    out["cost_per_unit"] = safe_div(out["cost_usd"], out["volume"]).to_numpy()
    if "vehicles" in out:
        out["km_per_vehicle"] = safe_div(out["km"], out["vehicles"]).to_numpy()
    if "co2e_kg" in out:
        out["co2e_g_per_km"] = (1000 * safe_div(out["co2e_kg"], out["km"])).to_numpy()
    return out


def with_unit_metrics(long: pd.DataFrame) -> pd.DataFrame:
    """Métricas fila a fila (segmento-mes-combustible)."""
    df = long if "co2e_kg" in long else add_co2e(long)
    return _ratios(df)


def _aggregate(long: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Suma magnitudes y recalcula razones sobre los totales (no promedia razones)."""
    df = long if "co2e_kg" in long else add_co2e(long)
    agg = {c: "sum" for c in SUM_COLUMNS}
    agg["vehicles"] = "max"  # vehículos es un inventario, no un flujo: no se suma entre meses
    grouped = df.groupby(by, dropna=False).agg(agg).reset_index()
    if "unit" not in by:
        units = df.groupby(by, dropna=False)["unit"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else "mixto")
        grouped["unit"] = units.to_numpy()
    grouped["months_reported"] = (
        df.groupby(by, dropna=False)[["year", "month"]].apply(lambda g: len(g.drop_duplicates())).to_numpy()
    )
    return _ratios(grouped)


def segment_summary(long: pd.DataFrame) -> pd.DataFrame:
    """Totales y razones por propiedad x tipo de vehículo x combustible."""
    return _aggregate(long, ["source", "ownership", "vehicle_type", "fuel", "unit"])


def monthly_trend(long: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Serie mensual; por defecto por segmento y combustible."""
    by = by if by is not None else ["ownership", "vehicle_type", "fuel"]
    return _aggregate(long, ["source", "year", "month", *by]).sort_values(["year", "month", *by])


def fuel_share(long: pd.DataFrame, value: str = "cost_usd") -> pd.DataFrame:
    """Participación (0-1) de cada combustible en ``value`` (cost_usd, km o co2e_kg).

    No se ofrece participación por volumen porque litros y kWh no son sumables.
    """
    if value not in {"cost_usd", "km", "co2e_kg"}:
        raise ValueError("value debe ser cost_usd, km o co2e_kg (litros y kWh no son sumables)")
    df = long if "co2e_kg" in long else add_co2e(long)
    totals = df.groupby(["source", "fuel"])[value].sum().reset_index()
    grand = totals.groupby("source")[value].transform("sum")
    totals["share"] = safe_div(totals[value], grand).to_numpy()
    return totals.sort_values(["source", "share"], ascending=[True, False]).reset_index(drop=True)


def co2e_by_fuel(long: pd.DataFrame) -> pd.DataFrame:
    """CO2e estimado (toneladas) por combustible."""
    df = long if "co2e_kg" in long else add_co2e(long)
    out = df.groupby(["source", "fuel", "unit"])[["volume", "co2e_kg"]].sum().reset_index()
    out["co2e_t"] = out["co2e_kg"] / 1000
    out["factor_kg_per_unit"] = out["fuel"].map(EMISSION_FACTORS_KG_PER_UNIT)
    return out


def headline(long: pd.DataFrame) -> dict[str, float]:
    """KPIs globales. Sólo suma litros entre combustibles líquidos (kWh aparte)."""
    df = long if "co2e_kg" in long else add_co2e(long)
    liquid = df[df["unit"] == "L"]
    return {
        "km": float(df["km"].sum()),
        "liters": float(liquid["volume"].sum()),
        "kwh": float(df.loc[df["unit"] == "kWh", "volume"].sum()),
        "cost_usd": float(df["cost_usd"].sum()),
        "co2e_t": float(df["co2e_kg"].sum() / 1000),
        "cost_per_km": safe_div(float(df["cost_usd"].sum()), float(df["km"].sum())),
        "segments": int(df[["ownership", "vehicle_type"]].drop_duplicates().shape[0]),
        "months": int(df[["year", "month"]].drop_duplicates().shape[0]),
    }
