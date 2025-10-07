# ETF DataLake & 3-Numbers Report (Autonomous)

Questa pipeline GitHub Actions scarica ~10 anni di dati giornalieri per i ticker in `tickers.txt`,
genera i CSV in `data/` e produce due report: `report.csv` e `report.md` con i **3 numeri** (profitto, rischio, orizzonte).

**Scheduling:** feriali alle 18:30 Europe/Rome (cron UTC 16:30). Puoi avviare manualmente dal tab **Actions**.

## Come usare
1. Crea un repository vuoto su GitHub.
2. Aggiungi questi file:
   - `.github/workflows/fetch.yml`
   - `pipeline.py`
   - `tickers.txt`
   - `README.md`
3. Vai su **Actions** → **Run workflow**. Al termine vedrai `data/*.csv`, `report.csv`, `report.md`.

## Note
- Aggiungi/rimuovi ETF modificando `tickers.txt` (uno per riga). Esempio:
  ```
  SEME.MI
  XAIX.MI
  TNOW.MI
  EDEF.PA
  ```
- Per massimizzare robustezza, in fase 2 aggiungeremo: max drawdown preciso, multi-orizzonte (10/5/3/1/YTD), rotazione momentum e dual momentum.
- Ultimo aggiornamento: 2025-10-07
