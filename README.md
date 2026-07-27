# ETF Datalake

Fonte operativa unica degli storici usati dalla trading suite.

- `universe.csv` contiene i 98 ticker candidati recuperati dalla cronologia.
- `scripts/update_universe.py` scarica gli storici dal 2018, normalizza lo schema
  e verifica completezza e aggiornamento.
- Il quality gate accetta la pubblicazione solo con almeno 96 ETF validi.
- `latest/quality-report.json` espone esito e anomalia di ogni ticker.
- `latest/index.json` e `latest/eod-latest.csv` sono rigenerati dai file validati.

Il workflow gira nei giorni feriali alle 18:30 circa (ora italiana estiva) ed è
anche avviabile manualmente.
