import math

import pandas as pd
import pytest

from fleet_analytics.cleaning import to_long
from fleet_analytics.emissions import EMISSION_FACTORS_KG_PER_UNIT
from fleet_analytics.metrics import (
    add_co2e,
    co2e_by_fuel,
    fuel_share,
    headline,
    monthly_trend,
    safe_div,
    segment_summary,
    with_unit_metrics,
)


def test_safe_div_handles_zero_and_nan():
    out = safe_div(pd.Series([10.0, 5.0, 1.0]), pd.Series([2.0, 0.0, float("nan")]))
    assert out.iloc[0] == 5
    assert math.isnan(out.iloc[1]) and math.isnan(out.iloc[2])
    assert safe_div(1.0, 4.0) == 0.25
    assert math.isnan(safe_div(1.0, 0.0))


def test_unit_metrics(small_raw):
    m = with_unit_metrics(to_long(small_raw)).set_index(["month", "vehicle_type", "fuel"])
    d = m.loc[(1, "truck", "diesel")]
    assert d["efficiency"] == pytest.approx(4.0)  # 4000 km / 1000 L
    assert d["l_per_100km"] == pytest.approx(25.0)
    assert d["cost_per_km"] == pytest.approx(1300 / 4000)
    assert d["cost_per_unit"] == pytest.approx(1.3)
    assert d["km_per_vehicle"] == pytest.approx(800)
    assert d["co2e_kg"] == pytest.approx(1000 * EMISSION_FACTORS_KG_PER_UNIT["diesel"])
    assert d["co2e_g_per_km"] == pytest.approx(1000 * 2680 / 4000)
    e = m.loc[(1, "truck", "electric")]
    assert e["efficiency"] == pytest.approx(1.2)  # km/kWh
    assert math.isnan(e["l_per_100km"])  # no aplica a kWh


def test_segment_summary_recomputes_ratios_from_totals(small_raw):
    s = segment_summary(to_long(small_raw)).set_index(["vehicle_type", "fuel"])
    car = s.loc[("car", "gasoline")]
    assert car["km"] == 2200
    assert car["volume"] == 200
    # ratio de totales (2200/200 = 11), no promedio de ratios ((10 + 12) / 2 = 11 coincide), usar costo:
    assert car["cost_per_km"] == pytest.approx(250 / 2200)
    assert car["vehicles"] == 10  # inventario: máximo, no suma
    assert car["months_reported"] == 2


def test_ratio_of_sums_not_mean_of_ratios():
    long = pd.DataFrame(
        {
            "source": "real", "year": 2023, "month": [1, 2], "month_name": ["January", "February"],
            "country": "X", "ownership": "O", "vehicle_type": "T", "fleet_quantity": 1.0,
            "fuel": "diesel", "unit": "L", "km": [100.0, 900.0], "volume": [10.0, 300.0],
            "cost_usd": [10.0, 300.0], "vehicles": 1.0,
        }
    )  # fmt: skip
    s = segment_summary(long).iloc[0]
    assert s["efficiency"] == pytest.approx(1000 / 310)  # no (10 + 3) / 2


def test_monthly_trend_total(small_raw):
    t = monthly_trend(to_long(small_raw), by=[])
    assert list(t["month"]) == [1, 2]
    assert t.loc[t["month"] == 1, "cost_usd"].item() == pytest.approx(120 + 1300 + 60)


def test_fuel_share_sums_to_one(small_raw):
    shares = fuel_share(to_long(small_raw), "cost_usd")
    assert shares["share"].sum() == pytest.approx(1.0)
    assert shares.iloc[0]["fuel"] == "diesel"


def test_fuel_share_rejects_volume(small_raw):
    with pytest.raises(ValueError):
        fuel_share(to_long(small_raw), "volume")


def test_co2e_by_fuel(small_raw):
    c = co2e_by_fuel(to_long(small_raw)).set_index("fuel")
    assert c.loc["gasoline", "co2e_t"] == pytest.approx(200 * 2.31 / 1000)
    assert c.loc["electric", "co2e_t"] == pytest.approx(500 * 0.12 / 1000)


def test_add_co2e_unknown_fuel_raises(small_raw):
    long = to_long(small_raw)
    with pytest.raises(KeyError):
        add_co2e(long, factors={"diesel": 1.0})


def test_headline_does_not_mix_liters_and_kwh(small_raw):
    h = headline(to_long(small_raw))
    assert h["liters"] == 200 + 1000
    assert h["kwh"] == 500
    assert h["cost_usd"] == pytest.approx(250 + 1300 + 60)


def test_real_data_known_values(real_raw):
    s = segment_summary(to_long(real_raw)).set_index("vehicle_type")
    assert s.loc["route trucks", "efficiency"] == pytest.approx(4.0)
    assert s.loc["tractor", "efficiency"] == pytest.approx(2.2222, rel=1e-4)
    assert s.loc["route trucks", "km"] == 26_364_000
    assert s.loc["tractor", "km"] == 13_957_605
