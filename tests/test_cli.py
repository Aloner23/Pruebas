from fleet_analytics.__main__ import main

from .conftest import REAL_CSV


def test_cli_report_real(tmp_path):
    out = tmp_path / "r.html"
    assert main(["report", str(REAL_CSV), "--out", str(out), "--processed-dir", str(tmp_path / "p")]) == 0
    html = out.read_text(encoding="utf-8")
    assert "<svg" in html
    assert "Datos reales, cobertura parcial" in html
    assert "SINTÉTICO" not in html
    assert (tmp_path / "p" / "canada_2023_flotilla_long.csv").exists()


def test_cli_report_synthetic_is_labeled(tmp_path):
    out = tmp_path / "s.html"
    assert main(["report", "--synthetic", "--out", str(out), "--processed-dir", ""]) == 0
    html = out.read_text(encoding="utf-8")
    assert "DATOS SINTÉTICOS" in html
    assert "No representan ninguna flotilla real" in html


def test_cli_validate_exit_code():
    assert main(["validate", str(REAL_CSV)]) == 0
