import pandas as pd

from fleet_analytics import synthetic
from fleet_analytics.cleaning import load_raw, to_long
from fleet_analytics.validation import validate

from .conftest import write_csv


def rules(issues: pd.DataFrame) -> set[str]:
    return set(issues["rule"])


def test_clean_fixture_has_no_errors(small_raw):
    issues = validate(small_raw)
    assert not (issues["severity"] == "error").any()
    assert "R8_reconciliation" not in rules(issues)


def test_negative_and_incomplete(tmp_path):
    raw = load_raw(
        write_csv(
            tmp_path,
            [
                "January,2023,Canada,Own,car,1,-100,10,$10,1,,,,,,,,",
                "January,2023,Canada,Own,truck,1,,,,,500,,$10,1,,,,",
            ],
        )
    )
    issues = validate(raw)
    assert {"R1_negative", "R2_incomplete"} <= rules(issues)
    assert (issues["severity"] == "error").sum() >= 2


def test_implausible_efficiency_and_cost(tmp_path):
    raw = load_raw(write_csv(tmp_path, ["January,2023,Canada,Own,car,1,100000,10,$100,1,,,,,,,,"]))
    issues = validate(raw)
    assert "R3_efficiency" in rules(issues)  # 10,000 km/L
    assert "R4_unit_cost" in rules(issues)  # 10 USD/L
    assert "R5_km_per_vehicle" in rules(issues)  # 100,000 km/vehículo/mes


def test_reconciliation_mismatch(tmp_path):
    raw = load_raw(
        write_csv(
            tmp_path,
            [
                "January,2023,Canada,Own,car,1,1000,100,$120,1,,,,,,,,",
                "Total,2023,Canada,Own,car,1,999,100,$120,1,0,0,$0,0,0,0,$0,0",
            ],
        )
    )
    issues = validate(raw)
    rec = issues[issues["rule"] == "R8_reconciliation"]
    assert len(rec) == 1
    assert "km" in rec.iloc[0]["message"]


def test_real_file_findings(real_raw):
    issues = validate(real_raw)
    assert not (issues["severity"] == "error").any()
    assert not (issues["severity"] == "warning").any()  # los Totales del archivo concilian
    r6 = issues[issues["rule"] == "R6_constant_ratio"]
    assert len(r6) == 3  # rendimiento y precio fijos en route trucks; rendimiento fijo en tractor
    empty = issues[(issues["rule"] == "R9_coverage") & (issues["month"] == "todos")]
    assert len(empty) == 5  # 5 segmentos "owned, leased or renting" sin datos
    assert (issues["rule"] == "R7_fleet_quantity").sum() == 5


def test_synthetic_is_labeled_and_valid():
    raw = synthetic.generate(seed=1)
    long = to_long(raw, source="synthetic")
    assert (long["source"] == "synthetic").all()
    assert long["month"].nunique() == 12
    assert long["fuel"].nunique() >= 4
    issues = validate(raw, long)
    assert issues[issues["severity"].isin(["error", "warning"])].empty


def test_synthetic_is_reproducible():
    pd.testing.assert_frame_equal(synthetic.generate(seed=7), synthetic.generate(seed=7))
