# Datalake — Build Index & Latest (minimal)
Carica questa cartella **direttamente nel repo `etf-datalake`**:
- `.github/workflows/build_index.yml`
- `scripts/build_index.py`

Cosa fa:
- Legge `data/*.csv`
- Genera `latest/index.json` (ticker, path, last_date, rows, bytes, count)
- Genera/aggiorna `latest/eod-latest.csv` (snapshot aggregato)
Frequenza: ogni giorno feriale 18:20 (Europe/Rome circa) + avviabile a mano.
