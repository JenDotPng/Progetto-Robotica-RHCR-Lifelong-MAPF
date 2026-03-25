# Analisi e Validazione Sperimentale del Framework RHCR (Rolling-Horizon Collision Resolution) per il Lifelong MAPF

## Indice
1. [Autori](#autori)
2. [Abstract](#abstract)
3. [Contesto e Motivazione](#contesto-e-motivazione)
4. [Obiettivi del Progetto](#obiettivi-del-progetto)
5. [Contributi Originali di Questa Estensione](#contributi-originali-di-questa-estensione)
6. [Architettura Complessiva](#architettura-complessiva)
7. [Mappe e Documentazione Dedicata](#mappe-e-documentazione-dedicata)
8. [Workflow Sperimentale (Metodologia)](#workflow-sperimentale-metodologia)
9. [Riproducibilita: Build ed Esecuzione](#riproducibilita-build-ed-esecuzione)
10. [Struttura del Repository](#struttura-del-repository)
11. [Licenza](#licenza)
12. [Repository Originale e Riferimenti](#repository-originale-e-riferimenti)

## Autori
- Piangatelli Jennifer
- Pavlovic Mattia

Studenti del corso di Robotica, Università degli Studi Brescia, Italia.

## Abstract
Questo repository estende il framework RHCR per il Lifelong MAPF con una pipeline sperimentale completa orientata alla valutazione metodologica in scenari di magazzino. Il lavoro integra simulazione C++, orchestrazione di campagne sperimentali, analisi quantitativa e strumenti di visualizzazione avanzata.

L'obiettivo del progetto non e solo eseguire benchmark, ma costruire un'infrastruttura replicabile per studiare in modo sistematico l'interazione tra algoritmo, parametri di rolling horizon e topologia della mappa.

## Contesto e Motivazione
Nel Lifelong MAPF gli agenti ricevono task in modo continuo e devono coordinarsi evitando collisioni nel tempo. RHCR affronta il problema tramite pianificazione a finestre mobili: ogni `h` timestep viene rilanciato il solver e viene garantita la collision-freedom su una finestra di ampiezza `w`, con vincolo tipico `w >= h`.

In contesti logistici realistici, la scelta di solver e parametri non puo essere disaccoppiata dalla struttura del grafo di navigazione. Per questo il progetto adotta una prospettiva map-centrica e data-driven.

## Obiettivi del Progetto
- Definire una metodologia riproducibile per il confronto tra solver MAPF in regime lifelong.
- Analizzare il ruolo dei parametri RHCR (`w`, `h`) in relazione alla mappa.
- Supportare l'identificazione di colli di bottiglia strutturali e zone critiche di conflitto.
- Fornire strumenti software per analisi, visualizzazione e reporting tecnico-scientifico.

## Contributi Originali di Questa Estensione
Le sezioni seguenti rappresentano contributi implementati ex novo in questo repository e non presenti nel codice RHCR originale.

### Visualizer web e toolkit di confronto
- Modulo dedicato in [visualizer/](visualizer/)
- Documentazione specifica in [visualizer/README.md](visualizer/README.md)

### Script di analisi e post-processing
- [analyzer_and_report/analyze_bottleneck.py](analyzer_and_report/analyze_bottleneck.py)
- [analyzer_and_report/analyze_conflict_profile.py](analyzer_and_report/analyze_conflict_profile.py)
- [analyzer_and_report/analyze_grid_graphs.py](analyzer_and_report/analyze_grid_graphs.py)
- [analyzer_and_report/analyze_normalized_metrics.py](analyzer_and_report/analyze_normalized_metrics.py)
- [analyzer_and_report/generate_report_plots.py](analyzer_and_report/generate_report_plots.py)
- [maps/map_to_grid.py](maps/map_to_grid.py) - conversione mappe da formato MovingAI (.map) a formato RHCR (.grid)

### Script di orchestrazione campagne sperimentali
- [final_stress_test.py](final_stress_test.py)
- [warehouse_final_stress_test.py](warehouse_final_stress_test.py)
- [sweep_sensitivity.py](sweep_sensitivity.py).

## Architettura Complessiva
### Core simulativo C++
Il nucleo computazionale rimane l'eseguibile `lifelong`, compilato dai moduli in `src/` e `inc/`.

Entry point:
- [src/driver.cpp](src/driver.cpp)

Layer principali:
- Graph layer: `BasicGraph`, `SortingGraph`, `KivaGraph`, `OnlineGraph`, `BeeGraph`
- System layer: `BasicSystem`, `SortingSystem`, `KivaSystem`, `OnlineSystem`, `BeeSystem`
- Solver layer: `PBS`, `ECBS`, `WHCA`, `LRA` con possibile wrapper `ID`
- Planner single-agent: `SIPP`, `State-Time A*`

### Pipeline Python
La pipeline Python e organizzata in due livelli:

- script in root per orchestrazione campagne (stress test e sensitivity sweep);
- script in `analyzer_and_report/` per analisi quantitativa, confronto e generazione grafici.

Gli output prodotti includono tipicamente `solver.csv`, `tasks.txt`, `paths.txt` e report aggregati in `exp/`.

## Mappe e Documentazione Dedicata
Mappe principali:
- [maps/sorting_map.grid](maps/sorting_map.grid)
- [maps/warehouse_map.grid](maps/warehouse_map.grid)
- [maps/warehouse_optimized.grid](maps/warehouse_optimized.grid)

Documentazione tecnica esistente da consultare:
- [docs/MAPS_ANALYSIS.md](docs/MAPS_ANALYSIS.md)
- [docs/SORTING_MAP.md](docs/SORTING_MAP.md)
- [docs/WAREHOUSE_MAP.md](docs/WAREHOUSE_MAP.md)
- [docs/REPORT.md](docs/REPORT.md)

## Workflow Sperimentale (Metodologia)
Il workflow adottato nel repository segue una pipeline riproducibile in quattro fasi:

1. Preprocessing e validazione mappe:
	- conversione con [maps/map_to_grid.py](maps/map_to_grid.py);
	- analisi topologica con [analyzer_and_report/analyze_grid_graphs.py](analyzer_and_report/analyze_grid_graphs.py).
2. Esecuzione campagne sperimentali:
	- stress test con [final_stress_test.py](final_stress_test.py) e [warehouse_final_stress_test.py](warehouse_final_stress_test.py);
	- sweep parametrico con [sweep_sensitivity.py](sweep_sensitivity.py).
3. Analisi post-run:
	- conflitti, metriche normalizzate e bottleneck con gli script in [analyzer_and_report/](analyzer_and_report/);
	- guida completa (ordine consigliato, output attesi e troubleshooting) in [analyzer_and_report/README.md](analyzer_and_report/README.md).
4. Reporting e visualizzazione:
	- report tecnico in [docs/REPORT.md](docs/REPORT.md);
	- analisi map-centric in [docs/MAPS_ANALYSIS.md](docs/MAPS_ANALYSIS.md), [docs/SORTING_MAP.md](docs/SORTING_MAP.md), [docs/WAREHOUSE_MAP.md](docs/WAREHOUSE_MAP.md);
	- ispezione qualitativa run con toolkit web in [visualizer/](visualizer/) (dettagli in [visualizer/README.md](visualizer/README.md)).

## Riproducibilità: Build ed Esecuzione
### Requisiti
- CMake >= 3.12
- Compilatore C++11
- Boost (`program_options`, `filesystem`)
- Python 3.10+

### Setup dipendenze Python
Installare le dipendenze Python dalla root del repository:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Nota:
- `requirements.txt` (root) copre script di orchestrazione, analyzer e visualizer;
- `visualizer/requirements.txt` rimane disponibile come set minimale solo per il modulo web.

### Dipendenza C++ esterna: Boost
Il codice richiede la libreria esterna BOOST (https://www.boost.org/).


### Build (Windows, MSVC)
```powershell
cmake -S . -B build -A x64
cmake --build build --config Release
```

Eseguibile atteso:
- `build/Release/lifelong.exe`

### Build (Linux/macOS)
```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

Eseguibile atteso:
- `build/lifelong`

### Esecuzione rapida
Windows (PowerShell):

```powershell
.\build\Release\lifelong.exe -m maps/sorting_map.grid -k 100 --scenario SORTING --simulation_window 5 --planning_window 10 --solver PBS --seed 0
```

Linux/macOS:

```bash
./build/lifelong -m maps/sorting_map.grid -k 100 --scenario SORTING --simulation_window 5 --planning_window 10 --solver PBS --seed 0
```

Output minimo atteso nella cartella di output (`--output`, default `../exp/test`):
- `solver.csv`
- `tasks.txt`
- `paths.txt`

### Esecuzione pipeline sperimentale
Esempi dalla root del repository:

```bash
# Stress test su sorting map
python final_stress_test.py

# Stress test su warehouse optimized
python warehouse_final_stress_test.py

# Sensitivity sweep (w, h)
python sweep_sensitivity.py
```

Analisi e report (modulo dedicato):
- riferimento principale: [analyzer_and_report/README.md](analyzer_and_report/README.md)
- eseguire preferibilmente dalla cartella [analyzer_and_report/](analyzer_and_report/) per coerenza dei path relativi

```bash
cd analyzer_and_report

# Analisi mappe come grafi
python analyze_grid_graphs.py

# Profilo conflitti/ripianificazioni
python analyze_conflict_profile.py

# Analisi bottleneck strutturale
python analyze_bottleneck.py

# Metriche normalizzate
python analyze_normalized_metrics.py

# Generazione grafici finali per report
python generate_report_plots.py
```

Visualizer (modulo dedicato):
- riferimento principale: [visualizer/README.md](visualizer/README.md)
- eseguire preferibilmente dalla cartella [visualizer/](visualizer/) per coerenza dei path relativi

```bash
cd visualizer

# Viewer interattivo su una run
python visualize_experiment.py "..\exp\<cartella_esperimento>"

```

### Troubleshooting rapido
- Errore Boost in configurazione CMake: verificare installazione locale e che `program_options` e `filesystem` siano disponibili.
- Eseguibile non trovato: controllare che la build sia `Release` e che il path usato negli script sia coerente con il sistema operativo.
- Errori Python su import: assicurarsi che `pip install -r requirements.txt` sia stato eseguito dalla root del repository.

## Struttura del Repository
```text
.
|- CMakeLists.txt
|- README.md
|- license.md
|- docs/                   # documentazione tecnica e report principali
|- analyzer_and_report/    # script di analisi quantitativa e plotting
|- src/                    # implementazione C++
|- inc/                    # header C++
|- maps/                   # mappe RHCR, utility conversione e output map-centric
|- exp/                    # output delle campagne sperimentali
|- visualizer/             # toolkit web di visualizzazione e confronto
|- final_stress_test.py
|- warehouse_final_stress_test.py
|- sweep_sensitivity.py
|- build/                  # output CMake locale (generato)
```

## Licenza
Il progetto deriva da RHCR e mantiene la licenza di ricerca USC del codice originale.

In questo repository, RHCR e stato utilizzato per finalita didattiche e di ricerca accademica non-profit; inoltre sono state implementate componenti custom (pipeline sperimentale, analisi, visualizzazione e documentazione tecnica) descritte in [NOTICE.md](NOTICE.md).

Per il modulo [visualizer/](visualizer/) e definito un perimetro licenza dedicato (MIT), documentato in [visualizer/LICENSE](visualizer/LICENSE) e [visualizer/NOTICE.md](visualizer/NOTICE.md).

Dettagli in [license.md](license.md).

## Repository Originale e Riferimenti
Codice sorgente RHCR originale:
- https://github.com/Jiaoyang-Li/RHCR

Riferimenti bibliografici:

[1] Jiaoyang Li, Andrew Tinka, Scott Kiesel, Joseph W. Durham, T. K. Satish Kumar and Sven Koenig. Lifelong Multi-Agent Path Finding in Large-Scale Warehouses. In Proceedings of the AAAI Conference on Artificial Intelligence (AAAI), 2021.
