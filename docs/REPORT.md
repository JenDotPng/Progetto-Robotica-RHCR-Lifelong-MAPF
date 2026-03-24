# Report sperimentale progetto MAPF

## Indice

- [1. Obiettivi del progetto](#1-obiettivi-del-progetto)
- [2. Architettura generale del sistema](#2-architettura-generale-del-sistema)
  - [2.1 Simulatore C++](#21-simulatore-c)
  - [2.2 Script Python principali (root)](#22-script-python-principali-root)
- [3. Mappe utilizzate e preprocessing](#3-mappe-utilizzate-e-preprocessing)
  - [3.1 Conversione mappe MovingAI → RHCR](#31-conversione-mappe-movingai--rhcr)
  - [3.2 Mappe finali](#32-mappe-finali)
  - [3.3 Analisi delle mappe come grafi](#33-analisi-delle-mappe-come-grafi)
  - [3.4 Considerazioni map-centriche (integrazione tecnica)](#34-considerazioni-map-centriche-integrazione-tecnica)
- [4. Workflow sperimentale](#4-workflow-sperimentale)
  - [4.0 Definizione del processo di analisi (workflow reale seguito)](#40-definizione-del-processo-di-analisi-workflow-reale-seguito)
  - [4.1 Stress test su sorting_map](#41-stress-test-su-sorting_map)
  - [4.2 Stress test su warehouse_optimized](#42-stress-test-su-warehouse_optimized)
  - [4.3 Sensitivity sweep dei parametri temporali (w, h)](#43-sensitivity-sweep-dei-parametri-temporali-w-h)
  - [4.4 Analisi del profilo conflitti e runtime per finestra](#44-analisi-del-profilo-conflitti-e-runtime-per-finestra)
  - [4.5 Metriche normalizzate per agente e per densità](#45-metriche-normalizzate-per-agente-e-per-densita)
  - [4.6 Analisi dei bottleneck strutturali con paths.txt](#46-analisi-dei-bottleneck-strutturali-con-pathstxt)
  - [4.7 Integrazione quantitativa dai CSV reali in exp/ (analisi per cartella)](#47-integrazione-quantitativa-dai-csv-reali-in-exp-analisi-per-cartella)
- [5. Sintesi complessiva e raccomandazioni](#5-sintesi-complessiva-e-raccomandazioni)
  - [5.1 Confronto tra mappe](#51-confronto-tra-mappe)
  - [5.2 Confronto tra solver](#52-confronto-tra-solver)
  - [5.3 Scelta dei parametri temporali (w, h)](#53-scelta-dei-parametri-temporali-w-h)
  - [5.4 Indicazioni per il layout della mappa](#54-indicazioni-per-il-layout-della-mappa)
  - [5.5 Raccomandazioni operative map-specifiche](#55-raccomandazioni-operative-map-specifiche)
  - [5.6 Ranking solver per mappa e fascia di densita](#56-ranking-solver-per-mappa-e-fascia-di-densita)
  - [5.7 Regole decisionali operative (pronte per tesi/deployment)](#57-regole-decisionali-operative-pronte-per-tesideployment)
- [6. Conclusione](#6-conclusione)

## 1. Obiettivi del progetto

Il progetto studia il comportamento di diversi algoritmi di Multi-Agent Path Finding (MAPF) in scenari di tipo **lifelong** su mappe di magazzino. Gli obiettivi principali sono:

- confrontare **PBS**, **ECBS** e **WHCA** in termini di:
  - **scalabilità computazionale** (runtime per finestra di pianificazione);
  - **throughput** (numero di finestre/task completati nel tempo di simulazione);
  - **robustezza** (success rate, fallimenti, timeout);
- analizzare l’impatto della **geometria della mappa** (corridoi stretti, posizionamento delle stazioni) rispetto alla sola densità di agenti;
- studiare la sensibilità alle **finestre temporali** di pianificazione e simulazione (`w` e `h`);
- identificare **bottleneck strutturali** nella mappa warehouse e suggerire micro-modifiche di layout;
- normalizzare le metriche per mettere a confronto mappe diverse in modo equo (per agente e per densità).

Tutta la pipeline combina un simulatore C++ (`lifelong`) con una batteria di script Python per lanciare gli esperimenti, aggregare i risultati e generare grafici e heatmap.

---

## 2. Architettura generale del sistema

### 2.1 Simulatore C++

Il cuore della simulazione è l’eseguibile **lifelong**, compilato a partire dal codice in `src/` e `inc/` (MAPF solvers, grafo della mappa, sistema di simulazione). Lo script principale C++ è [src/driver.cpp](src/driver.cpp), che espone la CLI usata da tutti gli script Python, con opzioni come:

- `-m <mappa>`: file `.grid` RHCR;
- `-k <k>`: numero di agenti;
- `--scenario SORTING`: scenario di sorting/warehouse;
- `--solver {PBS,ECBS,WHCA,...}`: scelta del solver;
- `--simulation_time T`: orizzonte temporale della simulazione;
- `--planning_window w`, `--simulation_window h` con vincolo $h \le w$;
- `--output <cartella>`: directory in cui vengono salvati `solver.csv`, `tasks.txt`, `paths.txt`, ecc.;
- altre opzioni (es. `--cutoffTime`, `--screen`, parametri ECBS).

Ogni run del simulatore produce file CSV strutturati che alimentano le analisi successive.

### 2.2 Script Python principali (root)

Gli script chiave nella root orchestrano gli esperimenti e le analisi:

- **Stress test su sorting_map**: [final_stress_test.py](final_stress_test.py)
- **Stress test su warehouse_optimized**: [warehouse_final_stress_test.py](warehouse_final_stress_test.py)
- **Sensitivity sweep temporale (w,h)**: [sweep_sensitivity.py](sweep_sensitivity.py)
- **Analisi bottleneck strutturali**: [analyze_bottleneck.py](analyze_bottleneck.py)
- **Profilo conflitti e runtime per finestra**: [analyze_conflict_profile.py](analyze_conflict_profile.py)
- **Analisi grafi di mappa**: [analyze_grid_graphs.py](analyze_grid_graphs.py)
- **Metriche normalizzate per agente/densità**: [analyze_normalized_metrics.py](analyze_normalized_metrics.py)
- **Conversione da MovingAI a RHCR**: [map_to_grid.py](map_to_grid.py)

Tutti si appoggiano su `pandas` e `matplotlib` (eventualmente `seaborn`) per caricare i dati e produrre grafici.

---

## 3. Mappe utilizzate e preprocessing

### 3.1 Conversione mappe MovingAI → RHCR

Lo script [map_to_grid.py](map_to_grid.py) converte file `.map` nel formato **MovingAI** in file `.grid` compatibili con il simulatore RHCR. Il flusso è:

1. Lettura dell’header MovingAI (dimensioni, griglia di caratteri).
2. Per ogni cella `(x, y)` viene assegnato:
   - `Obstacle` se la cella è bloccata (`@`, `T`);
   - `Induct` se è una cella libera in prossimità della colonna di ingresso (es. `x == 1`);
   - `Eject` se è una cella libera in prossimità della colonna di uscita (`x == width - 2`);
   - `Travel` altrimenti.
3. Per ogni cella non ostacolo sono settati i pesi degli archi verso N, S, E, W (peso 1 se la cella adiacente non è ostacolo, altrimenti `inf`) e un auto-arco `WAIT` con peso 1.

Questo step è stato usato per derivare la mappa RHCR `warehouse_map-10-20-10-2-2.grid` a partire da file MovingAI originali.

### 3.2 Mappe finali

Il progetto utilizza tre mappe principali in formato RHCR (directory `maps/`):

- **Warehouse (MovingAI)**: [maps/warehouse_map.grid](maps/warehouse_map.grid)
- **Warehouse ottimizzata**: [maps/warehouse_optimized.grid](maps/warehouse_optimized.grid)
- **Sorting map**: [maps/sorting_map.grid](maps/sorting_map.grid)

La mappa warehouse ottimizzata è una variante della warehouse MovingAI con layout migliorato pensata per ridurre colli di bottiglia strutturali.

Dal punto di vista dimensionale e operativo, le mappe non sono equivalenti:

- **sorting_map**: scala media (77 x 37), alta regolarità dei corridoi e molti endpoint; è un benchmark ottimo per calibrare solver e parametri RHCR in condizioni controllate.
- **warehouse_map (MovingAI)**: scala ampia (170 x 84), forte realismo logistico, alta interdipendenza dei flussi; è la mappa più severa per studiare congestione e propagazione dei conflitti.
- **warehouse_optimized**: stessa geometria fisica di base della warehouse, ma con direzionalità dei flussi più regolarizzata; è pensata per migliorare la stabilità ad alte densità senza semplificare eccessivamente lo scenario.

### 3.3 Analisi delle mappe come grafi

Lo script [analyze_grid_graphs.py](analyze_grid_graphs.py) legge ciascuna mappa `.grid` e costruisce un grafo diretto pesato con **NetworkX**:

- un nodo per ogni cella non ostacolo (`Travel`, `Induct`, `Eject`);
- archi direzionali per ogni movimento consentito (N, S, E, W) con peso finito;
- self-loop `WAIT` su ogni cella attraversabile.

Per ogni mappa vengono calcolate e stampate metriche sintetiche:

- numero di nodi e archi;
- grado medio;
- percentuale di ostacoli;
- numero di componenti fortemente connesse.

Inoltre genera per ciascuna mappa:

- una vista a griglia colorata (`*_grid.png`), che evidenzia ostacoli, corridoi di Travel e stazioni Induct/Eject;
- un grafo completo con frecce (`*_graph.png`);
- uno **zoom 15×15** centrato sulla mappa (`*_zoom.png`), utile per vedere direzionalità e vicinanza tra stazioni;
- un file **GraphML** (`*.graphml`) per elaborazioni esterne (es. Gephi).

Queste analisi mostrano qualitativamente che:

- la **sorting_map** è quasi una griglia regolare, con molti percorsi alternativi e nessun collo di bottiglia estremo;
- la **warehouse MovingAI** presenta corridoi lunghi e stretti, con poche alternative, favorendo la formazione di code;
- la **warehouse_optimized** riduce alcuni di questi problemi, pur mantenendo vincoli geometrici stringenti rispetto alla sorting_map.

### 3.4 Considerazioni map-centriche (integrazione tecnica)

Le evidenze combinate di [SORTING_MAP.md](SORTING_MAP.md), [WAREHOUSE_MAP.md](WAREHOUSE_MAP.md) e delle analisi in `exp/` suggeriscono una lettura map-centric precisa:

- In **sorting_map**, il throughput è relativamente poco sensibile al lookahead `w` in un ampio intervallo operativo, mentre il runtime cresce con `w`: questo conferma che in topologie regolari `w` agisce soprattutto sul costo computazionale.
- In **warehouse_map**, l'alta ramificazione locale produce molti percorsi alternativi ma anche numerosi punti di confluenza: al crescere di `k` aumenta la probabilità di conflitti a cascata (head-on, swap, spillback), con degrado rapido della stabilità.
- In **warehouse_optimized**, la riduzione della libertà laterale e la maggiore canalizzazione dei flussi abbassano i conflitti distruttivi agli incroci e migliorano la robustezza in alta densità, a costo di minore flessibilità nei regimi leggeri.
- Le due mappe warehouse sono quindi **complementari**:
  - `warehouse_map.grid` come stress test della resilienza in traffico caotico;
  - `warehouse_optimized.grid` come test di continuità operativa in condizioni vicine alla produzione.

Implicazione metodologica: la valutazione di un solver non dovrebbe mai basarsi su una sola mappa; la robustezza reale emerge dal confronto tra topologie con diversa struttura dei colli di bottiglia.

---

## 4. Workflow sperimentale

L’intero workflow sperimentale ruota attorno alla cartella `exp/`, che contiene:

- **stress test** su sorting e warehouse ottimizzata;
- **sensitivity sweep** sui parametri `w` e `h` per diversi valori di `k`;
- analisi derivate (bottleneck, conflitti, metriche normalizzate).

### 4.0 Definizione del processo di analisi (workflow reale seguito)

Questa sezione descrive in modo lineare il processo effettivamente adottato durante il lavoro sperimentale, separando chiaramente la fase di **workflow** dalla discussione analitica di dettaglio.

1. **Fase iniziale su scenario SORTING con sorting_map**
   - Punto di partenza: [maps/sorting_map.grid](maps/sorting_map.grid).
   - Obiettivo: capire la sensibilità delle prestazioni rispetto ai parametri RHCR (`w`, `h`) in una topologia più regolare e controllata.
   - Azioni svolte:
     - sensitivity sweep di `w` e `h`;
     - incremento progressivo del numero di agenti `k`;
     - confronto tra solver (PBS, ECBS, WHCA) su stabilità, runtime e throughput.
   - Esito metodologico: sorting_map è stata usata come benchmark di calibrazione per identificare regioni parametriche stabili e riconoscere i primi limiti di scalabilità dei solver.

2. **Trasferimento su warehouse_map da benchmark MovingAI**
   - Mappa introdotta: [maps/warehouse_map.grid](maps/warehouse_map.grid), derivata dal benchmark MovingAI.
   - Azioni svolte:
     - stress test su carichi crescenti;
     - sensitivity sweep su (`w`, `h`) in scenario SORTING.
   - Evidenza principale: la topologia warehouse “originale” introduce congestione strutturale più severa; molti solver diventano instabili o non operativi al crescere di `k`, e il regime affidabile resta limitato a carichi più bassi o finestre molto specifiche.

3. **Sviluppo della versione warehouse_optimized**
   - Nuova mappa: [maps/warehouse_optimized.grid](maps/warehouse_optimized.grid), progettata per mitigare i colli di bottiglia della warehouse originale.
   - Azioni svolte:
     - nuova sensitivity sweep per individuare finestre temporali opportune;
     - successivi stress test con incremento di agenti sulle finestre selezionate.
   - Esito: miglioramento netto della regione di stabilità (in particolare per ECBS), con possibilità di spingere `k` più in alto rispetto a warehouse_map, pur mantenendo limiti residui in alta densità.

4. **Consolidamento e analisi comparativa finale**
   - Integrazione dei risultati di:
     - sorting_map (benchmark e calibrazione);
     - warehouse_map (stress realistico severo);
     - warehouse_optimized (compromesso operativo più robusto).
   - Produzione di grafici, report aggregati e analisi map-centriche per distinguere:
     - limiti algoritmici del solver;
     - limiti topologici indotti dalla mappa.

#### 4.0.1 Lettura sintetica della situazione (mappe, limiti, solver)

- **sorting_map**
  - ambiente adatto a tuning e confronto controllato;
  - throughput relativamente stabile su ampie regioni di (`w`, `h`);
  - degradazione più graduale con `k`, utile per studiare differenze intrinseche tra solver.

- **warehouse_map (MovingAI)**
  - scenario più realistico ma topologicamente severo;
  - maggiore sensibilità a congestione, incroci critici e propagazione dei conflitti;
  - regione operativa stretta: diversi solver collassano o diventano poco produttivi già a carichi medi.

- **warehouse_optimized**
  - riduce i colli di bottiglia più penalizzanti della warehouse originale;
  - estende il range di carico gestibile e migliora la continuità operativa;
  - non elimina completamente i limiti ad alta densità, ma consente analisi e deployment più robusti.

#### 4.0.2 Risultato complessivo per solver (quadro operativo)

- **ECBS**: solver più solido nel passaggio a warehouse_optimized; mantiene il miglior compromesso tra stabilità e costo computazionale su carichi elevati.
- **PBS**: buone prestazioni e throughput competitivo in vari regimi, ma con segni di saturazione anticipata rispetto a ECBS nelle condizioni più estreme.
- **WHCA**: adatto solo in zone di carico contenuto o con tuning accurato; in ambienti warehouse congesti la produttività degrada rapidamente.

Questa “definizione del processo” rappresenta la narrativa ufficiale del workflow sperimentale: benchmark controllato su sorting_map, stress realistico su warehouse_map, redesign topologico con warehouse_optimized, quindi nuova validazione con sweep + stress test fino all'individuazione dei limiti di scala.

### 4.1 Stress test su sorting_map

**Script:** [final_stress_test.py](final_stress_test.py)

**Output principale:**

- [exp/stress_test_sorting_map/final_comparison/final_report_summary.csv](exp/stress_test_sorting_map/final_comparison/final_report_summary.csv)
- grafici `chart_runtime.png` e `chart_throughput.png` nella stessa cartella.

**Setup esperimento**

- Mappa: [maps/sorting_map.grid](maps/sorting_map.grid)
- Scenario: `SORTING`;
- Solvers: PBS, ECBS, WHCA;
- Numero di agenti `k`: da 100 fino a 1200 (con passi intermedi, inclusi 300, 400, 500, ...);
- Seed usato: 42;
- Tempo di simulazione: orizzonte della campagna `final_comparison` con timeout osservato a 240 s;
- Configurazioni solver-specifiche mantenute:
  - PBS: `h=5, w=5` (configurazione B);
  - ECBS: `h=5, w=10` (configurazione A, con `--suboptimal_bound 1.5` nella pipeline comparativa);
  - WHCA: `h=5, w=10`;
- Vincolo RHCR rispettato: $h \le w$.
- Per ogni run: pulizia delle **heuristics table** associate alla mappa per garantire coerenza tra esecuzioni.

**Metriche estratte**

Dai file di output (`final_report.csv`, `final_report_summary.csv`, con supporto di `solver.csv`/`tasks.txt` a seconda della pipeline) vengono ricavati:

- **Runtime medio per finestra** (colonna 0, in secondi);
- **Throughput**: metrica operativa ufficiale di produttività riportata nei report (task completati / produttività osservata nella campagna);
- **Status**: `Success` se throughput > 0 e runtime medio numericamente valido, altrimenti `Fail` o `Timeout`.

Queste metriche vengono aggregate nel file di riepilogo [final_report_summary.csv](exp/stress_test_sorting_map/final_comparison/final_report_summary.csv), che contiene, per ogni coppia (Solver, Agenti):

- `Runs`, `Success_Rate`;
- `Runtime_Mean`, `Runtime_Std`;
- `Throughput_Mean`, `Throughput_Std`.

**Risultati principali su sorting_map**

Analizzando [final_report_summary.csv](exp/stress_test_sorting_map/final_comparison/final_report_summary.csv) e [final_report.csv](exp/stress_test_sorting_map/final_comparison/final_report.csv) nel perimetro ufficiale `final_comparison`:

- **Quadro globale (12 livelli di carico, Runs=1 per punto)**
  - PBS: 10 Success, 2 Timeout;
  - ECBS: 9 Success, 3 Timeout;
  - WHCA: 8 Success, 3 Timeout, 1 Fail.
  - Success_Rate medio sui 12 livelli:
    - PBS: 0.833;
    - ECBS: 0.750;
    - WHCA: 0.667.

- **Fascia 100-300 (regime stabile)**
  - Tutti i solver sono operativi.
  - ECBS mantiene il miglior profilo runtime.
  - PBS è competitivo e, in vari punti della fascia, mostra throughput leggermente superiore.
  - WHCA funziona ma con costo computazionale più elevato.

- **Fascia 400-800 (transizione/pre-critica)**
  - PBS ed ECBS restano nel complesso stabili.
  - WHCA entra in crisi tra 400 e 600 (timeout) e poi mostra successi nominali a 700-800 con throughput molto basso e runtime vicino al limite.

- **Fascia 900-1200 (regime critico)**
  - `k=900`: PBS timeout, ECBS timeout, WHCA success nominale ma throughput non operativo.
  - `k=1000`: ECBS mantiene un punto molto forte (throughput alto), PBS timeout, WHCA throughput marginale.
  - `k=1100-1200`: PBS recupera successi ma in modalità degradata; ECBS non mantiene continuità su tutti i punti; WHCA resta non competitivo.

Questa lettura conferma che, su sorting_map ad alta densità, non basta il solo `Success_Rate`: serve un criterio congiunto basato su stato run, runtime e throughput reale.

I grafici `chart_runtime.png` e `chart_throughput.png` confermano visivamente queste tendenze: buona tenuta di PBS/ECBS in fascia nominale, forte instabilità nel regime critico e disallineamento di WHCA tra successo nominale e produttività effettiva.

#### 4.1.1 Analisi dedicata dello stress test sorting_map

Questa analisi usa direttamente:
- [exp/stress_test_sorting_map/final_comparison/final_report_summary.csv](exp/stress_test_sorting_map/final_comparison/final_report_summary.csv)
- [exp/stress_test_sorting_map/final_comparison/final_report.csv](exp/stress_test_sorting_map/final_comparison/final_report.csv)

e mette in evidenza cosa accade ai solver al crescere di `k`.

**PBS**
- Successi nominali: **10/12**;
- successi operativi (throughput > 1000): **10/12**;
- massimo throughput: **69358** a `k=800` con runtime **0.402 s**/finestra;
- in regime critico mostra due timeout (`k=900,1000`) ma poi recupera run valide a `k=1100,1200` (throughput **9898** e **13494**), con runtime molto piu alto (**~2.8-2.9 s**).

**ECBS**
- Successi nominali: **9/12**;
- successi operativi (throughput > 1000): **9/12**;
- massimo throughput: **62369** a `k=1000` con runtime **0.338 s**/finestra;
- fallisce a `k=900`, poi torna forte a `k=1000`, quindi fallisce ancora a `k=1100,1200`: comportamento non monotono vicino alla saturazione.

**WHCA**
- Successi nominali: **8/12**, ma successi operativi (throughput > 1000) solo **3/12**;
- massimo throughput utile: **27092** a `k=300` (runtime **0.162 s**);
- da `k>=700` prevalgono successi marginali con runtime a cutoff (**240 s**) e throughput quasi nullo (**1-9**), quindi stato `Success` spesso non corrisponde a prestazione operativa.

**Confronto diretto tra solver (lettura critica)**
- **Fase stabile (`k=100-300`)**: PBS e ECBS hanno throughput comparabile, ECBS e piu rapido in runtime; WHCA e piu lento ma ancora efficace.
- **Fase di transizione (`k=400-800`)**: PBS supera ECBS in throughput assoluto, ma paga un runtime crescente; WHCA collassa gia da `k=400` (timeout) e non recupera operativita reale.
- **Fase critica (`k=900-1200`)**: PBS ed ECBS alternano successi/fallimenti, segno di frontiera di scalabilita; WHCA resta fuori regime operativo nonostante alcuni `Success` nominali.

Conclusione specifica per lo stress test sorting_map:
- il miglior compromesso globale e tra **PBS** (throughput massimo e tenuta operativa piu ampia) ed **ECBS** (runtime piu contenuto quando converge);
- **WHCA** e competitivo solo in bassa densita, mentre in alta densita entra in una zona di saturazione con produttivita marginale.

---

### 4.2 Stress test su warehouse_optimized

**Script:** [warehouse_final_stress_test.py](warehouse_final_stress_test.py)

**Output principali (per singolo solver paragonato su k)**:

- WHCA (warehouse ottimizzata):
  - [exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report_summary.csv)
- ECBS:
  - [exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv)
- PBS:
  - [exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv)

**Setup esperimento**

- Mappa: [maps/warehouse_optimized.grid](maps/warehouse_optimized.grid)
- Scenario: `SORTING`;
- Numero di agenti `k`: da 100 a 1000, con passo 100;
- Tempo di simulazione: `simulation_time = 3000` (stress test prolungato);
- Cutoff di processo: `cutoffTime ≈ 240 s`, `PROCESS_TIMEOUT ≈ 300 s`;
- Finestre temporali (configurazione attuale per WHCA): `planning_window = 30`, `simulation_window = 5`;
- Pulizia della cache euristica dopo ogni run.

A differenza del caso sorting_map, qui il **throughput** per ogni combinazione viene calcolato da `tasks.txt` tramite la funzione `count_completed_tasks`:

- per ogni task si guarda il timestep di completamento e si conteggiano solo quelli con tempo > 0;
- il throughput corrisponde quindi a **numero di task completati** durante la simulazione, non solo a numero di finestre.

**Risultati per WHCA su warehouse_optimized**

Da [WHCA_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report_summary.csv):

- Per `k = 100, 200, 300`:
  - `Success_Rate = 1.0`;
  - Throughput_Mean cresce (≈ 1631 → 4887 task completati);
  - Runtime_Mean per finestra resta relativamente contenuto (0.05–0.39 s).
- Già qui, rispetto alla sorting_map, il **throughput assoluto** è più basso: la geometria della warehouse ottimizzata limita la capacità complessiva.
- Per `k ≥ 400`:
  - `Success_Rate = 0.0`, `Throughput_Mean = 0` per tutte le densità provate;
  - WHCA **non riesce a gestire** carichi oltre 300 agenti su questa mappa, con questi parametri temporali.

**Risultati per ECBS su warehouse_optimized**

Da [ECBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv):

- ECBS mantiene `Success_Rate = 1.0` per **tutti** i valori `k = 100…1000`.
- Il throughput medio cresce quasi linearmente da ~1639 a ~16039 task completati, mostrando una buona scalabilità nonostante la mappa più difficile.
- Il runtime medio per finestra aumenta gradualmente (da ~0.015 s a ~0.295 s), ma resta ampiamente sotto i limiti di timeout.
- ECBS si conferma quindi il solver **più robusto e scalabile** su warehouse_optimized.

**Risultati per PBS su warehouse_optimized**

Da [PBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv):

- PBS ha `Success_Rate = 1.0` fino a `k = 800` con throughput in crescita regolare.
- Per `k = 900` e `k = 1000` i run falliscono (`Success_Rate = 0.0`, throughput zero), sintomo di saturazione dell’algoritmo e/o della geometria.
- Nella regione stabile (100–800 agenti) il runtime è maggiore rispetto a ECBS, ma i throughput sono comparabili.

#### 4.2.1 Analisi dedicata stress test `warehouse_optimized` a finestre fisse (dati forniti)

Sorgenti usate per questa analisi:
- [exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv)
- [exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv)
- [exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report_summary.csv](exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report_summary.csv)
- [exp/stress_test_warehouse_optimized/ECBS_comparison_k_1100-1500/final_report_summary.csv](exp/stress_test_warehouse_optimized/ECBS_comparison_k_1100-1500/final_report_summary.csv)

Con finestre temporali fissate nella campagna, l’aumento progressivo di `k` mostra tre regimi molto netti:

1. **Regime stabile (k=100-300)**
  - tutti i solver convergono (`Success_Rate=1.0`);
  - throughput comparabile:
    - ECBS: 1639 -> 4899;
    - PBS: 1643 -> 4915;
    - WHCA: 1631 -> 4887;
  - WHCA ha runtime più alto già a `k=300` (0.388 s vs 0.062 PBS e 0.052 ECBS).

2. **Regime di separazione (k=400-800)**
  - **ECBS** resta sempre `Success` con throughput 6488 -> 12907 e runtime 0.093 -> 0.210 s;
  - **PBS** resta `Success` ma con costo crescente più rapido: runtime 0.102 -> 0.426 s;
  - **WHCA** collassa immediatamente (`Success_Rate=0` da `k=400` in poi, throughput zero).

3. **Regime critico (k>=900)**
  - **ECBS**: ancora operativo a `k=900` (14477) e `k=1000` (16039), con ulteriore successo a `k=1100` (17520, runtime 0.408 s);
  - **PBS**: timeout già a `k=900` e `k=1000`;
  - **WHCA**: già fuori regime da `k=400`.
  - Nell’estensione ECBS (`k=1200-1500`) compaiono timeout su tutti i punti: soglia pratica tra 1100 e 1200 agenti in questa configurazione.

**Confronto solver-to-solver sui dati osservati**
- **Robustezza**: ECBS (10/10 success su 100-1000) > PBS (8/10) >> WHCA (3/10).
- **Scalabilità**: ECBS è l’unico che estende operatività oltre 1000 agenti (fino a 1100 nella campagna allegata).
- **Throughput per agente (k=100-800)**: PBS e ECBS sono molto vicini (~16.13-16.43 task/agente), quindi la differenza principale non è la produttività unitaria.
- **Costo computazionale**: a parità di throughput/agente, PBS cresce più rapidamente nel runtime e perde stabilità prima; WHCA mostra un collasso precoce con finestre fisse.

Conclusione specifica dello stress test warehouse_optimized:
- con queste finestre fisse, **ECBS** è il solver più affidabile su carico crescente;
- **PBS** è competitivo nella fascia media ma satura prima in alta densità;
- **WHCA** è utilizzabile solo in bassa densità (`k<=300`) e non regge la crescita del carico.

**Confronto qualitativo sorting_map vs warehouse_optimized**

Confrontando i trend dei due stress test si osserva che:

- a parità di `k` e solver, il **throughput** su warehouse_optimized è nettamente inferiore rispetto a sorting_map;
- i runtime per finestra sono più alti su warehouse_optimized e crescono più rapidamente con `k`;
- la **soglia di densità massima gestibile** si abbassa: 
  - su sorting_map, PBS/ECBS sono stabili fino a ~700–800 agenti;
  - su warehouse_optimized, ECBS regge fino a 1000 agenti, ma WHCA collassa oltre ~300 e PBS oltre ~800.

Questo evidenzia come la **geometria del magazzino** (corridoi stretti, confluenza verso stazioni comuni) incida in modo pesante rispetto a una griglia “quasi ideale” come sorting_map.

---

### 4.3 Sensitivity sweep dei parametri temporali (w, h)

**Script:** [sweep_sensitivity.py](sweep_sensitivity.py)

**Output principali:**

- [exp/sensitivity_sweep_k50/sensitivity_summary.csv](exp/sensitivity_sweep_k50/sensitivity_summary.csv)
- [exp/sensitivity_sweep_k80/sensitivity_summary.csv](exp/sensitivity_sweep_k80/sensitivity_summary.csv)
- grafici `sensitivity_*.png`, `heatmap_*.png`, `heatmap_normalized_*.png` nelle corrispondenti cartelle.

**Setup esperimenti di sensitivity**

- Mappe:
  - `sorting`;
  - `warehouse` nei summary, corrispondente alla **warehouse_map MovingAI** (`warehouse_map.grid`).
- Solvers: PBS, ECBS, WHCA (LRA escluso perché fallisce sistematicamente su SORTING);
- Numero di agenti `k`: 50 e 80 (due campagne distinte);
- Seeds: insieme di seed (es. [42], o 3 seed per combinazione); `success_rate` in `sensitivity_summary.csv` riflette il numero di seed andati a buon fine;
- Parametri temporali:
  - `w ∈ {20, 40, 60}` (planning_window);
  - `h ∈ {3, 5, 8}` (simulation_window) con vincolo $h \le w$;
- Tempo di simulazione e cutoff gestiti tramite argomenti CLI (`--time`, `--cutoff`).

Nel perimetro ufficiale usato in questo report, i file [exp/sensitivity_sweep_k50/sensitivity_summary.csv](exp/sensitivity_sweep_k50/sensitivity_summary.csv) e [exp/sensitivity_sweep_k80/sensitivity_summary.csv](exp/sensitivity_sweep_k80/sensitivity_summary.csv) sono la sorgente primaria per il confronto `sorting` vs `warehouse_map`.

Per ogni tripletta (`map`, `solver`, `w`, `h`) si raccolgono:

- `throughput`: numero medio di finestre pianificate;
- `runtime`: runtime medio per finestra;
- `avg_collisions`: numero medio di collisioni iniziali per finestra;
- `success_rate`: frazione di seed in cui la run è andata a buon fine.

#### 4.3.1 Sensitivity su sorting_map (k = 50, 80)

Dai file [sensitivity_sweep_k50/sensitivity_summary.csv](exp/sensitivity_sweep_k50/sensitivity_summary.csv) e [sensitivity_sweep_k80/sensitivity_summary.csv](exp/sensitivity_sweep_k80/sensitivity_summary.csv) si osserva che, per la mappa **sorting**:

- Per tutti i solver (PBS, ECBS, WHCA) e per tutte le combinazioni valide di `w` e `h`:
  - `success_rate = 1.0`;
  - il **throughput** dipende principalmente da `h` e non da `w`:
    - `h = 3` → `throughput ≈ 134` finestre;
    - `h = 5` → `throughput ≈ 80` finestre;
    - `h = 8` → `throughput ≈ 50` finestre.
- A parità di `h`, variare `w` (20 → 40 → 60) fa crescere
a gradualemente il **runtime medio** per finestra, ma non cambia il numero di finestre completate.

Interpretazione:

- su una mappa ben connessa come sorting_map, l’effetto di `w` è essenzialmente **computazionale** (più orizzonte di pianificazione → più tempo di calcolo), mentre non limita il throughput finché non si arriva a densità molto elevate;
- la scelta di `h` bilancia frequenza di ripianificazione e durata della simulazione: un `h` più piccolo aumenta il numero di finestre (più campioni, più overhead) ma ogni finestra è più breve.

#### 4.3.2 Sensitivity su warehouse_map MovingAI (WHCA)

Per la mappa **warehouse** (MovingAI, non la versione ottimizzata), i summary per WHCA in [exp/sensitivity_sweep_k50/sensitivity_summary.csv](exp/sensitivity_sweep_k50/sensitivity_summary.csv) e [exp/sensitivity_sweep_k80/sensitivity_summary.csv](exp/sensitivity_sweep_k80/sensitivity_summary.csv) mostrano un quadro molto diverso:

- I valori di **throughput** sono molto più bassi (es. 5–20 finestre contro 50–134 su sorting);
- I **runtime medi per finestra** sono elevati, spesso dell’ordine di decine di secondi, e tendono a saturare vicino al cutoff (≈ 120 s) per alcune combinazioni (ad es. `w = 60`, `h ∈ {3,5,8}` → `runtime ≈ 120 s`, `throughput ≈ 1`);
- `success_rate` è spesso < 1.0 per varie coppie (`w`, `h`), segno di instabilità o timeout.

Ciò suggerisce che, per WHCA su questa mappa:

- esiste una **zona “buona”** dei parametri (tipicamente `w ≈ 20–40`, `h` piccolo, 3–5) in cui il solver riesce a mantenere un throughput non nullo;
- valori troppo alti di `w` e/o `h` portano a collassi: poche finestre completate, runtime che raggiunge il cutoff e fallimenti parziali.

Le heatmap normalizzate (`heatmap_normalized_warehouse_*.png`) mostrano graficamente queste regioni: le celle con valori elevati di throughput normalizzato identificano combinazioni (w,h) favorevoli, mentre ampie regioni scure corrispondono a bassa efficienza e alta probabilità di congestione/timeout.

#### 4.3.3 Valori ufficiali warehouse_map (k=50 e k=80)

Nei due summary ufficiali di sensitivity su warehouse_map (solver WHCA):

- per `k=50` il throughput medio varia da ~20 (migliori configurazioni) fino a ~1 nelle configurazioni in saturazione;
- per `k=80` il throughput medio varia da ~18.5 fino a ~1 nelle configurazioni in saturazione;
- i runtime medi passano da ~61-83 s/finestra nelle zone operative fino a ~120 s/finestra nelle combinazioni critiche;
- il `success_rate` mostra variabilità tra 0.333 e 1.0 nelle configurazioni più difficili, confermando elevata sensibilità topologica e parametrica.

Questo allineamento numerico conferma il quadro ufficiale: su warehouse_map la finestra di stabilità di WHCA è stretta e dipende in modo forte da `(w,h)`.

#### 4.3.4 Analisi separata per mappa in base alle finestre scelte (dati forniti)

In questa sottosezione si usa esplicitamente il dettaglio dei file:
- [exp/sensitivity_sweep_k50/sensitivity_summary.csv](exp/sensitivity_sweep_k50/sensitivity_summary.csv)
- [exp/sensitivity_sweep_k50/sensitivity_raw.csv](exp/sensitivity_sweep_k50/sensitivity_raw.csv)
- [exp/sensitivity_sweep_k80/sensitivity_summary.csv](exp/sensitivity_sweep_k80/sensitivity_summary.csv)
- [exp/sensitivity_sweep_k80/sensitivity_raw.csv](exp/sensitivity_sweep_k80/sensitivity_raw.csv)

con focus su come cambiano le prestazioni al variare di `planning_window = w` e `simulation_window = h`.

**A) sorting_map (analisi separata)**

Per `k=50` e `k=80`, tutte le combinazioni (`w` in {20,40,60}, `h` in {3,5,8}) sono operative per PBS, ECBS e WHCA (`success_rate=1.0` in summary e solo status `success` nel raw).

Trend principali guidati da `h`:
- `h=3` -> throughput fisso **134** finestre;
- `h=5` -> throughput fisso **80**;
- `h=8` -> throughput fisso **50**.

Effetto di `w` a parita di `h` (costo computazionale), coerente su entrambi i carichi:
- **k=50, h=3**
  - ECBS: **0.082** (`w=20`) -> **0.149** (`w=40`) -> **0.213** (`w=60`);
  - WHCA: **0.041** -> **0.053** -> **0.057**;
  - PBS: **0.0181** -> **0.0194** -> **0.0191**.
- **k=80, h=3**
  - ECBS: **0.137** -> **0.251** -> **0.373**;
  - WHCA: **0.092** -> **0.119** -> **0.130**;
  - PBS: **0.0371** -> **0.0405** -> **0.0411**.

Lettura operativa su sorting_map:
- la scelta di `h` controlla la produttivita (numero di finestre);
- la scelta di `w` controlla soprattutto il costo di pianificazione;
- a parita di throughput, PBS e il piu economico in runtime, ECBS il piu sensibile all'aumento di `w`.

**B) warehouse_map (analisi separata)**

Nei dati `k=50` e `k=80`, il raw mostra una differenza strutturale importante tra solver:
- PBS: tutte le combinazioni marcate `disconnected_graph`;
- ECBS: tutte le combinazioni marcate `disconnected_graph`;
- WHCA: combinazioni eseguite, con mix di `success`/`timeout`.

Quindi, per warehouse_map in questo sweep, il confronto per finestre e di fatto analizzabile solo su WHCA.

Prestazioni WHCA per finestra (`k=50`):
- `w=20`: `h=3/5/8` -> throughput **13.67 / 8.33 / 5.67**, runtime **81.06 / 81.77 / 82.70**, success_rate **1.0 / 1.0 / 1.0**;
- `w=40`: `h=3/5/8` -> throughput **20.0 / 8.33 / 5.67**, runtime **61.61 / 81.78 / 82.71**, success_rate **0.667 / 1.0 / 1.0**;
- `w=60`: `h=3/5/8` -> throughput **1.0 / 1.0 / 1.0**, runtime **120.001 / 120.001 / 120.0005**, success_rate **0.667 / 0.333 / 0.667**.

Prestazioni WHCA per finestra (`k=80`):
- `w=20`: `h=3/5/8` -> throughput **18.5 / 11.5 / 5.33**, runtime **61.76 / 62.83 / 82.93**, success_rate **0.667 / 0.667 / 1.0**;
- `w=40`: `h=3/5/8` -> throughput **12.67 / 11.5 / 5.33**, runtime **81.21 / 62.87 / 82.95**, success_rate **1.0 / 0.667 / 1.0**;
- `w=60`: `h=3/5/8` -> throughput **1.0 / 1.0 / 1.0**, runtime **120.001 / 120.001 / 120.003**, success_rate **0.333 / 0.667 / 0.333**.

Lettura operativa su warehouse_map:
- `w=60` e una zona di collasso (runtime al cutoff, produttivita quasi nulla);
- le configurazioni con `h` piccolo (`h=3`) sono quelle con throughput piu alto;
- migliore configurazione a `k=50`: `w=40,h=3` (throughput 20.0, ma robustezza incompleta);
- migliore configurazione a `k=80`: `w=20,h=3` (throughput 18.5, robustezza incompleta);
- rispetto a sorting_map, la stessa griglia di finestre produce una perdita di produttivita di un ordine di grandezza.

Implicazione metodologica:
- la scelta di (`w`,`h`) va fatta separatamente per mappa;
- una configurazione valida su sorting_map non e trasferibile automaticamente a warehouse_map;
- nei casi con `disconnected_graph` sistematico (PBS/ECBS su warehouse in questo sweep), i dati indicano un problema di configurazione/istanza oltre alla sola scelta di finestra, da verificare prima di confronti prestazionali diretti.

---

### 4.4 Analisi del profilo conflitti e runtime per finestra

**Script:** [analyze_conflict_profile.py](analyze_conflict_profile.py)

**Output:**

- profili temporali `conflict_profile_k*.png` per diversi valori di `k`;
- grafico aggregato `conflict_aggregate.png`;
- tabella `conflict_summary.csv` in [exp/analysis_conflicts](exp/analysis_conflicts).

Lo script legge i `solver.csv` esistenti (da esperimenti standard o da sensitivity sweep) e per ogni `k`:

- ricava, per ciascuna finestra temporale:
  - runtime (colonna 0);
  - numero di collisioni iniziali (colonna 8);
- costruisce serie temporali per **collisioni** e **runtime**;
- applica una **media mobile** per smussare le curve e visualizzare la tendenza nel tempo.

Dall’aggregazione su più `k` e mappe si possono trarre alcune conclusioni qualitative (riassunte direttamente nei commenti dello script):

- se le **collisioni medie per finestra** crescono fortemente con `k`, la congestione è guidata dalla **densità di agenti**;
- se per lo stesso `k` la mappa warehouse mostra collisioni molto maggiori della sorting_map, allora il problema è **strutturale** (geometria, colli di bottiglia) e non solo di densità;
- picchi di runtime non accompagnati da picchi di collisioni indicano invece **sovraccarico del solver** (overhead computazionale) piuttosto che congestione geometrica.

I grafici aggregati mettono a confronto, per ogni solver, l’andamento di collisioni e runtime su **sorting** e **warehouse**, evidenziando come la warehouse generi più conflitti e tempi di pianificazione maggiori a parità di numero di agenti.

---

### 4.5 Metriche normalizzate per agente e per densità

**Script:** [analyze_normalized_metrics.py](analyze_normalized_metrics.py)

**Input principali:**

- esperimenti storici in:
  - [exp/sorting](exp/sorting)
  - [exp/movingAI_warehouse_final](exp/movingAI_warehouse_final)

Per ciascuna mappa lo script legge i relativi `solver.csv` (per PBS, ECBS, WHCA) e, dopo aver parsato le mappe con `parse_grid`, calcola:

- numero di celle totali e libere;
- percentuale di ostacoli.

Per ogni combinazione (mappa, solver, `k`) si derivano quindi le metriche:

- throughput assoluto;
- runtime medio per finestra (in ms);
- collisioni medie per finestra;
- **throughput per agente** (throughput / k);
- **runtime per agente** (runtime_ms / k);
- **densità** = k / (celle libere);
- **throughput per densità** = throughput / densità.

**Output e interpretazione**

Nella cartella [exp/analysis_normalized](exp/analysis_normalized) vengono generati:

- `normalized_metrics.csv`: raccolta completa dei dati normalizzati;
- grafici:
  - `fig1_absolute.png`: throughput e runtime assoluti vs `k`;
  - `fig2_per_agent.png`: throughput/agente e runtime/agente vs `k`;
  - `fig3_per_density.png`: throughput normalizzato per densità;
  - `fig4_whca_comparison.png`: confronto diretto di WHCA su sorting vs warehouse.

Il commento finale nello script guida la lettura:

- **fig1** mostra differenze assolute (influenzate sia da k che dalla geometria);
- **fig2** isola l’effetto dell’algoritmo (normalizzando per agente);
- **fig3** isola l’effetto della **geometria** (normalizzazione per densità di celle occupate);
- **fig4** mette a confronto diretto WHCA su warehouse e sorting, evidenziando il gap dovuto alla mappa.

In sintesi, anche dopo la normalizzazione per agente e per densità, la mappa warehouse continua a mostrare **prestazioni peggiori** rispetto a sorting_map: segnale che i limiti sono dovuti a colli di bottiglia strutturali nella topologia dei percorsi.

---

### 4.6 Analisi dei bottleneck strutturali con paths.txt

**Script:** [analyze_bottleneck.py](analyze_bottleneck.py)

**Input:**

- mappa: [maps/warehouse_map-10-20-10-2-2.grid](maps/warehouse_map-10-20-10-2-2.grid)
- esperimenti: run in [exp/movingAI_warehouse_final](exp/movingAI_warehouse_final) che contengono `paths.txt`.

**Funzionamento**

1. La classe `GridInfo` legge la mappa e costruisce:
   - dimensioni (x, y), numero di celle totali, ostacoli e libere;
   - mappatura `cellid → (x, y, type, station)`.
2. `parse_paths` legge ogni `paths.txt` (una riga per agente, con sequenze `cellid,orient,t`) e accumula una **heatmap di occupazione** (conteggio dei passaggi per cella).
3. `analyze_corridors` calcola, per ogni cella non ostacolo:
   - `occupancy` = numero di timestep-agente in cui la cella è occupata;
   - `flow_per_agent` = occupazione normalizzata per numero di agenti;
   - numero di ostacoli adiacenti (proxy di “strettezza del corridoio”);
   - una label `is_bottleneck` se la cella è di tipo `Travel` e ha occupazione sopra il **90° percentile** delle celle Travel.
4. `suggest_modifications` genera suggerimenti automatici di micro-modifica:
   - conversione di ostacoli adiacenti a celle Travel per allargare i corridoi;
   - eventuale rilocazione di stazioni (`Induct`, `Eject`) in zone meno congestionate.
5. Vengono generati, per ogni run e in forma aggregata:
   - heatmap di flusso con overlay dei bottleneck (`heatmap_*.png`);
   - istogrammi della distribuzione del flusso sulle celle Travel (`hist_*.png`);
   - CSV dei corridoi più congestionati (`corridors_*.csv`, `corridors_aggregated.csv`);
   - un report testuale `bottleneck_report.csv` con indicatori come `max_flow`, `mean_flow`, `pct_saturated`.

**Interpretazione delle immagini e degli istogrammi**

Le heatmap e gli istogrammi prodotti (alcuni dei quali sono stati condivisi come immagini esterne) mostrano tipicamente che:

- la distribuzione del flusso sulle celle Travel è **fortemente sbilanciata**:
  - la maggior parte delle celle ha occupazione bassa o nulla;
  - una piccola frazione di celle presenta occupazioni molto elevate (la “coda pesante” dell’istogramma), oltre la soglia del 90° percentile;
- queste celle ad alto flusso si concentrano in:
  - corridoi stretti che collegano grandi regioni del magazzino;
  - intersezioni vicino alle stazioni di Induct/Eject;
- il parametro `pct_saturated` (percentuale di celle Travel sopra il 90° percentile) è un indicatore della severità della congestione:
  - valori molto elevati indicano congestione **strutturale** (layout insufficiente), non solo dovuta a una cattiva scelta di parametri del solver.

Le immagini con istogramma del flusso mostrano una linea verticale rossa che marca la soglia di bottleneck (90° percentile). Le celle a destra di questa linea sono quelle da attenzionare per interventi di layout (allargamento corridoi, creazione di bypass, ridistribuzione delle stazioni).

---

### 4.7 Integrazione quantitativa dai CSV reali in `exp/` (analisi per cartella)

Questa sezione integra i risultati precedenti con una lettura **strettamente data-driven** dei CSV di riepilogo presenti nelle sottocartelle di `exp/` (solo file `*summary*.csv`, `final_report*.csv`, `conflict_summary.csv`).

#### 4.7.1 `exp/stress_test_sorting_map/final_comparison`

Sorgente: `final_report_summary.csv`.

**PBS**
- Successi: **10/12** livelli di carico (`Success_Rate` medio = 0.833);
- massimo `k` con run riuscita: **1200**;
- throughput massimo osservato: **69358** (a `k=800`);
- in coda alta (`k=1100,1200`) resta formalmente `Success`, ma con degradazione forte rispetto al picco: throughput **9898** e **13494**, runtime medio/finestra **2.93 s** e **2.78 s**.

**ECBS**
- Successi: **9/12** (`Success_Rate` medio = 0.750);
- massimo `k` con run riuscita: **1000**;
- throughput massimo osservato: **62369** (a `k=1000`);
- timeout/fallimento su `k=900,1100,1200`.

**WHCA**
- Successi nominali: **8/12** (`Success_Rate` medio = 0.667), ma con forte mismatch tra stato e produttività;
- soglia realmente operativa: **~300 agenti** (throughput robusto fino a `k=300`, poi collasso);
- a `k=700,800,900,1000,1200` compaiono run marcati come `Success` con throughput **2, 8, 1, 1, 9** e runtime ~**240 s** (saturazione al cutoff): successo nominale ma non operativo.

Lettura critica locale:
- su questa cartella, PBS ha la migliore tenuta nominale in termini di punti validi;
- ECBS è meno continuo nei punti estremi ma mantiene throughput alto fino a `k=1000`;
- WHCA conferma che `Success_Rate` da solo non basta: servono soglie di throughput minimo operativo.

#### 4.7.2 `exp/stress_test_warehouse_optimized/*_comparison_k_100-1000`

Sorgenti: `final_report_summary.csv` in ciascuna cartella solver.

**WHCA (`WHCA_comparison_k_100-1000`)**
- Successi: **3/10** (solo `k=100,200,300`);
- throughput: **1631, 3255, 4887** nelle tre run valide;
- da `k=400` in poi: `Success_Rate=0`, throughput zero.

**PBS (`PBS_comparison_k_100-1000`)**
- Successi: **8/10** (stabile fino a `k=800`);
- throughput massimo: **13052** (a `k=800`);
- runtime medio/finestra a `k=800`: **0.426 s**;
- fallimento a `k=900` e `k=1000`.

**ECBS (`ECBS_comparison_k_100-1000`)**
- Successi: **10/10** (stabile fino a `k=1000`);
- throughput massimo: **16039** (a `k=1000`);
- runtime medio/finestra a `k=1000`: **0.295 s**.

**Estensione ECBS (`ECBS_comparison_k_1100-1500`)**
- Successi: **1/5**;
- unico punto valido: `k=1100` con throughput **17520**, runtime **0.408 s**;
- da `k=1200` in poi: collasso.

Lettura critica locale:
- su warehouse_optimized la gerarchia è netta: **ECBS > PBS >> WHCA** in robustezza;
- confrontando ECBS e PBS nel range comune `k=100..800`, il throughput per agente è quasi uguale (~16.1-16.4 task/agente), ma il runtime PBS cresce molto più rapidamente (fino a oltre **+100%** rispetto a ECBS a `k=800`): PBS resta competitivo in produttività, ma paga un costo computazionale crescente.

#### 4.7.3 `exp/sensitivity_sweep_k50` e `exp/sensitivity_sweep_k80`

Sorgente: `sensitivity_summary.csv`.

**Sorting (tutti i solver, k=50 e k=80)**
- `success_rate = 1.0` per tutte le combinazioni (`w` in {20,40,60}, `h` in {3,5,8});
- throughput determinato quasi interamente da `h`: **134** (h=3), **80** (h=5), **50** (h=8), indipendente da `w`.

Range runtime osservati (k=80, mappa sorting):
- PBS: **0.037-0.055 s**/finestra;
- WHCA: **0.092-0.158 s**/finestra;
- ECBS: **0.137-0.405 s**/finestra.

**Warehouse (WHCA, k=50 e k=80)**
- forte sensibilità parametrica;
- migliori configurazioni trovate nei due sweep:
  - k=50: `w=40,h=3` con throughput **20.0**, runtime **61.606 s**, `success_rate=0.667`;
  - k=80: `w=20,h=3` con throughput **18.5**, runtime **61.759 s**, `success_rate=0.667`.
- regione critica: `w=60` (con `h=3,5,8`) porta throughput ~**1** e runtime ~**120 s** (cutoff), con `success_rate` tra **0.333** e **0.667`.

Lettura critica locale:
- su sorting, `w` è soprattutto costo computazionale;
- su warehouse, `w` e `h` diventano parametri di stabilità: la finestra utile è stretta e si restringe al crescere di `k`.

#### 4.7.4 `exp/sensitivity_sweep_k50/analysis_conflicts` e `exp/sensitivity_sweep_k80/analysis_conflicts`

Sorgente: `conflict_summary.csv`.

Per `k=50`:
- sorting: finestre valide **134** per tutti i solver;
- warehouse: finestre valide **39** (ECBS/PBS/WHCA).

Metriche warehouse (`k=50`):
- ECBS: `mean_coll` **0.170**, `mean_rt_ms` **707**;
- PBS: `mean_coll` **5.726**, `mean_rt_ms` **85**;
- WHCA: `mean_coll` **0.0**, `mean_rt_ms` **7815**.

Per `k=80`:
- sorting: finestre valide **134**;
- warehouse: finestre valide **36**.

Metriche warehouse (`k=80`):
- ECBS: `mean_coll` **0.378**, `mean_rt_ms` **1141**;
- PBS: `mean_coll` **17.431**, `mean_rt_ms` **171**;
- WHCA: `mean_coll` **0.0**, `mean_rt_ms` **8599**.

Lettura critica locale:
- i valori `mean_coll=0` di WHCA in warehouse non indicano traffico "pulito": sono coerenti con run quasi ferme/sature (runtime altissimo e poche finestre utili);
- PBS accetta molti più conflitti ma mantiene runtime basso;
- ECBS riduce i conflitti al costo di una pianificazione più pesante: comportamento coerente con robustezza migliore negli stress test su warehouse_optimized.

#### 4.7.5 Analisi critica trasversale (evidenze dai dati)

1. **La mappa domina il comportamento del solver.**
  La differenza tra sorting e warehouse è strutturale: passare da una topologia regolare a corridoi critici riduce drasticamente finestre utili e produttività, anche con tuning di `w,h`.

2. **`Success_Rate` va interpretato insieme a throughput e runtime.**
  Il caso WHCA su sorting ad alto `k` mostra successi nominali con throughput quasi nullo e runtime al cutoff; senza una soglia di produttività, il confronto è fuorviante.

3. **PBS vs ECBS: stesso output utile in regione media, costo diverso vicino alla saturazione.**
  In warehouse_optimized fino a `k=800` il throughput/agente è simile, ma il costo computazionale di PBS cresce molto più rapidamente; ECBS conserva margine in alta densità.

4. **WHCA è solver di nicchia in questi scenari.**
  Va bene in regimi leggeri e mappe favorevoli; su warehouse (anche ottimizzata) la finestra operativa è corta.

5. **Limite metodologico importante nei file di stress:** `Runs=1` per punto.
  I trend sono chiari, ma la significatività statistica resta limitata. Per consolidare conclusioni finali, è consigliabile ripetere i punti vicini alle soglie di collasso con più seed (almeno 5-10).

#### 4.7.6 Integrazione dati `exp/movingAI_warehouse` (campagna storica)

Sorgenti considerate:
- [exp/movingAI_warehouse/final_report.csv](exp/movingAI_warehouse/final_report.csv)
- [exp/movingAI_warehouse/README.md](exp/movingAI_warehouse/README.md)

La campagna storica su warehouse MovingAI (k in {20,50,80,100,120}) aggiunge un ulteriore stress test sintetico con 4 solver (PBS, ECBS, WHCA, LRA).

Risultati osservati da `final_report.csv`:
- **PBS**: successi **1/5** (solo `k=20`), throughput massimo **166** (a `k=20`), poi fallimento sistematico da `k=50` in avanti.
- **ECBS**: successi **2/5** (`k=20` e `k=50`), throughput massimo **166** (a `k=50`), fallimento da `k=80` in avanti.
- **WHCA**: successi **2/5** (`k=80` e `k=120`), throughput massimo **48** (a `k=80`), timeout a `k=20,50,100`.
- **LRA**: successi **0/5**, sempre `Fail`.

Lettura critica dei pattern:
- ECBS e PBS mostrano throughput alto quando convergono, ma la convergenza si interrompe presto all'aumentare di `k` (collasso netto su questa mappa).
- WHCA presenta il pattern opposto: throughput piu basso, ma alcuni punti ad alta densita (`k=80`, `k=120`) risultano eseguibili.
- Il comportamento non monotono di WHCA (successo a `k=120` ma timeout a `k=100`) suggerisce alta sensibilita a seed/istanza e parametri, quindi non va interpretato come curva regolare di scalabilita.

Confronto con il README della campagna:
- Il README descrive WHCA come solver indicato per carichi alti; i dati del `final_report.csv` sono coerenti solo in parte (esistono successi ad alta densita, ma con throughput contenuto e forte variabilita).
- Nel README compaiono affermazioni estese (es. scalabilita molto oltre i punti testati) che non sono direttamente dimostrate dal solo CSV disponibile, che copre fino a `k=120`.

Implicazione per il report complessivo:
- questa campagna storica conferma il quadro generale: su warehouse originale la robustezza dipende molto da solver+parametri+istanza;
- rafforza anche la scelta metodologica gia adottata nel resto del lavoro: valutare sempre insieme **stato run**, **throughput** e **runtime**, evitando conclusioni basate su un solo indicatore.

---

## 5. Sintesi complessiva e raccomandazioni

### 5.1 Confronto tra mappe

Dall’insieme degli esperimenti e delle analisi si deduce che:

- **sorting_map** rappresenta un caso “facile”: griglia regolare, molti percorsi alternativi, pochi colli di bottiglia;
  - tutti i solver mantengono alte performance e throughput elevato almeno fino a ~300 agenti;
  - anche con densità maggiori, PBS ed ECBS degradano gradualmente, mentre WHCA collassa prima.
- **warehouse MovingAI** è molto più difficile:
  - i sensitivity sweep mostrano throughput bassi e runtime vicini ai cutoff per molte combinazioni (w,h), specialmente per WHCA;
  - le analisi di conflitti e bottleneck evidenziano corridoi stretti e zone in cui il traffico viene instradato su pochissime celle ad alto flusso;
  - anche dopo normalizzazione per agente e densità, la mappa continua a risultare penalizzante.
- **warehouse_optimized** migliora la situazione, ma non annulla il problema:
  - ECBS scala bene fino a 1000 agenti con success rate 1.0 e throughput crescente;
  - PBS è stabile fino a ~800 agenti, poi fallisce;
  - WHCA non regge oltre ~300 agenti con i parametri considerati.

### 5.2 Confronto tra solver

Sulla base dei risultati degli stress test e delle analisi:

- **ECBS**
  - è il solver più **robusto e scalabile** su warehouse_optimized;
  - mantiene success rate pari a 1.0 su un ampio intervallo di `k`, con runtime moderato;
  - rappresenta una buona scelta per scenari ad **alta densità**.

- **PBS**
  - è competitivo in termini di throughput, ma con runtime per finestra generalmente maggiore di ECBS;
  - nella campagna ufficiale sorting `final_comparison` mostra tenuta complessiva molto buona (incluso recupero in parte della fascia alta), pur con degrado vicino alla saturazione;
  - su warehouse_optimized mostra limiti prima di ECBS ad altissime densità.

- **WHCA**
  - su sorting_map è accettabile a densità basse, ma degrada rapidamente oltre 300 agenti;
  - su warehouse (specialmente MovingAI) soffre molto la geometria: sensitivity sweep e stress test indicano throughput molto basso e frequenti timeout già per valori di `k` modesti;
  - è adatto solo per scenari con **densità contenuta** o mappe con geometria particolarmente favorevole.

### 5.3 Scelta dei parametri temporali (w, h)

Dai sensitivity sweep:

- su **sorting_map**, per k=50 e k=80:
  - ogni combinazione (w,h) valida porta a throughput pieno (nessuna perdita di finestre);
  - aumentare `w` aumenta il costo computazionale senza portare grandi benefici di throughput;
  - parametri ragionevoli sono `w` medio (40–60) e `h` piccolo (3–5), per bilanciare reattività e overhead.

- su **warehouse** (MovingAI), in particolare per WHCA:
  - la scelta di (w,h) è critica: valori troppo grandi portano subito a runtime vicini al cutoff e throughput ~0;
  - esiste una regione ristretta (tipicamente `w ≈ 20–40`, `h` piccolo) dove il solver riesce a mantenere una produttività non nulla;
  - al crescere di `k`, questa regione utile si restringe ulteriormente.

### 5.4 Indicazioni per il layout della mappa

L’analisi con [analyze_bottleneck.py](analyze_bottleneck.py) e le heatmap derivate da `paths.txt` suggeriscono che:

- pochi corridoi stretti e intersezioni chiave concentrano gran parte del traffico;
- spostare anche solo alcuni ostacoli adiacenti alle celle più congestionate (convertendoli in Travel) può aumentare significativamente la capacità del sistema;
- ridistribuire alcune stazioni `Induct`/`Eject` lontano dalle aree già sature contribuisce a bilanciare i flussi.

Operativamente, una pipeline ragionevole per progettare/ottimizzare layout e parametri è:

1. **Definizione della mappa** con [map_to_grid.py](map_to_grid.py) e verifica topologica con [analyze_grid_graphs.py](analyze_grid_graphs.py);
2. **Sensitivity sweep** su (w,h) con [sweep_sensitivity.py](sweep_sensitivity.py) per identificare combinazioni stabili a bassa densità;
3. **Stress test** progressivi al crescere di `k` su sorting_map e poi su warehouse_optimized con [final_stress_test.py](final_stress_test.py) e [warehouse_final_stress_test.py](warehouse_final_stress_test.py);
4. **Analisi conflitti** e **metriche normalizzate** per capire se i problemi derivano da densità, algoritmo o geometria ([analyze_conflict_profile.py](analyze_conflict_profile.py), [analyze_normalized_metrics.py](analyze_normalized_metrics.py));
5. **Analisi bottleneck strutturali** con [analyze_bottleneck.py](analyze_bottleneck.py) per decidere interventi mirati sul layout;
6. Iterare i passi 1–5 fino a raggiungere il compromesso desiderato tra throughput, runtime e robustezza.

### 5.5 Raccomandazioni operative map-specifiche

Alla luce dei risultati disponibili, una strategia pratica è:

1. **Fase di tuning iniziale su sorting_map**
  - Usare sorting_map per identificare rapidamente regioni stabili di `(w,h)` e filtrare configurazioni chiaramente inefficienti.
  - In questa fase privilegiare metriche di efficienza (runtime/finestra) e consistenza del throughput.

2. **Validazione di robustezza su warehouse_map**
  - Portare solo le migliori configurazioni su warehouse_map per misurare sensibilità reale alla congestione strutturale.
  - Verificare non solo lo stato Success, ma anche throughput minimo operativo e assenza di saturazione prolungata al cutoff.

3. **Scelta finale su warehouse_optimized**
  - Se l'obiettivo è produzione ad alta densità, considerare warehouse_optimized come mappa decisionale principale.
  - Scegliere il solver che mantiene il miglior compromesso tra throughput sostenuto e runtime stabile (nei dati correnti: ECBS).

4. **Aggiornamento layout guidato da bottleneck**
  - Applicare micro-modifiche solo sulle celle realmente critiche (percentili alti di occupazione), evitando cambiamenti globali non necessari.
  - Rieseguire un ciclo corto sensitivity + stress test per confermare il beneficio prima di consolidare la nuova mappa.

### 5.6 Ranking solver per mappa e fascia di densita

Il ranking seguente sintetizza i risultati numerici delle campagne principali (`final_report_summary.csv`, `sensitivity_summary.csv`, `conflict_summary.csv`) in forma operativa.

| Mappa | Fascia di densita | 1 posto | 2 posto | 3 posto | Evidenza quantitativa sintetica |
|---|---|---|---|---|---|
| sorting_map | bassa (k=100-300) | PBS | ECBS | WHCA | Tutti operativi; throughput al top della fascia: PBS 27546 (k=300), ECBS 26999, WHCA 27092 ma con runtime piu alto. |
| sorting_map | media (k=400-800) | PBS | ECBS | WHCA | PBS e ECBS stabili su tutti i punti; WHCA collassa a k=400-600 e torna nominalmente a k=700-800 con throughput 2-8. |
| sorting_map | alta (k=900-1200) | PBS | ECBS | WHCA | PBS: 2 fail (900,1000) ma recupera a 1100-1200; ECBS unico picco forte a k=1000 (62369) ma fail a 900/1100/1200; WHCA solo successi nominali con throughput marginale (1-9). |
| warehouse_map (MovingAI) | bassa-media (k=50-80, sweep) | ECBS | PBS | WHCA | WHCA: throughput 5-20 e runtime 61-120 s, success_rate anche 0.333-0.667; conflict summary: ECBS meno collisioni, PBS piu collisioni ma piu reattivo, WHCA quasi fermo. |
| warehouse_optimized | bassa-media (k=100-800) | ECBS | PBS | WHCA | ECBS 8/8 success nel range e runtime piu basso; PBS 8/8 success ma runtime cresce fino a +102.6% vs ECBS a k=800; WHCA success solo fino a 300. |
| warehouse_optimized | alta (k=900-1100) | ECBS | PBS | WHCA | ECBS regge 900-1000 e anche 1100 (estensione), PBS fallisce gia a 900-1000, WHCA gia collassato da 400. |
| warehouse_optimized | estrema (k=1200-1500) | ECBS (parziale) | - | - | Estensione ECBS: 1/5 success (solo k=1100), fallimento da 1200 in poi; nessun solver pienamente operativo. |

Nota di lettura:
- il ranking privilegia la robustezza operativa (successo + throughput non marginale), poi il runtime;
- nei casi di successo nominale con throughput quasi nullo, il solver non e considerato competitivo nella fascia.

### 5.7 Regole decisionali operative (pronte per tesi/deployment)

1. **Se la mappa e regolare (profilo tipo sorting_map) e il carico e fino a medio-alto (`k <= 800`)**
  - scegliere **PBS** quando l'obiettivo principale e massimizzare il throughput;
  - scegliere **ECBS** quando si vuole maggiore stabilita del runtime vicino alla saturazione.

2. **Se la mappa e congestionata/realistica (profilo warehouse)**
  - usare **ECBS** come default per robustezza;
  - usare **PBS** solo se accettabile una crescita marcata del costo computazionale in alta densita;
  - evitare **WHCA** oltre regimi leggeri o fuori dalla regione parametrica favorevole.

3. **Regola su `Success_Rate`**
  - considerare una run realmente valida solo se `Success_Rate > 0` **e** throughput sopra una soglia minima operativa (da fissare per il caso d'uso, ad esempio >1000 task nello stress sorting);
  - classificare come "successo nominale non operativo" le run al cutoff con throughput quasi nullo.

4. **Regola di tuning `w,h`**
  - su mappe facili: usare `h` per bilanciare reattivita/overhead e tenere `w` moderato (40-60) per contenere runtime;
  - su warehouse: evitare `w=60` come default per WHCA (zona spesso in saturazione), partire da `w=20-40` e `h=3-5`.

5. **Regola di validazione statistica**
  - vicino alle soglie di collasso (es. 800-1200 agenti), richiedere almeno 5-10 seed per punto prima di una decisione finale di solver/layout;
  - mantenere una metrica composita di confronto: robustezza (successi operativi), throughput medio, runtime p95.

---

## 6. Conclusione

Nel complesso, gli esperimenti documentati in `exp/` mostrano che:

- la **mappa** è il fattore dominante nella prestazione complessiva: anche con buoni solver, una warehouse con corridoi troppo stretti non può sostenere throughput paragonabili a una griglia aperta;
- tra i solver testati, **ECBS** fornisce il miglior compromesso tra robustezza e costo computazionale, specialmente su warehouse_optimized;
- nel benchmark sorting ufficiale `final_comparison`, **PBS ed ECBS** restano entrambi riferimenti validi ma con trade-off diversi (PBS più orientato al throughput, ECBS più efficiente in runtime);
- la scelta oculata delle **finestre temporali** (w,h) è cruciale solo su mappe difficili; su mappe “facili” come sorting_map è invece principalmente una questione di efficienza computazionale;
- le analisi post-hoc (heatmap, istogrammi di flusso, grafi e metriche normalizzate) sono fondamentali per passare da una semplice misurazione numerica a una vera **comprensione strutturale** del sistema e per guidare modifiche di layout concrete.

Questo report riassume il workflow, le configurazioni e i risultati più rilevanti; ulteriori dettagli numerici possono essere estratti direttamente dai CSV in `exp/` e dalle figure generate dagli script di analisi.
