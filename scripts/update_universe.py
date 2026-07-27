#!/usr/bin/env python3
"""Download, validate and publish the ETF universe.

The candidate list intentionally contains 98 symbols recovered from repository
history.  A run is accepted only when at least 96 symbols are valid and fresh.
This avoids silently inventing which two symbols were absent from the old
96-ticker snapshot, which is no longer present in Git or Actions artifacts.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

REQUIRED = ("Date", "Ticker", "Open", "High", "Low", "Close", "Volume")


def normalize(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=REQUIRED)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [str(c[0]) for c in raw.columns]
    out = raw.reset_index()
    out.columns = [str(c).strip().replace(" ", "_") for c in out.columns]
    out = out.rename(columns={"Datetime": "Date", "Adj_Close": "AdjClose"})
    if "Date" not in out or "Close" not in out:
        return pd.DataFrame(columns=REQUIRED)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=True).dt.tz_localize(None)
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in out:
            out[col] = 0 if col == "Volume" else pd.NA
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Ticker"] = ticker
    out = out[list(REQUIRED)].dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return out.drop_duplicates(["Date", "Ticker"], keep="last").sort_values("Date")


def download(ticker: str, start: str, attempts: int = 3) -> pd.DataFrame:
    for attempt in range(attempts):
        try:
            raw = yf.download(
                ticker,
                start=start,
                interval="1d",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=False,
                timeout=20,
            )
            data = normalize(raw, ticker)
            if not data.empty:
                return data
        except Exception as exc:
            print(f"[WARN] {ticker} attempt {attempt + 1}: {exc}")
        time.sleep(2**attempt)
    return pd.DataFrame(columns=REQUIRED)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="universe.csv")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--latest-dir", default="latest")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--min-valid", type=int, default=96)
    parser.add_argument("--max-stale-days", type=int, default=7)
    args = parser.parse_args()

    candidates = (
        pd.read_csv(args.universe)["ticker"].dropna().astype(str).str.strip().tolist()
    )
    if len(candidates) != len(set(candidates)):
        raise SystemExit("Universe contains duplicate tickers")
    if len(candidates) < args.min_valid:
        raise SystemExit(f"Only {len(candidates)} candidates; need {args.min_valid}")

    data_dir, latest_dir = Path(args.data_dir), Path(args.latest_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for old_file in data_dir.glob("*.csv"):
        if old_file.stem not in candidates:
            old_file.unlink()
    freshness_cutoff = date.today() - timedelta(days=args.max_stale_days)
    results, latest_rows = [], []

    for ticker in candidates:
        frame = download(ticker, args.start)
        status, reason = "valid", ""
        if frame.empty:
            status, reason = "invalid", "no_data"
        else:
            first_date = frame["Date"].min().date()
            last_date = frame["Date"].max().date()
            if last_date < freshness_cutoff:
                status, reason = "invalid", "stale"
            elif len(frame) < 50:
                status, reason = "invalid", "too_short"
        if status == "valid":
            frame.to_csv(data_dir / f"{ticker}.csv", index=False)
            latest_rows.append(frame.iloc[-1].to_dict())
        else:
            stale_file = data_dir / f"{ticker}.csv"
            if stale_file.exists():
                stale_file.unlink()
        results.append(
            {
                "ticker": ticker,
                "status": status,
                "reason": reason,
                "rows": int(len(frame)),
                "first_date": str(frame["Date"].min().date()) if not frame.empty else None,
                "last_date": str(frame["Date"].max().date()) if not frame.empty else None,
            }
        )
        print(f"[{status.upper()}] {ticker}: {len(frame)} rows {reason}")

    valid = [row for row in results if row["status"] == "valid"]
    report = {
        "generated_utc": pd.Timestamp.now(tz=timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "valid_count": len(valid),
        "minimum_required": args.min_valid,
        "invalid_count": len(results) - len(valid),
        "status": "pass" if len(valid) >= args.min_valid else "fail",
        "tickers": results,
    }
    (latest_dir / "quality-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if latest_rows:
        pd.DataFrame(latest_rows, columns=REQUIRED).to_csv(
            latest_dir / "eod-latest.csv", index=False
        )
    if len(valid) < args.min_valid:
        raise SystemExit(
            f"Quality gate failed: {len(valid)} valid ETFs, minimum {args.min_valid}"
        )


if __name__ == "__main__":
    main()
