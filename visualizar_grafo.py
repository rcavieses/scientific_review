"""
Visualización interactiva del grafo de conocimiento científico.

Genera un archivo HTML con un grafo navegable (zoom, drag, filtros por tipo).

Uso:
    python visualizar_grafo.py                        # grafo completo (top-100 nodos)
    python visualizar_grafo.py --top 50               # solo los 50 nodos más conectados
    python visualizar_grafo.py --tipos Species Location  # solo esos tipos de entidad
    python visualizar_grafo.py --paper "2022_Feeding_habits..."  # entidades de un paper
    python visualizar_grafo.py --entidad "Lutjanus peru" --hops 2  # vecindad de una entidad
    python visualizar_grafo.py --todos                # grafo completo (puede ser lento)
    python visualizar_grafo.py --output mi_grafo.html
"""

import argparse
import io
import json
import sys
import webbrowser
from pathlib import Path

# Forzar UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Colores por tipo ──────────────────────────────────────────────────────────

ENTITY_COLORS = {
    "Species":  "#2ecc71",   # verde
    "Method":   "#3498db",   # azul
    "Location": "#e67e22",   # naranja
    "Concept":  "#9b59b6",   # morado
    "Author":   "#e74c3c",   # rojo
    "Paper":    "#f1c40f",   # amarillo
}

RELATION_COLORS = {
    "studies":        "#2ecc71",
    "found_in":       "#e67e22",
    "interacts_with": "#e74c3c",
    "measured_by":    "#3498db",
    "published_in":   "#f39c12",
    "co_occurs_with": "#9b59b6",
}

DEFAULT_COLOR = "#95a5a6"


def build_pyvis_graph(
    entities: dict,
    relations: dict,
    selected_nodes: set = None,
    height: str = "850px",
) -> "pyvis.network.Network":
    """Construye el objeto pyvis.Network con nodos y aristas configurados."""
    from pyvis.network import Network

    net = Network(
        height=height,
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ecf0f1",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )

    # Configuración de física y opciones de vis.js
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 120,
          "springConstant": 0.04,
          "damping": 0.09
        },
        "stabilization": {
          "iterations": 200,
          "updateInterval": 25
        }
      },
      "edges": {
        "smooth": {"type": "curvedCW", "roundness": 0.2},
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
        "font": {"size": 9, "color": "#bdc3c7", "strokeWidth": 0}
      },
      "nodes": {
        "font": {"size": 12, "color": "#ecf0f1"},
        "borderWidth": 1.5,
        "shadow": true
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 150
      }
    }
    """)

    # Calcular grado para tamaño de nodo
    degree: dict = {}
    for rel in relations.values():
        sid = rel["subject_id"]
        oid = rel["object_id"]
        if selected_nodes and (sid not in selected_nodes or oid not in selected_nodes):
            continue
        degree[sid] = degree.get(sid, 0) + 1
        degree[oid] = degree.get(oid, 0) + 1

    # Agregar nodos
    added_nodes = set()
    for eid, entity in entities.items():
        if selected_nodes and eid not in selected_nodes:
            continue

        etype = entity.get("entity_type", "Concept")
        color = ENTITY_COLORS.get(etype, DEFAULT_COLOR)
        deg = degree.get(eid, 0)
        size = max(10, min(40, 10 + deg * 2))

        # Tooltip con info de la entidad (texto plano — vis.js no renderiza HTML en titles)
        papers = entity.get("source_paper_ids", [])
        aliases = entity.get("aliases", [])
        lines = [
            entity["name"],
            f"Tipo: {etype}",
            f"Grado: {deg}",
            f"Papers: {len(papers)}",
        ]
        if aliases:
            lines.append(f"También: {', '.join(aliases[:3])}")
        tooltip = "\n".join(lines)

        net.add_node(
            eid,
            label=entity["name"][:30],
            title=tooltip,
            color={"background": color, "border": "#2c3e50", "highlight": {"background": "#f9f9f9"}},
            size=size,
            group=etype,
        )
        added_nodes.add(eid)

    # Agregar aristas
    for rel in relations.values():
        sid = rel["subject_id"]
        oid = rel["object_id"]
        if sid not in added_nodes or oid not in added_nodes:
            continue

        rtype = rel["relation_type"]
        conf = rel.get("confidence", 1.0)
        color = RELATION_COLORS.get(rtype, DEFAULT_COLOR)

        net.add_edge(
            sid,
            oid,
            label=rtype,
            title=f"{rtype} [conf={conf:.2f}]\n{rel.get('context_snippet', '')[:100]}",
            color={"color": color, "opacity": 0.7},
            width=max(0.5, conf * 2),
        )

    return net


def inject_legend(html_content: str) -> str:
    """Inyecta leyenda y tooltip CSS personalizado en el HTML generado."""
    legend_html = """
<style>
  #legend {
    position: fixed;
    top: 15px;
    right: 15px;
    background: rgba(26,26,46,0.92);
    border: 1px solid #34495e;
    border-radius: 8px;
    padding: 12px 16px;
    color: #ecf0f1;
    font-family: Arial, sans-serif;
    font-size: 12px;
    z-index: 9999;
    min-width: 160px;
  }
  #legend h3 { margin: 0 0 8px 0; font-size: 13px; color: #bdc3c7; }
  .legend-item { display: flex; align-items: center; margin: 4px 0; gap: 8px; }
  .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
  .legend-section { margin-top: 10px; border-top: 1px solid #34495e; padding-top: 8px; }
  .legend-line { width: 24px; height: 3px; flex-shrink: 0; border-radius: 2px; }
</style>
<div id="legend">
  <h3>Tipos de entidad</h3>
  <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div>Species</div>
  <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div>Method</div>
  <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div>Location</div>
  <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div>Concept</div>
  <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>Author</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f1c40f"></div>Paper</div>
  <div class="legend-section">
    <h3>Relaciones</h3>
    <div class="legend-item"><div class="legend-line" style="background:#2ecc71"></div>studies</div>
    <div class="legend-item"><div class="legend-line" style="background:#e67e22"></div>found_in</div>
    <div class="legend-item"><div class="legend-line" style="background:#e74c3c"></div>interacts_with</div>
    <div class="legend-item"><div class="legend-line" style="background:#3498db"></div>measured_by</div>
    <div class="legend-item"><div class="legend-line" style="background:#f39c12"></div>published_in</div>
    <div class="legend-item"><div class="legend-line" style="background:#9b59b6"></div>co_occurs_with</div>
  </div>
  <div class="legend-section" style="font-size:11px;color:#95a5a6;">
    Tamaño del nodo = grado<br>Ancho del arco = confianza
  </div>
</div>

<!-- Tooltip estilizado: intercepta el div nativo de vis.js con MutationObserver -->
<style>
  .vis-tooltip {
    background: rgba(26,26,46,0.97) !important;
    border: 1px solid #3498db !important;
    border-radius: 7px !important;
    padding: 10px 14px !important;
    color: #ecf0f1 !important;
    font-family: Arial, sans-serif !important;
    font-size: 12px !important;
    max-width: 300px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.6) !important;
    line-height: 1.7 !important;
    white-space: normal !important;
    pointer-events: none !important;
  }
</style>
<script>
(function() {
  // Esperar a que el contenedor del grafo exista
  function waitFor(selector, cb) {
    var el = document.querySelector(selector);
    if (el) { cb(el); return; }
    setTimeout(function() { waitFor(selector, cb); }, 150);
  }

  waitFor('#mynetwork', function(container) {
    // Observar cuando vis.js crea o muestra el tooltip
    var observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        m.addedNodes.forEach(function(node) {
          if (node.classList && node.classList.contains('vis-tooltip')) {
            styleTooltip(node);
          }
        });
        if (m.type === 'attributes' || m.type === 'characterData') {
          var tip = container.querySelector('.vis-tooltip');
          if (tip) styleTooltip(tip);
        }
      });
    });

    observer.observe(container, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
      attributeFilter: ['style']
    });
  });

  function styleTooltip(tip) {
    // Convertir \n en <br> y poner la primera línea en negrita/color
    var raw = tip.innerText || tip.textContent || '';
    if (!raw.trim()) return;
    var lines = raw.split('\n');
    var html = '<span style="font-weight:bold;font-size:13px;color:#3498db;display:block;'
             + 'border-bottom:1px solid #2c3e50;padding-bottom:4px;margin-bottom:5px;">'
             + esc(lines[0]) + '</span>';
    for (var i = 1; i < lines.length; i++) {
      if (lines[i].trim()) html += esc(lines[i]) + '<br>';
    }
    tip.innerHTML = html;
  }

  function esc(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
})();
</script>
"""
    return html_content.replace("</body>", legend_html + "\n</body>")


def main():
    parser = argparse.ArgumentParser(description="Visualización interactiva del grafo de conocimiento")
    parser.add_argument("--graph-dir", default="outputs/graph_index",
                        help="Directorio del grafo (default: outputs/graph_index)")
    parser.add_argument("--output", default="outputs/grafo_conocimiento.html",
                        help="Archivo HTML de salida (default: outputs/grafo_conocimiento.html)")
    parser.add_argument("--top", type=int, default=80,
                        help="Mostrar solo los N nodos más conectados (default: 80)")
    parser.add_argument("--todos", action="store_true",
                        help="Mostrar todos los nodos (puede ser lento)")
    parser.add_argument("--tipos", nargs="+",
                        choices=["Species", "Method", "Location", "Concept", "Author", "Paper"],
                        help="Filtrar por tipo de entidad")
    parser.add_argument("--paper", default=None,
                        help="Mostrar solo entidades del paper_id indicado")
    parser.add_argument("--entidad", default=None,
                        help="Entidad central para mostrar su vecindad")
    parser.add_argument("--hops", type=int, default=1,
                        help="Profundidad de vecindad al usar --entidad (default: 1)")
    parser.add_argument("--no-browser", action="store_true",
                        help="No abrir el navegador automáticamente")
    args = parser.parse_args()

    # Cargar grafo
    graph_file = Path(args.graph_dir) / "knowledge_graph.json"
    if not graph_file.exists():
        print(f"[error] No se encontró grafo en '{args.graph_dir}'.")
        print("  Construyelo primero: python construir_grafo.py")
        sys.exit(1)

    with open(graph_file, encoding="utf-8") as f:
        data = json.load(f)

    entities: dict = data.get("entities", {})
    relations: dict = data.get("relations", {})

    print(f"Grafo cargado: {len(entities)} entidades, {len(relations)} relaciones")

    # ── Selección de nodos ────────────────────────────────────────────────────

    selected: set = set(entities.keys())

    # Filtro por tipo
    if args.tipos:
        selected = {eid for eid in selected
                    if entities[eid].get("entity_type") in args.tipos}
        print(f"Filtro por tipo {args.tipos}: {len(selected)} entidades")

    # Filtro por paper
    if args.paper:
        selected = {eid for eid in selected
                    if args.paper in entities[eid].get("source_paper_ids", [])}
        print(f"Filtro por paper '{args.paper[:50]}': {len(selected)} entidades")

    # Vecindad de una entidad
    if args.entidad:
        # Buscar por nombre (case-insensitive)
        query = args.entidad.lower()
        center_id = next(
            (eid for eid, e in entities.items() if e["name"].lower() == query),
            next(
                (eid for eid, e in entities.items() if query in e["name"].lower()),
                None,
            ),
        )
        if not center_id:
            print(f"[error] No se encontró entidad '{args.entidad}'")
            sys.exit(1)

        print(f"Vecindad de '{entities[center_id]['name']}' ({args.hops} hops)")

        # BFS
        visited = {center_id}
        frontier = {center_id}
        for _ in range(args.hops):
            next_f = set()
            for rel in relations.values():
                if rel["subject_id"] in frontier and rel["object_id"] not in visited:
                    next_f.add(rel["object_id"])
                if rel["object_id"] in frontier and rel["subject_id"] not in visited:
                    next_f.add(rel["subject_id"])
            frontier = next_f & set(entities.keys())
            visited |= frontier
        selected = visited & set(entities.keys())
        print(f"Nodos en vecindad: {len(selected)}")

    # Limitar al top-N por grado (si no se pidieron todos)
    if not args.todos and not args.entidad and len(selected) > args.top:
        degree: dict = {}
        for rel in relations.values():
            for nid in (rel["subject_id"], rel["object_id"]):
                if nid in selected:
                    degree[nid] = degree.get(nid, 0) + 1
        top_ids = sorted(selected, key=lambda x: degree.get(x, 0), reverse=True)[:args.top]
        selected = set(top_ids)
        print(f"Limitado a top-{args.top} nodos más conectados")

    # Filtrar aristas a los nodos seleccionados
    n_edges = sum(
        1 for r in relations.values()
        if r["subject_id"] in selected and r["object_id"] in selected
    )
    print(f"Visualizando {len(selected)} nodos, {n_edges} relaciones")

    # ── Construir y guardar ───────────────────────────────────────────────────

    net = build_pyvis_graph(entities, relations, selected_nodes=selected)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Guardar HTML con UTF-8 explícito (save_graph usa el encoding del sistema en Windows)
    html_content = net.generate_html()
    html_content = inject_legend(html_content)
    output_path.write_text(html_content, encoding="utf-8")

    print(f"\nVisualización guardada en: {output_path.resolve()}")

    if not args.no_browser:
        webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    main()
