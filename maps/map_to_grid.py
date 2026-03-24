"""
map_to_grid.py

Scopo
- Convertire mappe MovingAI (.map) nel formato RHCR (.grid) usato dal simulatore `lifelong`.

Funzionalita principali
- Parsing dell'header MovingAI (width, height, sezione map).
- Conversione cella-per-cella in tipi RHCR:
    - Obstacle per celle bloccate (@, T)
    - Induct sulla colonna x == 1
    - Eject sulla colonna x == width - 2
    - Travel su celle libere rimanenti
- Generazione dei pesi di transizione N/W/S/E con costo unitario (1) o inf se bloccato.
- Inserimento del costo WAIT (=1) per ogni nodo.

Input atteso
- File testuale .map in formato MovingAI, ad esempio:
    - type octile
    - height H
    - width W
    - map
    - griglia di H righe

Output atteso
- File .grid RHCR con:
    - intestazione "Grid size (x,y)"
    - riga dimensioni "W,H"
    - tabella CSV dei nodi con campi:
        id,type,station,x,y,weight_to_NORTH,weight_to_WEST,weight_to_SOUTH,weight_to_EAST,weight_for_WAIT

Esempio CLI
- python map_to_grid.py maps/input.map maps/output.grid

Nota
- Il file contiene due funzioni di conversione equivalenti (`convert_to_rhcr` e
    `convert_map_to_grid`) per retro-compatibilita con usi precedenti.
"""

import argparse

def convert_to_rhcr(input_map, output_grid):
    with open(input_map, 'r') as f:
        lines = f.readlines()

    # Parsing Header MovingAI
    height = int(lines[1].split()[1])
    width = int(lines[2].split()[1])
    map_rows = [row.rstrip('\n') for row in lines[4:]]

    def is_blocked(nx, ny):
        if nx < 0 or nx >= width or ny < 0 or ny >= height:
            return True
        return map_rows[ny][nx] in ['@', 'T']

    with open(output_grid, 'w') as f:
        f.write(f"Grid size (x,y)\n{width},{height}\n")
        f.write("id,type,station,x,y,weight_to_NORTH,weight_to_WEST,weight_to_SOUTH,weight_to_EAST,weight_for_WAIT\n")

        node_id = 0
        for y in range(height):
            for x in range(width):
                char = map_rows[y][x]

                # Logica di assegnazione tipo cella
                if char in ['@', 'T']:
                    cell_type = "Obstacle"
                    station = "None"
                else:
                    if x == 1 and char == '.':
                        cell_type = "Induct"
                        station = f"I{y}"
                    elif x == width - 2 and char == '.':
                        cell_type = "Eject"
                        station = f"E{y}"
                    else:
                        cell_type = "Travel"
                        station = "None"

                if cell_type == "Obstacle":
                    wN = wW = wS = wE = "inf"
                else:
                    wN = "1" if not is_blocked(x, y - 1) else "inf"
                    wW = "1" if not is_blocked(x - 1, y) else "inf"
                    wS = "1" if not is_blocked(x, y + 1) else "inf"
                    wE = "1" if not is_blocked(x + 1, y) else "inf"

                f.write(f"{node_id},{cell_type},{station},{x},{y},{wN},{wW},{wS},{wE},1\n")
                node_id += 1

def main():
    parser = argparse.ArgumentParser(description="Convert MovingAI .map to RHCR .grid")
    parser.add_argument("input_map", help="Path to input .map file")
    parser.add_argument("output_grid", help="Path to output .grid file")
    args = parser.parse_args()

    convert_to_rhcr(args.input_map, args.output_grid)


def convert_map_to_grid(input_filename, output_filename):
    with open(input_filename, 'r') as f:
        lines = f.readlines()

    # Parsing dell'header Moving AI
    # Tipicamente: type, height, width, map
    height = int(lines[1].split()[1])
    width = int(lines[2].split()[1])
    map_data = [line.rstrip('\n') for line in lines[4:]]

    def is_blocked(nx, ny):
        if nx < 0 or nx >= width or ny < 0 or ny >= height:
            return True
        return map_data[ny][nx] in ['@', 'T']

    with open(output_filename, 'w') as f:
        f.write("Grid size (x,y)\n")
        f.write(f"{width},{height}\n")
        f.write("id,type,station,x,y,weight_to_NORTH,weight_to_WEST,weight_to_SOUTH,weight_to_EAST,weight_for_WAIT\n")

        current_id = 0
        for y in range(height):
            for x in range(width):
                char = map_data[y][x]

                if char in ['@', 'T']:
                    cell_type = "Obstacle"
                    station = "None"
                else:
                    if x == 1 and char == '.':
                        cell_type = "Induct"
                        station = f"I{y}"
                    elif x == width - 2 and char == '.':
                        cell_type = "Eject"
                        station = f"E{y}"
                    else:
                        cell_type = "Travel"
                        station = "None"

                if cell_type == "Obstacle":
                    w_n = w_w = w_s = w_e = "inf"
                else:
                    w_n = "1" if not is_blocked(x, y - 1) else "inf"
                    w_w = "1" if not is_blocked(x - 1, y) else "inf"
                    w_s = "1" if not is_blocked(x, y + 1) else "inf"
                    w_e = "1" if not is_blocked(x + 1, y) else "inf"

                f.write(f"{current_id},{cell_type},{station},{x},{y},{w_n},{w_w},{w_s},{w_e},1\n")
                current_id += 1



if __name__ == "__main__":
    #main()
    # Utilizzo:
    convert_map_to_grid('warehouse-10-20-10-2-2.map', 'warehouse_map.grid')