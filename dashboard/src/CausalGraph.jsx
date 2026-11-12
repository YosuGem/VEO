import React, { useState } from 'react';

/* ─────────────── Mock Data ─────────────── */
const NODES = [
  { id: 'IA', type: 'concepto', x: 50, y: 20 },
  { id: 'empleo', type: 'concepto', x: 30, y: 40 },
  { id: 'economia', type: 'concepto', x: 70, y: 40 },
  { id: 'politica', type: 'concepto', x: 85, y: 20 },
  { id: 'regulacion', type: 'evento', x: 65, y: 10 },
  { id: 'empresas tech', type: 'entidad', x: 20, y: 20 },
  { id: 'educacion', type: 'concepto', x: 10, y: 55 },
  { id: 'desigualdad', type: 'concepto', x: 45, y: 60 },
  { id: 'mercado laboral', type: 'concepto', x: 25, y: 75 },
  { id: 'inversion', type: 'concepto', x: 80, y: 55 },
  { id: 'banca central', type: 'entidad', x: 90, y: 70 },
  { id: 'inflacion', type: 'concepto', x: 60, y: 80 },
  { id: 'remoto', type: 'evento', x: 5, y: 35 },
  { id: 'GPT-4', type: 'entidad', x: 40, y: 5 },
  { id: 'open-source', type: 'entidad', x: 15, y: 5 },
];

const EDGES = [
  { from: 'IA', to: 'empleo', strength: 0.9 },
  { from: 'IA', to: 'economia', strength: 0.8 },
  { from: 'IA', to: 'regulacion', strength: 0.7 },
  { from: 'empleo', to: 'economia', strength: 0.85 },
  { from: 'economia', to: 'politica', strength: 0.75 },
  { from: 'regulacion', to: 'politica', strength: 0.9 },
  { from: 'empresas tech', to: 'IA', strength: 0.8 },
  { from: 'empresas tech', to: 'empleo', strength: 0.7 },
  { from: 'educacion', to: 'empleo', strength: 0.6 },
  { from: 'educacion', to: 'desigualdad', strength: 0.5 },
  { from: 'empleo', to: 'desigualdad', strength: 0.65 },
  { from: 'empleo', to: 'mercado laboral', strength: 0.9 },
  { from: 'economia', to: 'inversion', strength: 0.8 },
  { from: 'economia', to: 'inflacion', strength: 0.7 },
  { from: 'inversion', to: 'banca central', strength: 0.75 },
  { from: 'inflacion', to: 'banca central', strength: 0.85 },
  { from: 'politica', to: 'banca central', strength: 0.6 },
  { from: 'remoto', to: 'empleo', strength: 0.55 },
  { from: 'remoto', to: 'empresas tech', strength: 0.5 },
  { from: 'GPT-4', to: 'IA', strength: 0.95 },
  { from: 'open-source', to: 'GPT-4', strength: 0.7 },
  { from: 'open-source', to: 'IA', strength: 0.8 },
];

const NODE_COLORS = {
  entidad: '#4CAF50',
  concepto: '#2196F3',
  evento: '#FF9800',
};

const NODE_LABELS_ES = {
  entidad: 'Entidad', concepto: 'Concepto', evento: 'Evento',
};

/* ─────────────── Graph helpers ─────────────── */
function findPath(start, end) {
  const adj = {};
  NODES.forEach(n => adj[n.id] = []);
  EDGES.forEach(e => { adj[e.from].push(e.to); adj[e.to].push(e.from); });

  const visited = new Set();
  const queue = [[start]];
  while (queue.length) {
    const path = queue.shift();
    const node = path[path.length - 1];
    if (node === end) return path;
    if (visited.has(node)) continue;
    visited.add(node);
    for (const neighbor of adj[node]) {
      queue.push([...path, neighbor]);
    }
  }
  return null;
}

/* ─────────────── SVG Graph ─────────────── */
function GraphView({ highlightPath = [] }) {
  const highlightSet = new Set(highlightPath);
  const highlightEdges = new Set();
  for (let i = 0; i < highlightPath.length - 1; i++) {
    const a = highlightPath[i], b = highlightPath[i + 1];
    EDGES.forEach((e, idx) => {
      if ((e.from === a && e.to === b) || (e.from === b && e.to === a)) highlightEdges.add(idx);
    });
  }

  return (
    <svg viewBox="0 0 100 90" style={{ width: '100%', height: 'auto', background: '#1E1E1E', borderRadius: 8 }}>
      {/* Edges */}
      {EDGES.map((e, i) => {
        const from = NODES.find(n => n.id === e.from);
        const to = NODES.find(n => n.id === e.to);
        const isHighlighted = highlightEdges.has(i);
        return (
          <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
            stroke={isHighlighted ? '#fff' : '#444'} strokeWidth={isHighlighted ? 0.8 : 0.4}
            opacity={highlightPath.length > 0 && !isHighlighted ? 0.2 : 1}
          />
        );
      })}
      {/* Nodes */}
      {NODES.map(n => {
        const isHighlighted = highlightSet.has(n.id);
        return (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r={isHighlighted ? 4 : 3.2}
              fill={NODE_COLORS[n.type]}
              stroke={isHighlighted ? '#fff' : 'none'}
              strokeWidth={isHighlighted ? 1 : 0}
              opacity={highlightPath.length > 0 && !isHighlighted ? 0.3 : 1}
              style={{ cursor: 'pointer' }}
            />
            <text x={n.x} y={n.y + (n.y > 50 ? 6.5 : -4)} textAnchor="middle"
              fill={isHighlighted ? '#fff' : '#aaa'} fontSize="3.5"
              opacity={highlightPath.length > 0 && !isHighlighted ? 0.3 : 1}>
              {n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ─────────────── Main Component ─────────────── */
/* ─────────────── WS Indicator ─────────────── */
function WSIndicator({ message }) {
  if (!message) return null;
  return (
    <div style={{ position: 'fixed', bottom: 12, right: 12, background: '#1E1E1E', border: '1px solid var(--accent-green)', borderRadius: 6, padding: '8px 12px', fontSize: '0.75rem', color: '#4CAF50', zIndex: 1000, animation: 'fadeIn 0.3s ease' }}>
      <strong>WS:</strong> {message.tipo}
    </div>
  );
}

export default function CausalGraph({ wsMessage }) {
  const [fromNode, setFromNode] = useState('IA');
  const [toNode, setToNode] = useState('politica');
  const [pathResult, setPathResult] = useState(null);

  const handleFindPath = () => {
    const p = findPath(fromNode, toNode);
    setPathResult(p);
  };

  const totalNodes = NODES.length;
  const totalEdges = EDGES.length;
  const communities = 3;

  // Top centralidad (mock degree centrality)
  const centrality = NODES.map(n => ({
    node: n.id,
    degree: EDGES.filter(e => e.from === n.id || e.to === n.id).length,
  })).sort((a, b) => b.degree - a.degree);

  return (
    <div className="fade-in">
      <div className="page-title">&#9670; Grafo de Conocimiento</div>

      <div className="dashboard-grid-2">
        {/* Graph visualization */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9670; Mapa Causal</h3>
            <div className="graph-legend">
              {Object.entries(NODE_LABELS_ES).map(([type, label]) => (
                <div key={type} className="legend-item">
                  <span className="legend-dot" style={{ background: NODE_COLORS[type] }} />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
          <GraphView highlightPath={pathResult || []} />
          <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {totalNodes} nodos &middot; {totalEdges} relaciones &middot; {communities} comunidades detectadas
          </div>
        </div>

        {/* Stats panel */}
        <div className="card">
          <div className="card-header">
            <h3>&#9733; Estadisticas</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
            {[
              ['Nodos', totalNodes, '#2196F3'],
              ['Relaciones', totalEdges, '#4CAF50'],
              ['Comunidades', communities, '#FF9800'],
            ].map(([label, val, color]) => (
              <div key={label} style={{ textAlign: 'center', padding: 10, background: 'rgba(0,0,0,0.15)', borderRadius: 6 }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{val}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{label}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600 }}>
            Top 10 Centralidad (Degree):
          </div>
          <table>
            <thead>
              <tr><th>Nodo</th><th>Grado</th><th>Barra</th></tr>
            </thead>
            <tbody>
              {centrality.slice(0, 10).map(c => (
                <tr key={c.node}>
                  <td style={{ color: 'var(--accent-blue)' }}>{c.node}</td>
                  <td>{c.degree}</td>
                  <td>
                    <div className="progress-bar" style={{ maxWidth: 80 }}>
                      <div className="progress-fill blue" style={{ width: `${(c.degree / 6) * 100}%` }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Path finder */}
        <div className="card">
          <div className="card-header">
            <h3>&#10132; Buscar Camino</h3>
          </div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Desde</label>
              <select value={fromNode} onChange={e => setFromNode(e.target.value)}>
                {NODES.map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Hasta</label>
              <select value={toNode} onChange={e => setToNode(e.target.value)}>
                {NODES.map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
              </select>
            </div>
            <button className="btn-primary" onClick={handleFindPath} style={{ alignSelf: 'flex-end' }}>
              &#10132; Buscar
            </button>
          </div>

          {pathResult && (
            <div className="path-result">
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 10 }}>
                Camino encontrado ({pathResult.length - 1} saltos):
              </div>
              <div className="path-steps">
                {pathResult.map((node, i) => (
                  <React.Fragment key={i}>
                    <span className="path-node">{node}</span>
                    {i < pathResult.length - 1 && <span className="path-arrow">&#10132;</span>}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {pathResult === null && (
            <div style={{ color: 'var(--accent-red)', fontSize: '0.85rem' }}>
              No se encontro camino entre los nodos seleccionados.
            </div>
          )}
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
