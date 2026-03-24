#!/usr/bin/env python3
"""
MAPF Experiment Visualizer - Single Experiment Viewer

Scopo:
- visualizzare in modo interattivo un singolo esperimento MAPF;
- esportare i dati dell'esperimento in JSON;
- generare HTML standalone (con dati embedded) per condivisione offline;
- generare una pagina HTML con registrazione video lato browser (MediaRecorder).

Pipeline dati:
1) carica l'esperimento da cartella output (config, paths, tasks, solver stats);
2) calcola metriche aggregate e heatmap (congestion, conflict density, velocity);
3) serializza i dati in formato JSON compatibile con il viewer web;
4) avvia server Flask oppure esporta artefatti statici (HTML/JSON).

Modalita operative:
- Interactive server:
    avvia Flask e serve `viewer.html` + endpoint `/api/data`.
- Export JSON:
    salva il dataset elaborato in file JSON.
- Export standalone HTML:
    incorpora i dati direttamente nel template HTML (nessun server richiesto).
- Export video HTML:
    genera una pagina dedicata alla registrazione dell'animazione via MediaRecorder.

Input atteso:
- cartella esperimento contenente almeno `paths.txt`
    (piu file opzionali come `config.txt`, `tasks.txt`, `solver.csv`).

Output principali:
- `static/experiment_data.json` (nel caso server interattivo)
- `exports/json/<nomefile>.json` (`--export-json`)
- `exports/html/<nomefile>.html` (`--export-html`)
- `exports/video/<nomefile>.html` (`--export-video`)

Nota importante:
- per le opzioni di export, l'argomento FILE viene interpretato come nome file;
- il salvataggio avviene sempre nelle cartelle dedicate sotto `visualizer/exports/`.

Uso rapido:
- python visualize_experiment.py <exp_folder>
- python visualize_experiment.py <exp_folder> --export-html output.html   # -> exports/html/output.html
- python visualize_experiment.py <exp_folder> --export-json data.json     # -> exports/json/data.json
- python visualize_experiment.py <exp_folder> --export-video recorder.html # -> exports/video/recorder.html
"""

import argparse
import json
import sys
from pathlib import Path
import webbrowser
from flask import Flask, render_template, jsonify
import os
 
# Add utils to path
sys.path.append(str(Path(__file__).parent))
from utils.data_loader import load_experiment
from utils.metrics_calculator import (
    compute_metrics_summary,
    compute_congestion_heatmap,
    compute_conflict_density_heatmap,
    compute_velocity_heatmap,
)


def resolve_export_output_path(export_kind: str, requested_output: str) -> Path:
    """Resolve output path inside dedicated visualizer export folders.

    Export folders:
    - standalone HTML: visualizer/exports/html
    - JSON: visualizer/exports/json
    - video recorder HTML: visualizer/exports/video
    """
    export_dirs = {
        'html': 'html',
        'json': 'json',
        'video': 'video',
    }
    default_ext = {
        'html': '.html',
        'json': '.json',
        'video': '.html',
    }

    if export_kind not in export_dirs:
        raise ValueError(f"Unsupported export kind: {export_kind}")

    visualizer_root = Path(__file__).parent
    target_dir = visualizer_root / 'exports' / export_dirs[export_kind]
    target_dir.mkdir(parents=True, exist_ok=True)

    requested_name = Path(requested_output).name
    if not requested_name:
        requested_name = f"export{default_ext[export_kind]}"

    if Path(requested_name).suffix == '':
        requested_name += default_ext[export_kind]

    return target_dir / requested_name


def _json_default(obj):
    """Convert numpy/pandas types to JSON-serializable values."""
    # Numpy scalars
    if hasattr(obj, 'item'):
        try:
            return obj.item()
        except Exception:
            pass
    # Numpy arrays / pandas Series
    if hasattr(obj, 'tolist'):
        try:
            return obj.tolist()
        except Exception:
            pass
    # pandas Timestamp or datetime-like
    if hasattr(obj, 'isoformat'):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return str(obj)


def _attach_heatmaps(data: dict, exp_data):
    """Compute and attach all heatmaps used by the web viewer."""
    max_timestep = data.get('metrics', {}).get('max_timestep', 0)

    congestion = compute_congestion_heatmap(
        exp_data.paths,
        exp_data.grid,
        max_timestep
    ).tolist()
    conflicts = compute_conflict_density_heatmap(
        exp_data.paths,
        exp_data.grid,
        max_timestep
    ).tolist()
    velocity = compute_velocity_heatmap(
        exp_data.paths,
        exp_data.grid,
        max_timestep
    ).tolist()

    data.setdefault('metrics', {})['congestion_heatmap'] = congestion
    data['metrics']['conflict_heatmap'] = conflicts
    data['metrics']['velocity_heatmap'] = velocity

    # Backward compatibility for existing tools/tests.
    data['heatmap'] = congestion


def _build_viewer_data(exp_data):
    """Build the canonical data payload consumed by all viewer/export modes."""
    obstacles = [cell for cell in exp_data.grid.cells if cell['type'] == 'Obstacle']

    data = {
        'config': exp_data.config,
        'grid': {
            'width': exp_data.grid.width,
            'height': exp_data.grid.height,
            'cells': exp_data.grid.cells,
            'obstacles': obstacles,
        },
        'paths': [
            [
                {
                    'location': s.location,
                    'orientation': s.orientation,
                    'timestep': s.timestep,
                    'x': exp_data.grid.loc_to_xy(s.location)[0],
                    'y': exp_data.grid.loc_to_xy(s.location)[1],
                }
                for s in path
            ]
            for path in exp_data.paths
        ],
        'tasks': exp_data.tasks,
        'metrics': compute_metrics_summary(exp_data),
    }

    if exp_data.solver_stats is not None:
        data['solver_stats'] = exp_data.solver_stats.to_dict(orient='records')

    _attach_heatmaps(data, exp_data)
    return data


def export_experiment_to_json(exp_data, output_file):
    """Export experiment data to JSON format for web viewer."""
    data = _build_viewer_data(exp_data)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=_json_default)
    
    print(f"Exported data to {output_file}")
    return data


def start_viewer_server(exp_folder, port=5000, open_browser=True):
    """
    Start Flask server for interactive viewing.
    
    Args:
        exp_folder: Path to experiment folder
        port: Port number for server
        open_browser: Whether to open browser automatically
    """
    # Load experiment
    print(f"Loading experiment from {exp_folder}...")
    exp_data = load_experiment(exp_folder)
    
    # Create Flask app
    app = Flask(__name__,
                template_folder=str(Path(__file__).parent / 'templates'),
                static_folder=str(Path(__file__).parent / 'static'))
    
    # Export data to JSON
    data_file = Path(__file__).parent / 'static' / 'experiment_data.json'
    data_file.parent.mkdir(exist_ok=True)
    export_experiment_to_json(exp_data, str(data_file))
    
    @app.route('/')
    def index():
        """Serve the main viewer page."""
        return render_template('viewer.html')
    
    @app.route('/api/data')
    def get_data():
        """API endpoint to get experiment data."""
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    
    print(f"\n{'='*60}")
    print(f"[*] Starting Experiment Viewer")
    print(f"{'='*60}")
    print(f"  Experiment: {exp_data.name}")
    print(f"  Solver: {exp_data.config.get('solver', 'Unknown')}")
    print(f"  Agents: {len(exp_data.paths)}")
    print(f"  URL: http://localhost:{port}")
    print(f"{'='*60}\n")
    
    if open_browser:
        webbrowser.open(f'http://localhost:{port}')
    
    app.run(port=port, debug=False)


def export_static_html(exp_folder, output_file):
    """
    Export standalone HTML file with embedded data.
    
    Args:
        exp_folder: Path to experiment folder
        output_file: Output HTML file path
    """
    print(f"Loading experiment from {exp_folder}...")
    exp_data = load_experiment(exp_folder)
    
    data = _build_viewer_data(exp_data)
    
    # Read template and inline JS assets so the export works offline.
    visualizer_root = Path(__file__).parent
    template_file = visualizer_root / 'templates' / 'viewer.html'
    with open(template_file, 'r', encoding='utf-8') as f:
        html_template = f.read()

    viewer_js = (visualizer_root / 'static' / 'js' / 'viewer.js').read_text(encoding='utf-8')
    ui_js = (visualizer_root / 'static' / 'js' / 'ui.js').read_text(encoding='utf-8')

    html_template = html_template.replace(
        '<script src="/static/js/viewer.js"></script>',
        f'<script>\n{viewer_js}\n</script>'
    )
    html_template = html_template.replace(
        '<script src="/static/js/ui.js"></script>',
        f'<script>\n{ui_js}\n</script>'
    )
    
    # Inject data
    data_script = f"""
    <script>
        window.EXPERIMENT_DATA = {json.dumps(data, indent=2, default=_json_default)};
        console.log('Loaded experiment:', window.EXPERIMENT_DATA.config);
    </script>
    """
    
    # Insert before closing </body>
    html_output = html_template.replace('</body>', data_script + '</body>')
    
    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    print(f"Exported standalone HTML to {output_file}")
    print(f"Open it in a browser: file://{os.path.abspath(output_file)}")


def export_video_html(exp_folder, output_file):
    """
    Export HTML with integrated video recording capability (MediaRecorder API).
    Browser can record the animation directly to MP4/WebM.
    
    Args:
        exp_folder: Path to experiment folder
        output_file: Output HTML file path for video viewer
    """
    print(f"Loading experiment from {exp_folder}...")
    exp_data = load_experiment(exp_folder)

    data = _build_viewer_data(exp_data)
    viewer_js = (Path(__file__).parent / 'static' / 'js' / 'viewer.js').read_text(encoding='utf-8')
    
    # Create video recorder HTML template
    video_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visualizer - Experiment Video Recorder</title>
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; }}
        body {{ font-family: Arial, sans-serif; background: #222; color: #fff; overflow: hidden; }}
        .container {{ 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: flex-start;
            min-height: 100vh;
            height: 100vh;
            padding: 12px;
            gap: 8px;
            overflow: hidden;
        }}
        canvas {{ 
            border: 2px solid #444; 
            background: white;
            max-width: min(96vw, 1600px);
            max-height: 62vh;
            width: auto;
            height: auto;
            margin: 6px 0;
        }}
        .controls {{
            display: flex;
            gap: 10px;
            margin-top: 6px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        button {{ 
            padding: 10px 20px; 
            font-size: 14px; 
            cursor: pointer;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            transition: background 0.3s;
        }}
        button:hover {{ background: #45a049; }}
        button:disabled {{ background: #ccc; cursor: not-allowed; }}
        .info {{
            text-align: center;
            margin-top: 8px;
            font-size: 11px;
            color: #aaa;
            max-width: 900px;
            line-height: 1.35;
        }}
        .timestamp {{ margin-top: 15px; font-weight: bold; }}
        #status {{ color: #ffeb3b; margin-top: 10px; }}
        @media (max-height: 860px) {{
            h1 {{ font-size: 22px; }}
            canvas {{ max-height: 56vh; }}
            .info ol {{ display: none; }}
            .info p {{ margin: 4px 0; }}
        }}
        @media (max-height: 720px) {{
            h1 {{ font-size: 18px; }}
            canvas {{ max-height: 50vh; }}
            .info {{ display: none; }}
            .timestamp {{ margin-top: 4px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>VISUALIZER - Experiment Video Exporter</h1>
    <div id="expMeta">Map: N/A | Solver: N/A | Agents: 0 | w: N/A | h: N/A</div>
    <canvas id="mainCanvas"></canvas>
    
    <div class="controls">
        <button id="playBtn" onclick="startAnimation()">▶ Play</button>
        <button id="pauseBtn" onclick="pauseAnimation()" disabled>⏸ Pause</button>
        <button id="recordBtn" onclick="startRecording()" disabled>🔴 Record</button>
        <button id="stopRecordBtn" onclick="stopRecording()" disabled>⏹ Stop</button>
        <button id="downloadBtn" onclick="downloadVideo()" disabled>💾 Download</button>
    </div>
    
    <div class="timestamp" id="timestamp">0 / 0 ms</div>
    <div id="status"></div>
    
    <div class="info">
        <p><strong>Instructions:</strong></p>
        <ol style="text-align: left; display: inline-block;">
            <li>Click <strong>Play</strong> to start the animation</li>
            <li>During playback, click <strong>Record</strong> to capture video</li>
            <li>Click <strong>Stop</strong> when done</li>
            <li>Click <strong>Download</strong> to save as WebM (convert to MP4 with ffmpeg)</li>
        </ol>
        <p style="margin-top: 15px; font-size: 11px;">
            Conversion to MP4: <code>ffmpeg -i video.webm -c:v libx264 video.mp4</code>
        </p>
    </div>
</div>

<script>
    const EXPERIMENT_DATA = {json.dumps(data, indent=2, default=_json_default)};
    {viewer_js}

    const viewer = new ExperimentViewer('mainCanvas', EXPERIMENT_DATA);
    const cfg = EXPERIMENT_DATA.config || {{}};
    const rawMap = cfg.map || cfg.map_file || 'Unknown';
    const mapName = String(rawMap).split(/[\\\\/]/).pop() || 'Unknown';
    const solver = cfg.solver || 'Unknown';
    const numAgents = (EXPERIMENT_DATA.paths || []).length;
    const w = cfg.planning_window ?? cfg.window_size ?? cfg.w ?? 'N/A';
    const h = cfg.simulation_window ?? cfg.horizon ?? cfg.h ?? 'N/A';
    const expMeta = document.getElementById('expMeta');
    if (expMeta) {{
        expMeta.textContent = `Map: ${{mapName}} | Solver: ${{solver}} | Agents: ${{numAgents}} | w: ${{w}} | h: ${{h}}`;
    }}

    viewer.showTrails = true;
    viewer.showAgentIDs = true;
    viewer.showGrid = true;
    viewer.showPaths = false;
    viewer.setHeatmap(null);
    viewer.render();
    window.addEventListener('resize', () => viewer.onWindowResize());

    const canvas = viewer.canvas;
    const timestampEl = document.getElementById('timestamp');
    const statusEl = document.getElementById('status');
    const playBtn = document.getElementById('playBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const recordBtn = document.getElementById('recordBtn');
    const stopRecordBtn = document.getElementById('stopRecordBtn');
    const downloadBtn = document.getElementById('downloadBtn');

    let animationId = null;
    let isPlaying = false;
    let isRecording = false;
    let canvas_stream = null;
    let media_recorder = null;
    let recorded_chunks = [];

    // Export mode defaults to slower playback for clearer recordings.
    const FPS = 10;
    const PLAYBACK_SPEED = 0.6;
    const FRAME_TIME = 1000 / (FPS * PLAYBACK_SPEED);
    const MAX_TIMESTEP = viewer.getMaxTimestep();

    let currentTimestep = 0;
    let startTime = Date.now();

    function setTimestep(timestep) {{
        currentTimestep = Math.max(0, Math.min(timestep, MAX_TIMESTEP));
        viewer.setTimestep(currentTimestep);
        timestampEl.textContent = `${{currentTimestep}} / ${{MAX_TIMESTEP}} frames`;
    }}

    function animate() {{
        if (!isPlaying) return;

        const elapsed = Date.now() - startTime;
        const newTimestep = Math.floor(elapsed / FRAME_TIME);

        if (newTimestep > MAX_TIMESTEP) {{
            isPlaying = false;
            playBtn.disabled = false;
            pauseBtn.disabled = true;
            recordBtn.disabled = true;
            if (isRecording) stopRecording();
            return;
        }}

        setTimestep(newTimestep);
        animationId = requestAnimationFrame(animate);
    }}

    function startAnimation() {{
        if (isPlaying) return;
        isPlaying = true;
        startTime = Date.now() - currentTimestep * FRAME_TIME;
        playBtn.disabled = true;
        pauseBtn.disabled = false;
        recordBtn.disabled = false;
        animate();
    }}

    function pauseAnimation() {{
        isPlaying = false;
        if (animationId) {{
            cancelAnimationFrame(animationId);
        }}
        playBtn.disabled = false;
        pauseBtn.disabled = true;
        recordBtn.disabled = true;
    }}

    function startRecording() {{
        if (isRecording) return;
        isRecording = true;
        recorded_chunks = [];

        try {{
            canvas_stream = canvas.captureStream(FPS);
            media_recorder = new MediaRecorder(canvas_stream, {{
                mimeType: 'video/webm;codecs=vp8,opus'
            }});

            media_recorder.ondataavailable = (e) => {{
                recorded_chunks.push(e.data);
            }};

            media_recorder.onstop = () => {{
                downloadBtn.disabled = false;
                statusEl.textContent = '✓ Recording complete! Ready to download.';
            }};

            media_recorder.start();
            recordBtn.disabled = true;
            stopRecordBtn.disabled = false;
            statusEl.textContent = '🔴 Recording...';
        }} catch (e) {{
            statusEl.textContent = '✗ Error: ' + e.message;
        }}
    }}

    function stopRecording() {{
        if (!isRecording || !media_recorder) return;
        isRecording = false;
        media_recorder.stop();
        stopRecordBtn.disabled = true;
    }}

    function downloadVideo() {{
        if (recorded_chunks.length === 0) {{
            alert('No recording available');
            return;
        }}

        const blob = new Blob(recorded_chunks, {{ type: 'video/webm' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'experiment_' + (EXPERIMENT_DATA.config.solver || 'unknown') + '.webm';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }}

    setTimestep(0);

    window.startAnimation = startAnimation;
    window.pauseAnimation = pauseAnimation;
    window.startRecording = startRecording;
    window.stopRecording = stopRecording;
    window.downloadVideo = downloadVideo;
</script>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(video_html)
    
    print(f"\n✓ Exported video recorder HTML to {output_file}")
    print(f"Open it in a browser: file://{os.path.abspath(output_file)}")
    print(f"\nTo convert WebM to MP4:")
    print(f"  ffmpeg -i experiment.webm -c:v libx264 experiment.mp4")


def main():
    parser = argparse.ArgumentParser(
        description='MAPF Experiment Visualizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive viewer (opens in browser)
  python visualize_experiment.py ../exp/tesi_final_results/PBS_k20
  
  # Export standalone HTML
  python visualize_experiment.py ../exp/tesi_final_results/PBS_k20 --export-html output.html
  
  # Export data to JSON
  python visualize_experiment.py ../exp/tesi_final_results/PBS_k20 --export-json data.json
  
  # Start server on custom port
  python visualize_experiment.py ../exp/tesi_final_results/PBS_k20 --port 8080
        """
    )
    
    parser.add_argument('exp_folder', 
                       help='Path to experiment folder (containing paths.txt, config.txt, etc.)')
    
    parser.add_argument('--port', type=int, default=5000,
                       help='Port number for web server (default: 5000)')
    
    parser.add_argument('--no-browser', action='store_true',
                       help='Do not open browser automatically')
    
    parser.add_argument('--export-html', metavar='FILE',
                       help='Export standalone HTML (saved in visualizer/exports/html)')
    
    parser.add_argument('--export-json', metavar='FILE',
                       help='Export experiment data JSON (saved in visualizer/exports/json)')
    
    parser.add_argument('--export-video', metavar='FILE',
                       help='Export video recorder HTML (saved in visualizer/exports/video)')
    
    args = parser.parse_args()
    
    # Validate experiment folder
    exp_folder = Path(args.exp_folder)
    if not exp_folder.exists():
        print(f"Error: Experiment folder not found: {exp_folder}")
        return 1
    
    if not (exp_folder / 'paths.txt').exists():
        print(f"Error: paths.txt not found in {exp_folder}")
        return 1
    
    try:
        # Export options
        if args.export_html:
            output_file = resolve_export_output_path('html', args.export_html)
            print(f"Saving standalone HTML to: {output_file}")
            export_static_html(str(exp_folder), str(output_file))
        elif args.export_json:
            output_file = resolve_export_output_path('json', args.export_json)
            print(f"Saving JSON export to: {output_file}")
            exp_data = load_experiment(str(exp_folder))
            export_experiment_to_json(exp_data, str(output_file))
        elif args.export_video:
            output_file = resolve_export_output_path('video', args.export_video)
            print(f"Saving video recorder HTML to: {output_file}")
            export_video_html(str(exp_folder), str(output_file))
        else:
            # Start interactive server
            start_viewer_server(
                str(exp_folder), 
                port=args.port,
                open_browser=not args.no_browser
            )
    
    except KeyboardInterrupt:
        print("\n\nViewer stopped by user")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
