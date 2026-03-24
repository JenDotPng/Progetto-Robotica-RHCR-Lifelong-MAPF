# NOTICE

Questo repository include e deriva dal framework RHCR (Lifelong MAPF) sviluppato da The University of Southern California (USC).

## 1. Licenza del codice RHCR originale
Il codice RHCR originale resta soggetto ai termini riportati in [license.md](license.md).

## 2. Uso nel presente progetto
L'utilizzo di RHCR in questo repository e finalizzato a scopi didattici e di ricerca accademica non-profit, in coerenza con i termini di licenza USC.

## 3. Componenti custom implementate nel progetto
Nel repository sono state sviluppate componenti aggiuntive rispetto al codice RHCR originale, tra cui:

- pipeline sperimentale Python in root:
  - [final_stress_test.py](final_stress_test.py)
  - [warehouse_final_stress_test.py](warehouse_final_stress_test.py)
  - [sweep_sensitivity.py](sweep_sensitivity.py)
- strumenti di analisi in [analyzer_and_report/](analyzer_and_report/):
  - [analyzer_and_report/analyze_bottleneck.py](analyzer_and_report/analyze_bottleneck.py)
  - [analyzer_and_report/analyze_conflict_profile.py](analyzer_and_report/analyze_conflict_profile.py)
  - [analyzer_and_report/analyze_grid_graphs.py](analyzer_and_report/analyze_grid_graphs.py)
  - [analyzer_and_report/analyze_normalized_metrics.py](analyzer_and_report/analyze_normalized_metrics.py)
  - [analyzer_and_report/generate_report_plots.py](analyzer_and_report/generate_report_plots.py)
- utility mappe in [maps/map_to_grid.py](maps/map_to_grid.py)
- documentazione tecnica in [docs/](docs/)
- toolkit di visualizzazione in [visualizer/](visualizer/) (con perimetro licenza dedicato in [visualizer/LICENSE](visualizer/LICENSE) e [visualizer/NOTICE.md](visualizer/NOTICE.md))

## 4. Nota legale
Le componenti custom non rimuovono ne sostituiscono i termini applicabili al codice RHCR originale.
Per eventuale uso commerciale del codice RHCR, fare riferimento alle indicazioni presenti in [license.md](license.md).
