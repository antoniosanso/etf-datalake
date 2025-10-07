import os, math, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

TICKERS_FILE = "tickers.txt"
DATA_DIR = "data"
START_YEARS = 10  # ~10 anni di storico

os.makedirs(DATA_DIR, exist_ok=True)

# Carica lista tickers (uno per riga)
if os.path.exists(TICKERS_FILE):
    with open(TICKERS_FILE, "r", encoding="utf-8") as f:
        TICKERS = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
else:
    TICKERS = ["SEME.MI","XAIX.MI","TNOW.MI","EDEF.PA"]

# Calcola data di inizio
today = dt.date.today()
try:
    start = today.replace(year=today.year - START_YEARS)
except ValueError:
    start = today - dt.timedelta(days=365*START_YEARS)

def download_ohlcv(ticker: str):
    try:
        df = yf.download(ticker, start=start.isoformat(), interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    except Exception as e:
        print(f"[{ticker}] ERROR download: {e}")
        return None
    if df is None or df.empty: 
        print(f"[{ticker}] NO DATA")
        return None
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(0):
            df = df[ticker]
        else:
            df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns=str.lower).reset_index().rename(columns={"date":"dt","adj close":"adj_close"})
    df["ticker"] = ticker
    df = df.dropna(subset=["open","high","low","close"])
    out = os.path.join(DATA_DIR, f"{ticker}.csv")
    df.to_csv(out, index=False)
    print(f"[{ticker}] saved -> {out} ({len(df)} rows)")
    return df

def atr14(df):
    h,l,c = df["high"].values, df["low"].values, df["close"].values
    if len(df) < 16: 
        return np.full(len(df), np.nan)
    tr = np.maximum.reduce([h[1:]-l[1:], np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])])
    atr = np.full(len(df), np.nan)
    seed = np.nanmean(tr[:14])
    vals = [np.nan, seed]
    for i in range(14, len(tr)):
        vals.append((vals[-1]*13 + tr[i]) / 14.0)
    atr[:len(vals)] = vals
    return atr

def backtest_variant(df, variant):
    d = df.copy()
    d["atr14"] = atr14(d)
    d["high20"] = d["high"].rolling(20).max().shift(1)
    d["volume_ma20"] = d["volume"].rolling(20).mean()
    d["volume_sd20"] = d["volume"].rolling(20).std(ddof=0)
    d["vol_z"] = (d["volume"] - d["volume_ma20"]) / d["volume_sd20"]
    d["ma50"] = d["close"].rolling(50).mean()
    d["ma200"] = d["close"].rolling(200).mean()

    if variant == "Aggressiva":
        z_th, atr_lo, atr_hi, buf, tstop, tp1_share, trail_mult, risk, adtv = 0.5, 0.5, 8.0, 0.05, None, 0.00, 3.0, 0.02, 3e5
    elif variant == "Intermedia v2":
        z_th, atr_lo, atr_hi, buf, tstop, tp1_share, trail_mult, risk, adtv = 0.6, 0.5, 8.0, 0.05, 20,   0.15, 3.0, 0.015, 5e5
    else:  # Conservativa v2
        z_th, atr_lo, atr_hi, buf, tstop, tp1_share, trail_mult, risk, adtv = 0.8, 0.5, 6.0, 0.05, None, 0.00, 3.5, 0.01, 5e5

    filt = (
        (d["atr14"]/d["close"]*100 >= atr_lo) &
        (d["atr14"]/d["close"]*100 <= atr_hi) &
        (d["vol_z"] >= z_th) &
        (d["ma50"] > d["ma200"]) &
        (d["volume_ma20"]*d["close"] >= adtv)
    )

    capital = 10000.0
    in_pos, entry, stop, qty, entry_idx = False, None, None, 0, None
    pnl_sum = 0.0
    tp_done = False

    for i in range(len(d)):
        if i == 0: continue
        row = d.iloc[i]

        if (not in_pos) and filt.iloc[i] and pd.notna(row["high20"]) and pd.notna(row["atr14"]):
            trigger = row["high20"] + buf*row["atr14"]
            if row["close"] >= trigger:
                risk_amt = capital * risk
                initial_stop = max(d.iloc[max(0,i-10):i]["low"].min(), row["close"] - 1.25*row["atr14"])
                if initial_stop < row["close"]:
                    rps = row["close"] - initial_stop
                    qty = int(risk_amt // rps) if rps > 0 else 0
                    if qty > 0:
                        in_pos = True; entry = row["close"]; stop = initial_stop; entry_idx = i; tp_done = False

        elif in_pos:
            rps = entry - stop
            tp1 = entry + 1.0*rps
            trail = row["close"] - trail_mult*(row["atr14"] if not math.isnan(row["atr14"]) else 0.0)
            stop_active = max(stop, trail)

            if (variant != "Aggressiva") and (not tp_done) and (row["high"] >= tp1):
                take = max(1, int(qty*(0.15 if variant == "Intermedia v2" else 0.0)))
                if take > 0:
                    pnl_sum += take*(tp1 - entry)
                    qty -= take
                    stop = entry
                    tp_done = True

            exit_price = None
            if (variant == "Intermedia v2") and ((i - entry_idx) >= 20):
                exit_price = row["close"]
            if exit_price is None and row["low"] <= stop_active:
                exit_price = stop_active

            if exit_price is not None:
                pnl_sum += (exit_price - entry) * qty
                in_pos = False; qty = 0; entry = stop = None; entry_idx = None

    if in_pos:
        last = d.iloc[-1]
        exit_price = last["close"]
        pnl_sum += (exit_price - entry) * qty

    return float(pnl_sum)

def buy_hold_pct(df):
    start_price = float(df["open"].iloc[0])
    end_price = float(df["close"].iloc[-1])
    return (end_price / start_price - 1.0) * 100.0

rows = []
for t in TICKERS:
    df = download_ohlcv(t)
    if df is None or df.empty:
        rows.append({"ticker": t, "status": "NO DATA"})
        continue
    strategies = ["Aggressiva","Intermedia v2","Conservativa v2"]
    perf = {s: backtest_variant(df, s) for s in strategies}
    best = max(perf, key=perf.get)
    best_pnl = perf[best]
    risk_eur = max(0.0, -best_pnl)
    bh = buy_hold_pct(df)

    rows.append({
        "ticker": t,
        "best_strategy": best,
        "profit_est_eur": round(best_pnl,2),
        "profit_est_pct": round(best_pnl/10000.0*100.0,2),
        "risk_est_eur": round(risk_eur,2),
        "risk_est_pct": round(risk_eur/10000.0*100.0,2),
        "horizon_hint": "swing–position (settimane/mesi)",
        "buy_hold_pct_ref": round(bh,2),
        "status": "OK"
    })

rep = pd.DataFrame(rows)
rep.to_csv("report.csv", index=False)

with open("report.md","w",encoding="utf-8") as f:
    f.write("# ETF – Report giornaliero (3 numeri)\n\n")
    f.write(rep.to_markdown(index=False))

print("Done. Wrote report.csv and report.md")
