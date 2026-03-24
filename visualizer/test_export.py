#!/usr/bin/env python3
"""
Test script per verificare la funzionalità di esportazione dei dati dell'esperimento in formato JSON. 
Questo script carica un esperimento esistente, lo esporta in JSON e verifica la struttura dei dati esportati. Assicurati di avere un esperimento valido nella cartella specificata prima di eseguire questo test.
"""

import sys
import json
from pathlib import Path

# Add utils to path
sys.path.append(str(Path(__file__).parent))
from utils.data_loader import load_experiment
from visualize_experiment import export_experiment_to_json

# Test with the same experiment
exp_folder = Path(__file__).parent.parent / "exp" / "AGENTS_TEST" / "movingAI_warehouse" / "PBS_k120"  # Cambia questo percorso se necessario

print(f"Testing export from: {exp_folder}")
print(f"Folder exists: {exp_folder.exists()}")

if not exp_folder.exists():
    print("ERROR: Experiment folder not found!")
    sys.exit(1)

try:
    # Load experiment
    print("\n1. Loading experiment...")
    exp_data = load_experiment(str(exp_folder))
    print(f"   ✓ Loaded: {len(exp_data.paths)} agents")
    print(f"   ✓ Grid: {exp_data.grid.width} × {exp_data.grid.height}")
    print(f"   ✓ Config keys: {list(exp_data.config.keys())}")
    print(f"   ✓ Solver: {exp_data.config.get('solver', 'Unknown')}")
    
    # Export to JSON
    print("\n2. Exporting to JSON...")
    output_file = Path(__file__).parent / "test_export_data.json"
    export_experiment_to_json(exp_data, str(output_file))
    print(f"   ✓ Exported to: {output_file}")
    
    # Verify JSON structure
    print("\n3. Verifying JSON structure...")
    with open(output_file, 'r') as f:
        data = json.load(f)
    
    print(f"   ✓ Top-level keys: {list(data.keys())}")
    print(f"   ✓ Config: {list(data['config'].keys())}")
    print(f"   ✓ Grid keys: {list(data['grid'].keys())}")
    print(f"   ✓ Grid obstacles: {len(data['grid']['obstacles'])} obstacles")
    print(f"   ✓ Paths: {len(data['paths'])} agent paths")
    print(f"   ✓ Metrics keys: {list(data['metrics'].keys())}")
    print(f"   ✓ Heatmap shape: {len(data['heatmap'])}×{len(data['heatmap'][0]) if data['heatmap'] else 0}")
    
    
    # Check first path structure
    if data['paths']:
        print(f"\n4. Sample path structure (agent 0):")
        first_state = data['paths'][0][0]
        print(f"   ✓ State keys: {list(first_state.keys())}")
        print(f"   ✓ Sample state: {first_state}")
    
    # Aggiungi dopo il punto 4 nel tuo script:
    if data['paths'] and data['grid']['obstacles']:
        print("\n5. Deep Collision Check:")
        # Crea un set di tuple (x,y) degli ostacoli per ricerca veloce
        obs_coords = {(o['x'], o['y']) for o in data['grid']['obstacles']}
        
        # Controlla la posizione iniziale di ogni agente
        collisions = 0
        for i, path in enumerate(data['paths']):
            start = path[0]
            if (start['x'], start['y']) in obs_coords:
                print(f"ERRORE: Agente {i} inizia su un ostacolo a ({start['x']}, {start['y']})")
                collisions += 1
        
        if collisions == 0:
            print("Successo: Nessun agente parte sopra un ostacolo nei dati JSON.")
        else:
            print(f"Fallimento: {collisions} agenti iniziano sopra ostacoli.")

    print("\nAll checks passed!")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
