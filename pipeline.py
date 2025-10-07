import os, math, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

# -------------------- CONFIG --------------------
TICKERS_FILE = "tickers.txt"
DATA_DIR = "data"
START_YEARS = 10      # ~10 anni di storico
CAPITAL0 = 10000.0    # capitale di riferimento per P&L €

os.makedirs(DATA_DIR, exist_ok=True)

# -------------------- TICKERS --------------------
def read_tickers():
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, "r", encoding="utf-8") as f:
            return [t.strip() for t in f if t.strip() and not t.strip().startswith("#")]
    # default fallback
    return ["SEME.MI","XAIX.MI","TNOW.MI","SMH.MI","RBOT.MI","STKX.MI","EDEF.MI"]

def start_date(years=START_YEARS):
    today = dt.date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today - dt.timedelta(days=365*years)

# -------------------- DATA --------------------
def dl_ohlcv(ticker: str, start_date):
    try:
        df = yf.download(ticker, start=start_date.isoformat(), interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    except Exception as e:
        print(f"[{ticker}] ERROR download: {e}")
        return None
    if df is None or df.empty:
        print(f"[{ticker}] NO DATA")
        return None
    # yfinance sometimes returns MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(0):
            df = df[ticker]
        else:
            df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns=str.lower).reset_index().rename(columns={"date":"dt","adj close":"adj_close"})
    df["ticker"] = ticker
    # remove rows with missing core fields
    df = df.dropna(subset=["open","high","low","close"])
    out = os.path.join(DATA_DIR, f"{ticker}.csv")
    df.to_csv(out, index=False)
    print(f"[{ticker}] saved -> {out} ({len(df)} rows)")
    return df

# -------------------- INDICATORS --------------------
def atr14(df: pd.DataFrame) -> np.ndarray:
    h,l,c = df["high"].values, df["low"].values, df["close"].values
    if len(df) < 16: return np.full(len(df), np.nan)
    tr = np.maximum.reduce([h[1:]-l[1:], np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])])
    atr = np.full(len(df), np.nan)
    seed = np.nanmean(tr[:14])
    vals = [np.nan, seed]
    for i in range(14, len(tr)):
        vals.append((vals[-1]*13 + tr[i]) / 14.0)
    atr[:len(vals)] = vals
    return atr

# -------------------- BACKTEST (with metrics) --------------------
def backtest_variant_with_metrics(df: pd.DataFrame, variant: str) -> dict:
    d = df.copy()
    # indicators
    d["atr14"] = atr14(d)
    d["high20"] = d["high"].rolling(20).max().shift(1)
    d["volume_ma20"] = d["volume"].rolling(20).mean()
    d["volume_sd20"] = d["volume"].rolling(20).std(ddof=0)
    d["vol_z"] = (d["volume"] - d["volume_ma20"]) / d["volume_sd20"]
    d["ma50"] = d["close"].rolling(50).mean()
    d["ma200"] = d["close"].rolling(200).mean()

    # params
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

    # simulation with mark-to-market equity
    cash = CAPITAL0
    shares = 0
    in_pos = False
    entry = stop = None
    entry_idx = None
    tp_done = False

    holds = []
    equity = []

    for i in range(len(d)):
        if i == 0:
            equity.append(cash)
            continue

        row = d.iloc[i]

        # ENTRY at close if trigger exceeded
        if (not in_pos) and filt.iloc[i] and pd.notna(row["high20"]) and pd.notna(row["atr14"]):
            trigger = row["high20"] + buf*row["atr14"]
            if row["close"] >= trigger:
                initial_stop = max(d.iloc[max(0,i-10):i]["low"].min(), row["close"] - 1.25*row["atr14"])
                rps = row["close"] - initial_stop
                if rps > 0:
                    risk_amt = (cash + shares*row["close"]) * risk
                    qty = int(risk_amt // rps)
                    if qty > 0:
                        entry = row["close"]
                        stop  = initial_stop
                        shares += qty
                        cash  -= qty * entry
                        in_pos = True
                        entry_idx = i
                        tp_done = False

        # MANAGEMENT
        if in_pos:
            rps = entry - stop
            tp1 = entry + 1.0*rps
            trail = row["close"] - trail_mult*(row["atr14"] if not math.isnan(row["atr14"]) else 0.0)
            stop_active = max(stop, trail)

            exit_price = None

            # TP1 partial (only for Intermedia)
            if (tp1_share > 0) and (not tp_done) and (row["high"] >= tp1):
                take = max(1, int(shares*tp1_share))
                cash += take * tp1
                shares -= take
                stop = entry  # move to BE on remaining
                tp_done = True

            # Time stop (only for Intermedia v2)
            if (tstop is not None) and ((i - entry_idx) >= tstop):
                exit_price = row["close"]

            # Stop/trail
            if (exit_price is None) and (row["low"] <= stop_active):
                exit_price = stop_active

            if exit_price is not None:
                cash += shares * exit_price
                holds.append(i - entry_idx)
                shares = 0
                in_pos = False
                entry = stop = None
                entry_idx = None

        # mark-to-market equity
        equity.append(cash + shares * row["close"])

    # close any open position at last close
    if in_pos:
        last = d.iloc[-1]
        cash += shares * float(last["close"])
        holds.append(len(d)-1 - entry_idx)
        shares = 0

    equity = pd.Series(equity, index=pd.to_datetime(d["dt"]))
    pnl_eur = float(equity.iloc[-1] - CAPITAL0)
    pnl_pct = pnl_eur / CAPITAL0 * 100.0

    # Max Drawdown
    peak = equity.cummax()
    dd_series = equity/peak - 1.0
    maxdd_pct = float(dd_series.min() * 100.0)

    # CAGR
    days = (equity.index[-1] - equity.index[0]).days or 1
    cagr_pct = ( (equity.iloc[-1]/equity.iloc[0]) ** (365.25/days) - 1.0 ) * 100.0

    median_hold = int(np.median(holds)) if holds else 0

    return {
        "pnl_eur": round(pnl_eur,2),
        "pnl_pct": round(pnl_pct,2),
        "maxdd_pct": round(abs(maxdd_pct),2),
        "maxdd_eur": round(abs(maxdd_pct)/100*CAPITAL0,2),
        "cagr_pct": round(cagr_pct,2),
        "median_hold_days": median_hold,
        "n_trades": len(holds)
    }

def buy_hold_pct(df: pd.DataFrame) -> float:
    start_price = float(df["open"].iloc[0])
    end_price = float(df["close"].iloc[-1])
    return (end_price / start_price - 1.0) * 100.0

# -------------------- PORTFOLIO MOMENTUM (optional) --------------------
def build_monthly_close(dfs: dict) -> pd.DataFrame:
    outs = []
    for t, df in dfs.items():
        s = df.set_index(pd.to_datetime(df["dt"]))["close"].asfreq("B").ffill()
        m = s.resample("M").last().rename(t)
        outs.append(m)
    return pd.concat(outs, axis=1)

def momentum_rotation_monthly(prices: pd.DataFrame, k: int = 2, lookback_months: int = 12) -> pd.Series:
    prices = prices.dropna(how="all")
    rets = prices.pct_change().fillna(0.0)
    equity = [1.0]
    for i in range(lookback_months, len(prices)-1):
        window = prices.iloc[i-lookback_months:i]
        mom = (window.iloc[-1] / window.iloc[0] - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
        top = mom.sort_values(ascending=False).index[:k]
        nxt = rets.iloc[i+1]
        r = sum((1.0/k) * nxt.get(t,0.0) for t in top)
        equity.append(equity[-1]*(1.0+r))
    equity = pd.Series(equity, index=prices.index[lookback_months:len(prices)])
    return equity

def cagr(series: pd.Series) -> float:
    if len(series) < 2: return 0.0
    years = (series.index[-1] - series.index[0]).days / 365.25
    total = series.iloc[-1] / series.iloc[0]
    if years <= 0 or total <= 0: return 0.0
    return total ** (1/years) - 1.0

def max_drawdown(series: pd.Series) -> float:
    if series.empty: return 0.0
    peak = series.cummax()
    dd = (series/peak - 1.0).min()
    return float(dd)

# -------------------- MAIN --------------------
def main():
    tickers = read_tickers()
    start = start_date()
    dfs = {}
    rows = []

    for t in tickers:
        df = dl_ohlcv(t, start)
        if df is None or df.empty:
            rows.append({"ticker": t, "status": "NO DATA"})
            continue

        dfs[t] = df

        variants = ["Aggressiva","Intermedia v2","Conservativa v2"]
        perf = {v: backtest_variant_with_metrics(df, v) for v in variants}
        best = max(perf, key=lambda k: perf[k]["pnl_eur"])

        rows.append({
            "ticker": t,
            "best_strategy": best,
            "profit_est_eur": perf[best]["pnl_eur"],
            "profit_est_pct": perf[best]["pnl_pct"],
            "risk_est_eur": perf[best]["maxdd_eur"],       # Max Drawdown in €
            "risk_est_pct": perf[best]["maxdd_pct"],       # Max Drawdown in %
            "horizon_hint": f"mediana hold {perf[best]['median_hold_days']}g; {perf[best]['n_trades']} trade",
            "CAGR_pct": perf[best]["cagr_pct"],
            "status": "OK"
        })

    rep = pd.DataFrame(rows)
    rep.to_csv("report.csv", index=False)
    # Markdown with fallback if 'tabulate' is missing
    try:
        md = rep.to_markdown(index=False)
    except Exception:
        md = rep.to_csv(index=False)
    with open("report.md","w",encoding="utf-8") as f:
        f.write("# ETF – Report giornaliero (3 numeri)\n\n")
        f.write(md)

    # ---- Portfolio Momentum Rotation (top-2, monthly) ----
    if len(dfs) >= 2:
        monthly = build_monthly_close(dfs)
        eq = momentum_rotation_monthly(monthly, k=2, lookback_months=12)
        if not eq.empty:
            series = eq * CAPITAL0
            total_ret = series.iloc[-1]/series.iloc[0] - 1.0
            cagr_pct = cagr(series) * 100.0
            dd_pct = max_drawdown(series) * 100.0
            pr = pd.DataFrame({
                "strategy": ["Momentum Rotation (top-2, monthly)"],
                "start": [str(series.index[0].date())],
                "end":   [str(series.index[-1].date())],
                "total_return_pct": [round(total_ret*100.0,2)],
                "CAGR_pct": [round(cagr_pct,2)],
                "MaxDD_pct": [round(dd_pct,2)],
            })
            pr.to_csv("portfolio_report.csv", index=False)

    print("Done v3.")

if __name__ == "__main__":
    main()
