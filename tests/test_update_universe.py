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

UNIVERSE_PATH = Path(__file__).parents[1] / "universe.csv"


def test_universe_has_required_milan_etfs_and_enough_candidates():
    universe = pd.read_csv(UNIVERSE_PATH)

    assert universe["ticker"].is_unique
    assert len(universe) >= 200
    assert {"SEME.MI", "XAIX.MI", "TNOW.MI"} <= set(universe["ticker"])
    assert universe["isin"].str.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}").all()


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
