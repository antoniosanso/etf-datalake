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
            df = pd.read_csv(p, parse_dates=["Date"])
            if df.empty or "Date" not in df.columns:
                continue
            df = df.sort_values("Date")
            last = df.iloc[-1]
            latest_rows.append({
                "Date": last["Date"],
                "Ticker": ticker,
                "Open": last.get("Open", None),
                "High": last.get("High", None),
                "Low":  last.get("Low", None),
                "Close": last.get("Close", None),
                "Volume": last.get("Volume", None),
                "Currency": last.get("Currency", None),
            })
            index_items.append({
                "ticker": ticker,
                "path": f"data/{p.name}",
                "last_date": str(pd.to_datetime(last["Date"]).date()),
                "rows": int(df.shape[0]),
                "bytes": p.stat().st_size
            })
        except Exception:
            # skip unreadable files
            continue

    # Write latest CSV (aggregated snapshot)
    if latest_rows:
        pd.DataFrame(latest_rows, columns=["Date","Ticker","Open","High","Low","Close","Volume","Currency"]).to_csv(out_dir / "eod-latest.csv", index=False)

    # Write compact JSON index
    index = {
        "count": len(index_items),
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "items": index_items
    }
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",",":")), encoding="utf-8")

if __name__ == "__main__":
    main()
