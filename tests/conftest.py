from pathlib import Path

import pandas as pd
import pytest

from fleet_analytics.cleaning import load_raw

ROOT = Path(__file__).resolve().parents[1]
REAL_CSV = ROOT / "data" / "raw" / "canada_2023_flotilla.csv"

HEADER = (
    "Month,Year,Country,Ownership,Type,Quantity,"
    "Gasoline_km,Gasoline_lt,Gasoline_$ (US Dlls),Gasoline_Quantity,"
    "Diesel_km,Diesel_lt,Diesel_$ (US Dlls),Diesel_Quantity,"
    "Electric_km,Electric_kWh,Electric_$ (US Dlls),Electric_Quantity"
)


def write_csv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "flotilla.csv"
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def small_raw(tmp_path) -> pd.DataFrame:
    rows = [
        'January,2023,Canada,Own,car,"10","1,000",100,"$120.00",10,,,,,,,,',
        'January,2023,Canada,Own,truck,5,,,,,"4,000","1,000","$1,300.00",5,"600",500,$60,2',
        'February,2023,Canada,Own,car,10,"1,200",100,"$130.00",10,,,,,,,,',
        "February,2023,Canada,Own,truck,5,,,,,,,,,,,,",
        'Total,2023,Canada,Own,car,10,"2,200",200,$250.00,10,0,0,$0.00,0,0,0,$0.00,0',
        'Total,2023,Canada,Own,truck,5,0,0,$0.00,0,"4,000","1,000","$1,300.00",5,600,500,$60.00,2',
    ]
    return load_raw(write_csv(tmp_path, rows))


@pytest.fixture
def real_raw() -> pd.DataFrame:
    return load_raw(REAL_CSV)
