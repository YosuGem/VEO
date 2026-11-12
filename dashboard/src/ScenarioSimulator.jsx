import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';

/* ─────────────── Helpers ─────────────── */
function generateNormal(mean, std, n = 10000) {
  const out = [];
  for (let i = 0; i < n; i++) {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    const z = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    out.push(mean + std * z);
  }
  return out;
}

function histogram(data, bins = 30) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const step = (max - min) / bins;
  const counts = Array(bins).fill(0);
  data.forEach(v => {
    const idx = Math.min(Math.floor((v - min) / step), bins - 1);
    counts[idx]++;
  });
  return Array.from({ length: bins }, (_, i) => ({
    bin: `${(min + i * step).toFixed(1)}`,
    count: counts[i],
    range: [min + i * step, min + (i + 1) * step],
  }));
}

function percentile(sorted, p) {
  const idx = Math.floor(sorted.length * p);
  return sorted[idx];
}

/* ─────────────── Mock Scenarios ─────────────── */
const SAVED_SCENARIOS = [
  {
    id: 'S1', name: 'Recesion suave 2024', desc: 'Escenario de desaceleracion economica moderada',
    variables: [
      { name: 'PIB', base: 1.5, min: -2, max: 3, dist: 'normal' },
      { name: 'Inflacion', base: 3.2, min: 1, max: 7, dist: 'normal' },
      { name: 'Desempleo', base: 4.5, min: 3, max: 9, dist: 'normal' },
      { name: 'Tipos interes', base: 4.0, min: 2, max: 6, dist: 'uniforme' },
    ]
  },
  {
    id: 'S2', name: 'Boom IA acelerado', desc: 'Adopcion masiva de IA generativa',
    variables: [
      { name: 'Adopcion IA', base: 65, min: 40, max: 95, dist: 'normal' },
      { name: 'Productividad', base: 2.8, min: 0, max: 6, dist: 'normal' },
      { name: 'Cambio empleo', base: -5, min: -15, max: 5, dist: 'normal' },
      { name: 'Inversion tech', base: 120, min: 80, max: 200, dist: 'lognormal' },
    ]
  },
];

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

export default function ScenarioSimulator({ wsMessage }) {
  const [scenarioName, setScenarioName] = useState('');
  const [scenarioDesc, setScenarioDesc] = useState('');
  const [variables, setVariables] = useState([
    { name: '', base: '', min: '', max: '', dist: 'normal' },
  ]);
  const [simResult, setSimResult] = useState(null);
  const [compareA, setCompareA] = useState('S1');
  const [compareB, setCompareB] = useState('S2');

  const addVariable = () => {
    setVariables([...variables, { name: '', base: '', min: '', max: '', dist: 'normal' }]);
  };

  const removeVariable = (idx) => {
    setVariables(variables.filter((_, i) => i !== idx));
  };

  const updateVar = (idx, field, value) => {
    setVariables(variables.map((v, i) => i === idx ? { ...v, [field]: value } : v));
  };

  const runSimulation = () => {
    const results = {};
    variables.forEach(v => {
      if (!v.name) return;
      const mean = Number(v.base) || 0;
      const std = (Math.abs(Number(v.max) - Number(v.min)) || 1) / 4;
      const samples = generateNormal(mean, std, 10000);
      const sorted = [...samples].sort((a, b) => a - b);
      results[v.name] = {
        histogram: histogram(samples, 30),
        stats: {
          mean: sorted.reduce((a, b) => a + b, 0) / sorted.length,
          median: percentile(sorted, 0.5),
          p5: percentile(sorted, 0.05),
          p95: percentile(sorted, 0.95),
        },
        impact: std / (Math.abs(mean) || 1),
      };
    });
    setSimResult(results);
    console.log('[SOIS] Simulacion Monte Carlo ejecutada:', Object.keys(results));
  };

  const scenarioA = SAVED_SCENARIOS.find(s => s.id === compareA);
  const scenarioB = SAVED_SCENARIOS.find(s => s.id === compareB);

  return (
    <div className="fade-in">
      <div className="page-title">&#9881; Simulador de Escenarios</div>

      <div className="dashboard-grid-2">
        {/* Form */}
        <div className="card">
          <div className="card-header">
            <h3>&#9998; Crear Escenario</h3>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Nombre</label>
              <input value={scenarioName} onChange={e => setScenarioName(e.target.value)} placeholder="Ej: Recesion suave" />
            </div>
            <div className="form-group">
              <label>Descripcion</label>
              <input value={scenarioDesc} onChange={e => setScenarioDesc(e.target.value)} placeholder="Breve descripcion" />
            </div>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600 }}>
            Variables ({variables.length}):
          </div>
          <div className="variables-list">
            {variables.map((v, i) => (
              <div key={i} className="variable-row">
                <div className="form-group">
                  <label style={{ fontSize: '0.7rem' }}>Nombre</label>
                  <input value={v.name} onChange={e => updateVar(i, 'name', e.target.value)} placeholder="Variable" />
                </div>
                <div className="form-group">
                  <label style={{ fontSize: '0.7rem' }}>Base</label>
                  <input type="number" value={v.base} onChange={e => updateVar(i, 'base', e.target.value)} placeholder="0" />
                </div>
                <div className="form-group">
                  <label style={{ fontSize: '0.7rem' }}>Min</label>
                  <input type="number" value={v.min} onChange={e => updateVar(i, 'min', e.target.value)} placeholder="0" />
                </div>
                <div className="form-group">
                  <label style={{ fontSize: '0.7rem' }}>Max</label>
                  <input type="number" value={v.max} onChange={e => updateVar(i, 'max', e.target.value)} placeholder="0" />
                </div>
                <div className="form-group">
                  <label style={{ fontSize: '0.7rem' }}>Dist.</label>
                  <select value={v.dist} onChange={e => updateVar(i, 'dist', e.target.value)}>
                    <option value="normal">Normal</option>
                    <option value="uniforme">Uniforme</option>
                    <option value="lognormal">Log-Normal</option>
                  </select>
                </div>
                <button onClick={() => removeVariable(i)} className="btn-danger btn-small" style={{ height: 32 }}>
                  &#10005;
                </button>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <button onClick={addVariable}>&#43; Agregar Variable</button>
            <button className="btn-success" onClick={runSimulation}>
              &#9654; Ejecutar Simulacion (MC)
            </button>
          </div>
        </div>

        {/* Results */}
        {simResult && (
          <div>
            {Object.entries(simResult).map(([varName, data]) => (
              <div key={varName} className="card" style={{ marginBottom: 16 }}>
                <div className="card-header">
                  <h3>&#128200; {varName}</h3>
                  <span className="tag tag-blue">n=10,000</span>
                </div>

                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={data.histogram}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="bin" stroke="#777" fontSize={9} tickLine={false} interval={4} />
                    <YAxis stroke="#777" fontSize={10} tickLine={false} />
                    <Tooltip contentStyle={{ background: '#1E1E1E', border: '1px solid #333', fontSize: '0.8rem' }} />
                    <Bar dataKey="count" fill="#2196F3" radius={[2, 2, 0, 0]}>
                      {data.histogram.map((_, i) => (
                        <Cell key={i} fill={i < data.histogram.length / 2 ? '#2196F3' : '#4CAF50'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>

                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 10
                }}>
                  {[
                    ['Media', data.stats.mean.toFixed(2), '#E0E0E0'],
                    ['Mediana', data.stats.median.toFixed(2), '#2196F3'],
                    ['P5', data.stats.p5.toFixed(2), '#F44336'],
                    ['P95', data.stats.p95.toFixed(2), '#4CAF50'],
                  ].map(([label, val, color]) => (
                    <div key={label} style={{ textAlign: 'center', padding: 8, background: 'rgba(0,0,0,0.15)', borderRadius: 4 }}>
                      <div style={{ fontSize: '0.9rem', fontWeight: 700, color }}>{val}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Sensitivity */}
            <div className="card">
              <div className="card-header">
                <h3>&#9733; Analisis de Sensibilidad</h3>
              </div>
              <table>
                <thead>
                  <tr><th>Variable</th><th>Impacto</th><th>Score</th></tr>
                </thead>
                <tbody>
                  {Object.entries(simResult)
                    .sort((a, b) => b[1].impact - a[1].impact)
                    .map(([name, data]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>
                          <div className="progress-bar" style={{ maxWidth: 120 }}>
                            <div className="progress-fill orange" style={{ width: `${Math.min(data.impact * 100, 100)}%` }} />
                          </div>
                        </td>
                        <td style={{ fontWeight: 600, color: 'var(--accent-orange)' }}>
                          {data.impact.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Comparison */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#8596; Comparar Escenarios</h3>
          </div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
            <div className="filter-group">
              <label>Escenario A:</label>
              <select value={compareA} onChange={e => setCompareA(e.target.value)}>
                {SAVED_SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="filter-group">
              <label>Escenario B:</label>
              <select value={compareB} onChange={e => setCompareB(e.target.value)}>
                {SAVED_SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>

          {scenarioA && scenarioB && (
            <table>
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>{scenarioA.name}</th>
                  <th>{scenarioB.name}</th>
                  <th>Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {scenarioA.variables.map((v, i) => {
                  const vB = scenarioB.variables[i] || {};
                  const diff = Number(v.base) - Number(vB.base || 0);
                  return (
                    <tr key={v.name} className={Math.abs(diff) > 1 ? 'comparison-highlight' : ''}>
                      <td><strong>{v.name}</strong></td>
                      <td>{v.base} ({v.dist})</td>
                      <td>{vB.base || '-'} ({vB.dist || '-'})</td>
                      <td style={{ color: diff > 0 ? '#4CAF50' : diff < 0 ? '#F44336' : '#aaa', fontWeight: 600 }}>
                        {diff > 0 ? '+' : ''}{diff.toFixed(1)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
