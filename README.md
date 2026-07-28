# ETF Datalake

Fonte operativa unica degli storici usati dalla trading suite.

- `universe.csv` contiene l'universo di ETF quotati a Milano da aggiornare,
  con ticker Yahoo, ISIN e classificazione dell'esposizione.
- `scripts/update_universe.py` scarica gli storici dal 2018, normalizza lo schema,
  limita tutti i prezzi OHLC a tre decimali e verifica completezza e aggiornamento.
- Il quality gate accetta la pubblicazione solo con almeno 200 ETF validi.
- `latest/quality-report.json` espone esito e anomalia di ogni ticker.
- `latest/index.json` e `latest/eod-latest.csv` sono rigenerati dai file validati.
- `data/` conserva un CSV storico distinto per ciascun ETF.
- `tests/` verifica le regole di validazione dei dati OHLC.

Quando il provider restituisce un massimo inferiore all'apertura o alla chiusura,
oppure un minimo superiore a uno di questi due prezzi, la pipeline amplia il
range giornaliero fino a includerli. La correzione non modifica mai apertura o
chiusura ed è riportata esplicitamente in `quality-report.json`.

Il solo workflow operativo, `.github/workflows/fetch.yml`, gira nei giorni
feriali alle 18:30 circa (ora italiana estiva) ed è anche avviabile manualmente.
Esegue test, aggiornamento e validazione degli storici, rigenerazione degli
output in `latest/` e pubblicazione dei dati aggiornati.

Simulazioni, strategie e report di trading appartengono al repository
`etf-trading-suite`, non al datalake.
