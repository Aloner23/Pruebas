"""Fleet Energy Analytics: limpieza, validación y métricas de consumo energético de flotillas."""

from fleet_analytics.cleaning import load_raw, split_totals, to_long
from fleet_analytics.metrics import (
    co2e_by_fuel,
    fuel_share,
    monthly_trend,
    segment_summary,
    with_unit_metrics,
)
from fleet_analytics.validation import Issue, validate

__all__ = [
    "Issue",
    "co2e_by_fuel",
    "fuel_share",
    "load_raw",
    "monthly_trend",
    "segment_summary",
    "split_totals",
    "to_long",
    "validate",
    "with_unit_metrics",
]

__version__ = "0.1.0"
