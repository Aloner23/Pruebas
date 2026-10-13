"""Carga y limpieza del template mensual de flotilla (formato ancho -> formato largo/tidy).

El CSV original tiene una fila por (mes, tipo de propiedad, tipo de vehículo) y, por cada
combustible, cuatro columnas: ``<Combustible>_km``, ``<Combustible>_lt`` (o ``_kWh`` para
eléctrico), ``<Combustible>_$ (US Dlls)`` y ``<Combustible>_Quantity``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

#: Prefijo de columna en el CSV -> nombre normalizado del combustible.
#: Nota: el template dice "NCG (gas)"; se interpreta como gas natural comprimido (CNG/GNC),
#: con volumen en litros equivalentes de gasolina (ver fleet_analytics.emissions).
FUEL_PREFIXES = {
    "Gasoline": "gasoline",
    "Diesel": "diesel",
    "Ethanol": "ethanol",
    "LPG(gas)": "lpg",
    "NCG (gas)": "cng",
    "Electric": "electric",
}

#: Unidad de volumen/energía con la que se reporta cada combustible.
FUEL_UNITS = {
    "gasoline": "L",
    "diesel": "L",
    "ethanol": "L",
    "lpg": "L",
    "cng": "L",
    "electric": "kWh",
}

_METRIC_SUFFIX = {
    "km": "km",
    "lt": "volume",
    "kWh": "volume",
    "$ (US Dlls)": "cost_usd",
    "Quantity": "vehicles",
}

ID_COLUMNS = ["Month", "Year", "Country", "Ownership", "Type", "Quantity"]

LONG_COLUMNS = [
    "source",
    "year",
    "month",
    "month_name",
    "country",
    "ownership",
    "vehicle_type",
    "fleet_quantity",
    "fuel",
    "unit",
    "km",
    "volume",
    "cost_usd",
    "vehicles",
]


def parse_number(value: object) -> float:
    """Convierte textos como ``"$1,721,771.43"``, ``"2,028,000"`` o ``""`` a float (NaN si vacío)."""
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in {"", "-", "nan", "NaN", "None"}:
        return float("nan")
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[\s$,()]", "", text)
    if text.startswith("-"):
        negative, text = True, text[1:]
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"Valor numérico no interpretable: {value!r}") from exc
    return -number if negative else number


def load_raw(path: str | Path) -> pd.DataFrame:
    """Lee el CSV crudo como texto (sin inferir tipos) y valida que tenga las columnas esperadas."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in ID_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {missing}")
    for col in ("Month", "Country", "Ownership", "Type"):
        df[col] = df[col].str.strip()
    return df


def split_totals(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa las filas mensuales de las filas ``Total`` (que se usan sólo para conciliar)."""
    is_total = raw["Month"].str.lower().eq("total")
    return raw.loc[~is_total].copy(), raw.loc[is_total].copy()


def _fuel_columns(columns: list[str]) -> dict[tuple[str, str], str]:
    """Mapea (fuel, métrica) -> nombre de columna original."""
    mapping: dict[tuple[str, str], str] = {}
    for col in columns:
        for prefix, fuel in FUEL_PREFIXES.items():
            if col.startswith(prefix + "_"):
                suffix = col[len(prefix) + 1 :]
                if suffix in _METRIC_SUFFIX:
                    mapping[(fuel, _METRIC_SUFFIX[suffix])] = col
    return mapping


def to_long(raw: pd.DataFrame, source: str = "real", drop_empty: bool = True) -> pd.DataFrame:
    """Transforma el template ancho a formato largo: una fila por segmento-mes-combustible.

    Parameters
    ----------
    raw:
        Salida de :func:`load_raw` (puede incluir filas ``Total``; se excluyen).
    source:
        Etiqueta de procedencia (``"real"`` o ``"synthetic"``). Se conserva en cada fila
        para que nunca se mezclen cifras sintéticas con reales sin etiqueta.
    drop_empty:
        Si es True, elimina combinaciones sin ningún dato numérico (o todo en cero).
    """
    monthly, _ = split_totals(raw)
    unknown = sorted(set(monthly["Month"].str.lower()) - set(MONTHS))
    if unknown:
        raise ValueError(f"Meses no reconocidos: {unknown}")

    fuel_cols = _fuel_columns(list(raw.columns))
    frames = []
    for fuel in FUEL_PREFIXES.values():
        part = pd.DataFrame(
            {
                "source": source,
                "year": monthly["Year"].map(parse_number).astype("Int64"),
                "month": monthly["Month"].str.lower().map(MONTHS).astype("Int64"),
                "month_name": monthly["Month"].str.title(),
                "country": monthly["Country"],
                "ownership": monthly["Ownership"],
                "vehicle_type": monthly["Type"],
                "fleet_quantity": monthly["Quantity"].map(parse_number),
                "fuel": fuel,
                "unit": FUEL_UNITS[fuel],
            }
        )
        for metric in ("km", "volume", "cost_usd", "vehicles"):
            col = fuel_cols.get((fuel, metric))
            part[metric] = monthly[col].map(parse_number) if col else float("nan")
        frames.append(part)

    long = pd.concat(frames, ignore_index=True)[LONG_COLUMNS]
    if drop_empty:
        values = long[["km", "volume", "cost_usd", "vehicles"]]
        has_data = values.fillna(0).ne(0).any(axis=1)
        long = long.loc[has_data]
    return long.sort_values(["year", "month", "ownership", "vehicle_type", "fuel"]).reset_index(drop=True)


def totals_to_long(raw: pd.DataFrame) -> pd.DataFrame:
    """Convierte las filas ``Total`` del CSV al mismo esquema largo (sin columna de mes)."""
    _, totals = split_totals(raw)
    if totals.empty:
        return pd.DataFrame(columns=["ownership", "vehicle_type", "fuel", "km", "volume", "cost_usd"])
    tmp = totals.copy()
    tmp["Month"] = "January"  # marcador para reutilizar to_long; se descarta después
    long = to_long(tmp, drop_empty=False)
    return long[["ownership", "vehicle_type", "fuel", "km", "volume", "cost_usd", "vehicles"]]


def coverage_matrix(raw: pd.DataFrame) -> pd.DataFrame:
    """Matriz segmento x mes con True si la fila tiene al menos un dato numérico distinto de cero."""
    monthly, _ = split_totals(raw)
    value_cols = [c for c in raw.columns if c not in ID_COLUMNS]
    numeric = monthly[value_cols].apply(lambda s: s.map(parse_number)).fillna(0)
    flag = numeric.ne(0).any(axis=1)
    out = pd.DataFrame(
        {
            "segment": monthly["Ownership"] + " | " + monthly["Type"],
            "month": monthly["Month"].str.lower().map(MONTHS),
            "has_data": flag,
        }
    )
    return out.pivot_table(index="segment", columns="month", values="has_data", aggfunc="any")
