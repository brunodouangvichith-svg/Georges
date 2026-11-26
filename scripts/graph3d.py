"""Vue 3D du graphe graphify : graphify-out/graph.json -> graphify-out/graph3d.html.

    graphify update .
    python scripts/graph3d.py

La page charge la bibliothèque 3d-force-graph depuis unpkg (connexion requise).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "graphify-out"

# Zone = premier dossier du fichier source. Couleur fixe, lisible sur fond sombre.
ZONES = {
    "engine": "#4f9dff",
    "agents": "#b78bff",
    "api": "#34d399",
    "ingestion": "#fbbf24",
    "web": "#f472b6",
    "mobile": "#22d3ee",
    "tests": "#94a3b8",
    "docs": "#f87171",
    "autres": "#d6d3d1",
}


def zone(source_file: str) -> str:
    path = source_file.replace("\\", "/")
    if path.endswith(".md"):
        return "docs"
    head = path.split("/")[0]
    return head if head in ZONES else "autres"


def load_graph() -> dict:
    graph = json.loads((OUT / "graph.json").read_text(encoding="utf-8"))
    links = graph.get("links") or graph.get("edges") or []
    degree = Counter()
    for link in links:
        degree[link["source"]] += 1
        degree[link["target"]] += 1
    return {
        "nodes": [
            {
                "id": n["id"],
                "label": n.get("label") or n["id"],
                "file": (n.get("source_file") or "").replace("\\", "/"),
                "line": n.get("source_location") or "",
                "zone": zone(n.get("source_file") or ""),
                "degree": degree[n["id"]],
            }
            for n in graph["nodes"]
        ],
        "links": [
            {"source": l["source"], "target": l["target"], "relation": l.get("relation", "")} for l in links
        ],
    }


PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Graphe 3D George</title>
<style>
html,body{margin:0;height:100%;overflow:hidden;background:#0f1626;color:#e8ecf8;font:14px system-ui,sans-serif}
aside{position:fixed;top:12px;left:12px;width:270px;max-height:calc(100% - 48px);overflow:auto;
 background:#17213aee;border:1px solid #33406b;border-radius:10px;padding:12px}
input,button{font:inherit;color:inherit;background:#0f1626;border:1px solid #55649a;border-radius:6px;padding:5px 8px}
input[type=search]{box-sizing:border-box;width:100%}
button{cursor:pointer}
label{display:flex;gap:8px;align-items:center;margin:3px 0}
.dot{width:10px;height:10px;border-radius:50%}
#info{overflow-wrap:anywhere;margin-top:8px}
#info button{display:block;width:100%;text-align:left;border:0;padding:2px 0}
small{color:#aab4d6}
</style></head><body>
<div id="graph"></div>
<aside>
 <input id="q" type="search" list="names" placeholder="Chercher puis Entrée" aria-label="Chercher un nœud">
 <datalist id="names"></datalist>
 <div id="zones"></div>
 <button id="reset">Vue d'ensemble</button>
 <div id="info" aria-live="polite"></div>
</aside>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
<script>
const data = __DATA__, colors = __ZONES__;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
const byId = new Map(data.nodes.map(n => [n.id, n]));
const near = new Map(data.nodes.map(n => [n.id, new Set()]));
data.links.forEach(l => { near.get(l.source)?.add(l.target); near.get(l.target)?.add(l.source); });
const shown = new Set(Object.keys(colors));
let selected = null;
const end = e => typeof e === 'object' ? e : byId.get(e);
const lit = n => !selected || n === selected || near.get(selected.id).has(n.id);
const touches = l => selected && (end(l.source) === selected || end(l.target) === selected);

if (typeof ForceGraph3D === 'undefined') {
  $('info').textContent = 'Bibliothèque 3D non chargée : vérifiez la connexion Internet.';
  throw new Error('3d-force-graph absent');
}
const G = ForceGraph3D()($('graph'))
  .backgroundColor('#0f1626')
  .nodeRelSize(3)
  .nodeVal(n => 1 + n.degree / 2)
  .nodeLabel(n => `<b>${esc(n.label)}</b><br>${esc(n.file)} ${esc(n.line)}<br>${n.degree} liens`)
  .nodeColor(n => lit(n) ? colors[n.zone] : '#222c49')
  .nodeVisibility(n => shown.has(n.zone))
  .linkVisibility(l => shown.has(end(l.source).zone) && shown.has(end(l.target).zone))
  .linkColor(l => touches(l) ? '#ffd34d' : (selected ? '#1b2440' : '#6b7aaa'))
  .linkOpacity(0.3)
  .linkLabel(l => esc(l.relation))
  .onNodeClick(select)
  .onBackgroundClick(() => select(null))
  .graphData(data);
G.d3Force('charge').strength(-50);
addEventListener('resize', () => G.width(innerWidth).height(innerHeight));

function select(node) {
  selected = node;
  G.nodeColor(G.nodeColor()).linkColor(G.linkColor());
  const box = $('info');
  box.textContent = '';
  const add = (tag, text) => { const e = document.createElement(tag); e.textContent = text; box.append(e); return e; };
  if (!node) { add('small', `${data.nodes.length} nœuds, ${data.links.length} liens`); return; }
  add('b', node.label); add('br', ''); add('small', `${node.file} ${node.line}`);
  [...near.get(node.id)].map(i => byId.get(i)).sort((a, b) => b.degree - a.degree)
    .forEach(n => { add('button', n.label).onclick = () => select(n); });
  G.zoomToFit(800, 60, lit);
}

Object.entries(colors).forEach(([name, color]) => {
  const row = document.createElement('label'), box = document.createElement('input'), dot = document.createElement('span');
  box.type = 'checkbox'; box.checked = true; dot.className = 'dot'; dot.style.background = color;
  box.onchange = () => {
    box.checked ? shown.add(name) : shown.delete(name);
    G.nodeVisibility(G.nodeVisibility()).linkVisibility(G.linkVisibility());
  };
  row.append(box, dot, `${name} (${data.nodes.filter(n => n.zone === name).length})`);
  $('zones').append(row);
});
[...new Set(data.nodes.map(n => n.label))].sort().forEach(l => $('names').append(new Option(l)));
$('q').onchange = e => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) return;
  const hit = data.nodes.filter(n => n.label.toLowerCase().includes(q))
    .sort((a, b) => (b.label.toLowerCase() === q) - (a.label.toLowerCase() === q) || b.degree - a.degree)[0];
  if (hit) select(hit); else $('info').textContent = 'Aucun résultat';
};
$('reset').onclick = () => { select(null); G.zoomToFit(800, 40); };
select(null);
setTimeout(() => G.zoomToFit(800, 40), 4000);
</script></body></html>
"""


def main() -> None:
    data = load_graph()
    # « < » échappé : un libellé ne doit pas pouvoir fermer la balise <script>.
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = PAGE.replace("__ZONES__", json.dumps(ZONES)).replace("__DATA__", blob)
    (OUT / "graph3d.html").write_text(html, encoding="utf-8")
    print(f"graph3d.html : {len(data['nodes'])} nœuds, {len(data['links'])} liens")


if __name__ == "__main__":
    main()
