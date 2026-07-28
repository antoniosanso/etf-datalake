# ETF Datalake

Questo repository raccoglie, controlla e pubblica gli storici giornalieri degli ETF utilizzati dalla ETF Trading Platform.

È il **deposito dati** del progetto: non decide cosa comprare o vendere e non esegue strategie di trading. Simulazioni, segnali, portafogli e report appartengono al repository separato `etf-trading-suite`.

## Cosa fa

La pipeline:

1. legge da `universe.csv` l'elenco degli strumenti da seguire;
2. scarica da Yahoo Finance i dati giornalieri disponibili a partire dal 1° gennaio 2018;
3. normalizza ogni serie nello stesso formato;
4. arrotonda `Open`, `High`, `Low` e `Close` a tre decimali;
5. verifica completezza, coerenza e aggiornamento dei dati;
6. salva uno storico CSV separato per ogni ETF valido;
7. genera gli indici e il riepilogo più recente;
8. pubblica gli aggiornamenti nel repository solo se il controllo qualità viene superato.

## Universo degli strumenti

`universe.csv` contiene attualmente 325 ETF candidati quotati sul mercato ETFplus di Borsa Italiana, inclusi strumenti con esposizioni geografiche, settoriali, tematiche e obbligazionarie anche parzialmente sovrapposte.

Per ogni strumento sono conservati:

- ticker Yahoo con suffisso `.MI`;
- ISIN;
- denominazione;
- benchmark;
- area geografica;
- categoria;
- emittente.

`SEME.MI`, `XAIX.MI` e `TNOW.MI` sono strumenti obbligatori dell'universo e la loro presenza è verificata dai test automatici.

L'inclusione in `universe.csv` non garantisce che uno strumento disponga sempre di uno storico sufficiente o aggiornato: la validità viene verificata nuovamente a ogni esecuzione.

## Struttura del repository

| Percorso | Contenuto |
|---|---|
| `universe.csv` | Elenco e classificazione degli ETF candidati |
| `data/<TICKER>.csv` | Storico giornaliero di ciascun ETF valido |
| `latest/eod-latest.csv` | Ultima barra disponibile di tutti gli ETF validi |
| `latest/index.json` | Indice dei file storici con date, righe e dimensioni |
| `latest/quality-report.json` | Esito dei controlli e anomalie per ciascun ticker |
| `scripts/update_universe.py` | Download, normalizzazione e validazione degli storici |
| `scripts/build_index.py` | Generazione dell'indice e del riepilogo più recente |
| `tests/test_update_universe.py` | Test delle regole sull'universo e sui prezzi OHLC |
| `.github/workflows/fetch.yml` | Unico workflow automatico operativo |

## Formato dei dati storici

Ogni file in `data/` usa le colonne:

| Colonna | Significato |
|---|---|
| `Date` | Data della seduta |
| `Ticker` | Simbolo Yahoo dell'ETF |
| `Open` | Prezzo di apertura |
| `High` | Prezzo massimo |
| `Low` | Prezzo minimo |
| `Close` | Prezzo di chiusura |
| `Volume` | Volume riportato dal provider |

Tutti i prezzi OHLC sono salvati con un massimo di tre decimali. Il volume non viene arrotondato con la stessa regola.

## Controlli qualità

Uno strumento è considerato valido soltanto se:

- restituisce dati utilizzabili;
- contiene almeno 50 osservazioni;
- l'ultima osservazione non è più vecchia di sette giorni;
- non contiene prezzi OHLC mancanti, nulli, negativi o incoerenti.

La pubblicazione complessiva supera il quality gate soltanto se risultano validi almeno 200 ETF. Il numero effettivo può quindi essere inferiore ai 325 candidati e può cambiare nel tempo.

### Correzione delle barre OHLC

Per una barra giornaliera deve valere:

- `High` maggiore o uguale ad apertura e chiusura;
- `Low` minore o uguale ad apertura e chiusura.

Se Yahoo Finance restituisce un intervallo incompatibile, la pipeline amplia esclusivamente `High` o `Low` quanto basta per includere `Open` e `Close`. Apertura e chiusura non vengono mai modificate da questa correzione.

Il numero di righe corrette e le eventuali righe ancora non valide sono registrati in `latest/quality-report.json`. Questo rende i dati adatti alle analisi basate sui prezzi di chiusura, ma richiede maggiore cautela per strategie che dipendono dai massimi e minimi intraday.

## Aggiornamento automatico

L'unico workflow operativo è `.github/workflows/fetch.yml`.

Viene eseguito:

- dal lunedì al venerdì alle 16:30 UTC, cioè alle 18:30 in Italia durante l'ora legale e alle 17:30 durante l'ora solare;
- automaticamente quando cambiano l'universo, gli script o il workflow;
- manualmente dalla sezione **Actions** di GitHub.

A ogni esecuzione il workflow:

1. installa Python 3.11 e le dipendenze;
2. esegue i test;
3. scarica e valida l'intero universo;
4. rigenera i file in `data/` e `latest/`;
5. verifica il superamento del quality gate;
6. crea automaticamente un commit se i dati sono cambiati.

Se i test falliscono, restano meno di 200 ETF validi o vengono rilevate barre OHLC non valide, la pubblicazione viene bloccata.

## Limiti da conoscere

- Yahoo Finance è una fonte esterna e può avere ritardi, indisponibilità o anomalie, soprattutto sugli ETF meno liquidi.
- Il ticker identifica la quotazione milanese usata dalla pipeline; l'ISIN identifica stabilmente lo strumento.
- La presenza nel datalake non equivale a una raccomandazione d'investimento.
- Duplicati o sovrapposizioni di esposizione sono intenzionali e permettono alla trading suite di confrontare strumenti simili.
- Gli storici giornalieri non ricostruiscono in modo affidabile l'ordine degli eventi intraday.

## Documentazione

Questo `README.md` è l'unico documento descrittivo e operativo del repository. Non sono richiesti file separati come `README_OPS.md`, `DECISIONS.md` o `RUNBOOK.md`.
