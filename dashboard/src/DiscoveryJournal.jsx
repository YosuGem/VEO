import React, { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

/* ─────────────── Mock Data ─────────────── */
const WEEKS = [
  { id: 'W8', label: 'Semana 8 (actual)' },
  { id: 'W7', label: 'Semana 7' },
  { id: 'W6', label: 'Semana 6' },
  { id: 'W5', label: 'Semana 5' },
  { id: 'W4', label: 'Semana 4' },
  { id: 'W3', label: 'Semana 3' },
  { id: 'W2', label: 'Semana 2' },
  { id: 'W1', label: 'Semana 1' },
];

const WEEKLY_DATA = {
  W8: {
    newHypotheses: 5, confirmed: 2, refuted: 1, avgConfidence: 0.68,
    newList: [
      { id: 'H#48', text: 'La regulacion de IA en la UE impulsara la inversion en startups europeas de compliance' },
      { id: 'H#49', text: 'El modelo "freemium" de APIs de IA alcanzara punto de inflexion en Q2 2024' },
      { id: 'H#50', text: 'Los sindicatos de tech ganaran traccion en empresas con >1000 empleados' },
      { id: 'H#51', text: 'Las stablecoins de bancos centrales reemplazaran el 20% de pagos transfronterizos' },
      { id: 'H#52', text: 'La energia nuclear modular sera anunciada como prioridad energetica por 3+ paises' },
    ],
    confirmedList: [
      { id: 'H#44', text: 'El teletrabajo hibrido se consolida como modelo dominante en tech (>70%)' },
      { id: 'H#47', text: 'Los modelos open-source alcanzan paridad de rendimiento con GPT-4' },
    ],
    refutedList: [
      { id: 'H#45', text: 'Las stablecoins reguladas superaran en volumen a las no reguladas' },
    ],
    trends: ['IA regulacion', 'Open-source LLMs', 'Energia nuclear', 'Teletrabajo hibrido', 'Sindicatos tech'],
    learnings: [
      { title: 'La evidencia academica tiene mayor peso en predicciones de 6+ meses', source: 'Validacion dual H#42' },
      { title: 'Los mercados de prediccion anticiparon 3 dias la confirmacion de H#44', source: 'Analisis MP-08' },
      { title: 'El sentimiento en HN/Reddit precede a los cambios en datos laborales en ~2 semanas', source: 'Pipeline narrativa' },
    ],
  },
  W7: {
    newHypotheses: 4, confirmed: 1, refuted: 2, avgConfidence: 0.62,
    newList: [
      { id: 'H#44', text: 'El teletrabajo hibrido se consolida como modelo dominante en tech' },
      { id: 'H#45', text: 'Las stablecoins reguladas superaran en volumen a las no reguladas' },
      { id: 'H#46', text: 'La inversion en nuclear resurgira como prioridad energetica' },
      { id: 'H#47', text: 'Los modelos open-source alcanzan paridad con GPT-4' },
    ],
    confirmedList: [{ id: 'H#40', text: 'El gasto en cloud supera el 40% del presupuesto IT empresarial' }],
    refutedList: [
      { id: 'H#38', text: 'El metaverso empresarial alcanzara adopcion critica en 2024' },
      { id: 'H#36', text: 'Las criptomonedas se usaran para salarios mainstream' },
    ],
    trends: ['Adopcion cloud', 'Metaverso lento', 'Cripto salarios', 'Nuclear revival'],
    learnings: [
      { title: 'Las hipotesis con >5 evidencias iniciales tienen 3x tasa de confirmacion', source: 'Analisis historico' },
    ],
  },
};

const EIGHT_WEEKS_HISTORY = Array.from({ length: 8 }, (_, i) => ({
  semana: `S${i + 1}`,
  hipotesis: [8, 12, 6, 9, 11, 7, 10, 5][i],
  confianza: [0.55, 0.58, 0.62, 0.60, 0.65, 0.63, 0.66, 0.68][i],
  actividad: [45, 62, 38, 55, 71, 48, 58, 52][i],
  confirmadas: [2, 3, 1, 2, 4, 2, 3, 2][i],
  refutadas: [1, 2, 3, 1, 1, 2, 2, 1][i],
}));

/* ─────────────── Custom Tooltip ─────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload) return null;
  return (
    <div style={{
      background: '#1E1E1E', border: '1px solid #333', borderRadius: 6,
      padding: '8px 12px', fontSize: '0.8rem'
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(p.name === 'Confianza' ? 2 : 0) : p.value}
        </div>
      ))}
    </div>
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

export default function DiscoveryJournal({ wsMessage }) {
  const [selectedWeek, setSelectedWeek] = useState('W8');

  const data = WEEKLY_DATA[selectedWeek] || WEEKLY_DATA['W8'];

  return (
    <div className="fade-in">
      <div className="page-title">&#9997; Diario de Descubrimientos</div>

      {/* Week selector */}
      <div className="filters-bar" style={{ marginBottom: 20 }}>
        <div className="filter-group">
          <label>Semana:</label>
          <select value={selectedWeek} onChange={e => setSelectedWeek(e.target.value)}>
            {WEEKS.map(w => <option key={w.id} value={w.id}>{w.label}</option>)}
          </select>
        </div>
      </div>

      {/* Summary metrics */}
      <div className="dashboard-grid" style={{ marginBottom: 20 }}>
        {[
          { label: 'Hipotesis Nuevas', value: data.newHypotheses, color: 'var(--accent-blue)' },
          { label: 'Confirmadas', value: data.confirmed, color: 'var(--accent-green)' },
          { label: 'Refutadas', value: data.refuted, color: 'var(--accent-red)' },
          { label: 'Confianza Promedio', value: `${(data.avgConfidence * 100).toFixed(0)}%`, color: 'var(--accent-orange)' },
        ].map((m, i) => (
          <div key={i} className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: m.color }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid-2">
        {/* New hypotheses */}
        <div className="card">
          <div className="card-header">
            <h3>&#9733; Hipotesis Nuevas ({data.newList.length})</h3>
          </div>
          {data.newList.map(h => (
            <div key={h.id} style={{
              padding: '10px 12px', marginBottom: 8, background: 'rgba(33,150,243,0.1)',
              borderRadius: 6, border: '1px solid rgba(33,150,243,0.2)', fontSize: '0.85rem'
            }}>
              <strong style={{ color: 'var(--accent-blue)' }}>{h.id}</strong>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>{h.text}</span>
            </div>
          ))}
        </div>

        {/* Confirmed */}
        <div className="card">
          <div className="card-header">
            <h3 style={{ color: 'var(--accent-green)' }}>&#10003; Confirmadas ({data.confirmedList.length})</h3>
          </div>
          {data.confirmedList.map(h => (
            <div key={h.id} style={{
              padding: '10px 12px', marginBottom: 8, background: 'rgba(76,175,80,0.1)',
              borderRadius: 6, border: '1px solid rgba(76,175,80,0.2)', display: 'flex', alignItems: 'center', gap: 10
            }}>
              <span style={{ fontSize: '1.1rem', color: 'var(--accent-green)' }}>&#10003;</span>
              <div>
                <strong style={{ color: 'var(--accent-green)', fontSize: '0.8rem' }}>{h.id}</strong>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{h.text}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Refuted */}
        <div className="card">
          <div className="card-header">
            <h3 style={{ color: 'var(--accent-red)' }}>&#10005; Refutadas ({data.refutedList.length})</h3>
          </div>
          {data.refutedList.map(h => (
            <div key={h.id} style={{
              padding: '10px 12px', marginBottom: 8, background: 'rgba(244,67,54,0.1)',
              borderRadius: 6, border: '1px solid rgba(244,67,54,0.2)', display: 'flex', alignItems: 'center', gap: 10
            }}>
              <span style={{ fontSize: '1.1rem', color: 'var(--accent-red)' }}>&#10005;</span>
              <div>
                <strong style={{ color: 'var(--accent-red)', fontSize: '0.8rem' }}>{h.id}</strong>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{h.text}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Trends */}
        <div className="card">
          <div className="card-header">
            <h3>&#9650; Tendencias Detectadas</h3>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.trends.map(t => (
              <span key={t} className="tag tag-orange">{t}</span>
            ))}
          </div>
        </div>

        {/* Learnings */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9733; Aprendizajes</h3>
          </div>
          <div className="dashboard-grid-3">
            {data.learnings.map((l, i) => (
              <div key={i} style={{
                padding: 14, background: 'rgba(0,0,0,0.15)', borderRadius: 8,
                border: '1px solid var(--border-color)'
              }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginBottom: 6, fontWeight: 500 }}>
                  {l.title}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{l.source}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 8-week history chart */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#128200; Evolucion Temporal (8 semanas)</h3>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={EIGHT_WEEKS_HISTORY}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="semana" stroke="#777" fontSize={11} tickLine={false} />
              <YAxis yAxisId="left" stroke="#777" fontSize={11} tickLine={false} />
              <YAxis yAxisId="right" orientation="right" stroke="#777" fontSize={11} tickLine={false} domain={[0, 1]} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
              <Line yAxisId="left" type="monotone" dataKey="hipotesis" name="Hipotesis" stroke="#2196F3" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="left" type="monotone" dataKey="actividad" name="Actividad" stroke="#FF9800" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="left" type="monotone" dataKey="confirmadas" name="Confirmadas" stroke="#4CAF50" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="left" type="monotone" dataKey="refutadas" name="Refutadas" stroke="#F44336" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="right" type="monotone" dataKey="confianza" name="Confianza" stroke="#9C27B0" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
