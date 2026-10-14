import math

import pytest

from fleet_analytics.cleaning import coverage_matrix, parse_number, split_totals, to_long


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,721,771.43", 1721771.43),
        ("2,028,000", 2028000.0),
        ("849", 849.0),
        ("$0.00", 0.0),
        ("(1,000)", -1000.0),
        ("-5", -5.0),
        (" 12.5 ", 12.5),
        (3, 3.0),
    ],
)
def test_parse_number(text, expected):
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "  ", "-", None, "nan"])
def test_parse_number_empty_is_nan(text):
    assert math.isnan(parse_number(text))


def test_parse_number_rejects_garbage():
    with pytest.raises(ValueError):
        parse_number("abc")


def test_split_totals(small_raw):
    monthly, totals = split_totals(small_raw)
    assert len(monthly) == 4
    assert len(totals) == 2
    assert set(totals["Month"]) == {"Total"}


def test_to_long_shape_and_values(small_raw):
    long = to_long(small_raw)
    # car-gasolina x2 meses + truck-diésel + truck-eléctrico en enero; febrero truck vacío se elimina
    assert len(long) == 4
    assert set(long["fuel"]) == {"gasoline", "diesel", "electric"}
    jan_diesel = long[(long["month"] == 1) & (long["fuel"] == "diesel")].iloc[0]
    assert jan_diesel["km"] == 4000
    assert jan_diesel["volume"] == 1000
    assert jan_diesel["cost_usd"] == 1300
    assert jan_diesel["unit"] == "L"
    assert long.loc[long["fuel"] == "electric", "unit"].item() == "kWh"
    assert (long["source"] == "real").all()


def test_to_long_keeps_empty_when_asked(small_raw):
    long = to_long(small_raw, drop_empty=False)
    # 4 filas mensuales x 6 combustibles del catálogo (los ausentes en el header quedan en NaN)
    assert len(long) == 4 * 6


def test_to_long_labels_source(small_raw):
    assert (to_long(small_raw, source="synthetic")["source"] == "synthetic").all()


def test_to_long_rejects_unknown_month(small_raw):
    bad = small_raw.copy()
    bad.loc[0, "Month"] = "Smarch"
    with pytest.raises(ValueError, match="Meses no reconocidos"):
        to_long(bad)


def test_real_file_structure(real_raw):
    monthly, totals = split_totals(real_raw)
    assert len(monthly) == 84  # 12 meses x 7 segmentos
    assert len(totals) == 7
    long = to_long(real_raw)
    assert len(long) == 17
    assert set(long["fuel"]) == {"diesel"}
    assert long.groupby("vehicle_type").size().to_dict() == {"route trucks": 12, "tractor": 5}


def test_coverage_matrix(real_raw):
    cov = coverage_matrix(real_raw)
    assert cov.shape == (7, 12)
    assert int(cov.to_numpy().sum()) == 17
