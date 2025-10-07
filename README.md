# ETF DataLake & Report – v3

Questa versione **sostituisce completamente** i file precedenti e corregge i numeri:
- `report.csv` ora contiene **profitto**, **rischio = Max Drawdown** (in % e in €), **CAGR%**, **orizzonte** (mediana giorni in posizione, n° trade).
- Robustezza nel salvataggio di `report.md` anche senza il pacchetto `tabulate`.
- Continua a creare i CSV giornalieri in `data/` per ogni ticker.
- (Opzionale) genera `portfolio_report.csv` per **Momentum Rotation** (top-2, mensile).

**Scheduling:** feriali 18:30 Europe/Rome (cron 16:30 UTC).  
**Capitale di riferimento:** €10000.  
**Ultimo aggiornamento:** 2025-10-07.
