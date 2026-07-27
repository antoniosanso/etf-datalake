#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in data_root.glob("*.csv") if p.is_file()])
    latest_rows = []
    index_items = []

    for p in files:
        ticker = p.stem
        try:
            df = pd.read_csv(p)
            aliases = {str(c).lower(): c for c in df.columns}
            date_col = aliases.get("date") or aliases.get("dt")
            if df.empty or date_col is None:
                continue
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col]).sort_values(date_col)
            if df.empty:
                continue
            last = df.iloc[-1]
            latest_rows.append({
                "Date": last[date_col],
                "Ticker": ticker,
                "Open": last.get(aliases.get("open", ""), None),
                "High": last.get(aliases.get("high", ""), None),
                "Low":  last.get(aliases.get("low", ""), None),
                "Close": last.get(aliases.get("close", ""), None),
                "Volume": last.get(aliases.get("volume", ""), None),
                "Currency": last.get(aliases.get("currency", ""), None),
            })
            index_items.append({
                "ticker": ticker,
                "path": f"data/{p.name}",
                "last_date": str(pd.to_datetime(last[date_col]).date()),
                "rows": int(df.shape[0]),
                "bytes": p.stat().st_size
            })
        except Exception as exc:
            raise RuntimeError(f"Cannot index {p}: {exc}") from exc

    # Write latest CSV (aggregated snapshot)
    if latest_rows:
        pd.DataFrame(latest_rows, columns=["Date","Ticker","Open","High","Low","Close","Volume","Currency"]).to_csv(out_dir / "eod-latest.csv", index=False)

    # Write compact JSON index
    index = {
        "count": len(index_items),
        "generated_utc": pd.Timestamp.now("UTC").isoformat(),
        "items": index_items
    }
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",",":")), encoding="utf-8")

if __name__ == "__main__":
    main()
