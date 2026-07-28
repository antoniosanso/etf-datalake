import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


sys.modules.setdefault("yfinance", types.SimpleNamespace())
MODULE_PATH = Path(__file__).parents[1] / "scripts" / "update_universe.py"
SPEC = importlib.util.spec_from_file_location("update_universe", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_repair_expands_range_without_changing_open_or_close():
    source = pd.DataFrame(
        {
            "Open": [10.0, 10.0, 10.0],
            "High": [9.5, 11.0, 11.0],
            "Low": [9.0, 10.5, 9.0],
            "Close": [9.8, 10.8, 10.5],
        }
    )

    repaired, audit = MODULE.repair_and_validate_ohlc(source)

    assert repaired["Open"].equals(source["Open"])
    assert repaired["Close"].equals(source["Close"])
    assert repaired["High"].tolist() == [10.0, 11.0, 11.0]
    assert repaired["Low"].tolist() == [9.0, 10.0, 9.0]
    assert audit == {"ohlc_repaired_rows": 2, "ohlc_invalid_rows": 0}


def test_repair_reports_non_positive_prices_as_invalid():
    source = pd.DataFrame(
        {"Open": [10.0], "High": [11.0], "Low": [0.0], "Close": [10.5]}
    )

    _, audit = MODULE.repair_and_validate_ohlc(source)

    assert audit["ohlc_invalid_rows"] == 1
