# Analyzer And Report

## Indice
1. [Panoramica](#panoramica)
2. [Prerequisiti](#prerequisiti)
3. [Come Eseguire Gli Script](#come-eseguire-gli-script)
4. [Script Disponibili](#script-disponibili)
5. [Ordine Consigliato Di Esecuzione](#ordine-consigliato-di-esecuzione)
6. [Output Generati](#output-generati)
7. [Troubleshooting](#troubleshooting)

## Panoramica
Questa cartella contiene gli script Python per analisi quantitativa, analisi map-centric e generazione grafici finali del progetto RHCR.

Script inclusi:
- `analyze_grid_graphs.py`: analisi topologica delle mappe RHCR e export GraphML.
- `analyze_conflict_profile.py`: profilo temporale di conflitti e runtime dalle run sperimentali.
- `analyze_bottleneck.py`: analisi di congestione spaziale (heatmap e corridoi critici) da `paths.txt`.
- `analyze_normalized_metrics.py`: confronto normalizzato (per agente e per densita) tra mappe/solver.
- `generate_report_plots.py`: produzione dei grafici finali per report e tesi.

## Prerequisiti
Dalla root del repository:

```bash
pip install -r requirements.txt
```

Dipendenze principali usate dagli script:
- pandas
- numpy
- matplotlib
- networkx

## Come Eseguire Gli Script
Gli script usano molti percorsi relativi (`../exp`, `../maps`), quindi e consigliato eseguirli dalla cartella `analyzer_and_report`:

```bash
cd analyzer_and_report
```

## Script Disponibili
### 1) analyze_grid_graphs.py
Scopo:
- converte le mappe RHCR in grafo diretto pesato;
- produce visualizzazioni griglia/grafo e file GraphML.

Comando base:

```bash
python analyze_grid_graphs.py
```

Input attesi (default nello script):
- `warehouse_map.grid`
- `warehouse_optimized.grid`
- `sorting_map.grid`

Output principali:
- `<map>_grid.png`
- `<map>_graph.png`
- `<map>_zoom.png`
- `<map>.graphml`

### 2) analyze_conflict_profile.py
Scopo:
- analizza collisioni e runtime per finestra temporale da `solver.csv`;
- confronta andamento per mappa, solver e numero agenti.

Comando base:

```bash
python analyze_conflict_profile.py
```

Comandi utili:

```bash
python analyze_conflict_profile.py --k 50 80
python analyze_conflict_profile.py --exp_dir ../exp/sensitivity_sweep --w 40 --h 5 --seed 42
```

Output principali:
- `conflict_profile_k*.png`
- `conflict_aggregate.png`
- `conflict_summary.csv`

Output directory (default):
- `../exp/analysis_conflicts/`

### 3) analyze_bottleneck.py
Scopo:
- analizza i file `paths.txt` per identificare corridoi critici e celle congestionate;
- genera heatmap e suggerimenti di micro-modifica della mappa.

Comando base:

```bash
python analyze_bottleneck.py --exp_dir ../exp --map ../maps/warehouse_map.grid
```

Comando esteso (output custom):

```bash
python analyze_bottleneck.py --exp_dir ../exp --map ../maps/warehouse_map.grid --output ../exp/analysis_bottleneck
```

Output principali:
- `heatmap_<run>.png`
- `hist_<run>.png`
- `corridors_<run>.csv`
- `heatmap_aggregated.png`
- `corridors_aggregated.csv`
- `bottleneck_report.csv`

Output directory (default):
- `../exp/analysis_bottleneck/`

### 4) analyze_normalized_metrics.py
Scopo:
- confronta throughput/runtime normalizzati tra mappe e solver;
- evidenzia effetto di densita agenti e topologia mappa.

Comando base:

```bash
python analyze_normalized_metrics.py
```

Output principali:
- `normalized_metrics.csv`
- `fig1_absolute.png`
- `fig2_per_agent.png`
- `fig3_per_density.png`
- `fig4_whca_comparison.png`

Output directory (default):
- `../exp/analysis_normalized/`

Nota:
- lo script usa percorsi mappe predefiniti nelle costanti interne. Se il nome del file mappa nel repository e diverso, aggiornare i path nella sezione `EXP_DIRS` dello script.

### 5) generate_report_plots.py
Scopo:
- genera i grafici finali per il report sperimentale;
- integra risultati stress test, sensitivity e (se disponibili) analisi aggregate.

Comando base:

```bash
python generate_report_plots.py
```

Comando con parametri:

```bash
python generate_report_plots.py --output ../exp/analysis_report_plots --operational-threshold 1000
```

Output principali:
- heatmap di operativita solver
- curve throughput/runtime vs k
- grafici Pareto
- confronto successo nominale vs operativo
- grafici transizione di regime
- sensitivity heatmap e rischio deadlock
- `README_PLOTS.md` (guida lettura grafici)

## Ordine Consigliato Di Esecuzione
1. `analyze_grid_graphs.py`
2. `analyze_conflict_profile.py`
3. `analyze_bottleneck.py`
4. `analyze_normalized_metrics.py`
5. `generate_report_plots.py`

## Output Generati
In generale gli output vengono salvati in sottocartelle di `../exp/`.

Cartelle piu comuni:
- `../exp/analysis_conflicts/`
- `../exp/analysis_bottleneck/`
- `../exp/analysis_normalized/`
- `../exp/analysis_report_plots/`

## Troubleshooting
- ImportError su librerie Python:
  - eseguire `pip install -r ../requirements.txt` dalla cartella `analyzer_and_report`.
- Nessun dato trovato:
  - verificare che in `../exp` esistano i file `solver.csv` e `paths.txt` attesi dagli script.
- Errore file mappa non trovato:
  - controllare il path passato con `--map` oppure aggiornare i path predefiniti nelle costanti dello script.
- Grafici report mancanti:
  - `generate_report_plots.py` produce alcuni grafici solo se trova i CSV di input richiesti.
