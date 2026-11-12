import React from 'react';

/* ─────────────── Mock Data ─────────────── */
const SHIFTS = [
  {
    id: 1, topic: 'Regulacion de IA en la UE',
    from: 'Skepticismo / oposicion tech',
    to: 'Aceptacion como inevitable / oportunidad',
    magnitude: 0.78, date: '2024-01-15', direction: 'positive',
    beforeTerms: ['bloqueo', 'burocracia', 'retraso', 'oposicion'],
    afterTerms: ['liderazgo', 'confianza', 'ventaja competitiva', 'responsable'],
  },
  {
    id: 2, topic: 'Modelo de trabajo remoto',
    from: 'Debate abierto hibrido vs presencial',
    to: 'Hibrido consolidado como estandar',
    magnitude: 0.65, date: '2024-01-14', direction: 'positive',
    beforeTerms: ['vuelta oficina', 'presencial obligatorio', 'productividad dudosa'],
    afterTerms: ['flexibilidad', 'talento global', 'balance', 'resultados'],
  },
  {
    id: 3, topic: 'Energia nuclear',
    from: 'Tabu post-Fukushima',
    to: 'Solucion necesaria para net-zero',
    magnitude: 0.82, date: '2024-01-12', direction: 'positive',
    beforeTerms: ['peligrosa', 'residuos', 'accidente', 'renovable pura'],
    afterTerms: ['limpia', 'confiable', 'base carga', 'SMR revolucion'],
  },
  {
    id: 4, topic: 'Criptomonedas institucionales',
    from: 'Interes especulativo',
    to: 'Skepticismo post-ETF/regular',
    magnitude: 0.55, date: '2024-01-10', direction: 'negative',
    beforeTerms: ['adopcion institucional', 'hedge inflacion', 'descorrelacion'],
    afterTerms: ['volatilidad', 'regulacion pendiente', 'riesgo sistémico'],
  },
  {
    id: 5, topic: 'Open-source vs closed AI',
    from: 'GPT-4 dominante / open insuficiente',
    to: 'Open-source alcanza paridad funcional',
    magnitude: 0.71, date: '2024-01-08', direction: 'positive',
    beforeTerms: ['gap de rendimiento', 'empresarial cerrado', 'API-only'],
    afterTerms: ['Llama-3', 'Mistral', 'self-hosting', 'soberania IA'],
  },
];

const TERMS_COMPARISON = [
  { term: 'regulacion IA', before: 12, after: 78, trend: 'up' },
  { term: 'open-source LLM', before: 45, after: 89, trend: 'up' },
  { term: 'teletrabajo', before: 92, after: 68, trend: 'down' },
  { term: 'oficina presencial', before: 34, after: 22, trend: 'down' },
  { term: 'energia nuclear', before: 18, after: 64, trend: 'up' },
  { term: 'cripto institucional', before: 71, after: 38, trend: 'down' },
  { term: 'sindicatos tech', before: 8, after: 41, trend: 'up' },
  { term: 'metaverso', before: 88, after: 25, trend: 'down' },
  { term: 'multimodal AI', before: 15, after: 72, trend: 'up' },
  { term: 'RAG systems', before: 22, after: 66, trend: 'up' },
];

/* ─────────────── Sentiment Gauge ─────────────── */
function SentimentGauge({ value }) {
  const pct = ((value + 1) / 2) * 100;
  const color = value > 0.3 ? '#4CAF50' : value > -0.3 ? '#FF9800' : '#F44336';
  const label = value > 0.3 ? 'Positivo' : value > -0.3 ? 'Neutral' : 'Negativo';
  return (
    <div className="gauge-container">
      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Sentimiento Narrativo</div>
      <div style={{ fontSize: '2rem', fontWeight: 700, color }}>{label}</div>
      <div style={{ fontSize: '1.2rem', color }}>{value > 0 ? '+' : ''}{value.toFixed(2)}</div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="gauge-labels">
        <span>-1.0</span><span>0</span><span>+1.0</span>
      </div>
    </div>
  );
}

/* ─────────────── Shift Magnitude Bar ─────────────── */
function MagnitudeBar({ value }) {
  const color = value >= 0.7 ? '#F44336' : value >= 0.5 ? '#FF9800' : '#4CAF50';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 100 }}>
      <div className="progress-bar" style={{ flex: 1 }}>
        <div className="progress-fill" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.75rem', fontWeight: 600, color, minWidth: 32 }}>
        {(value * 100).toFixed(0)}%
      </span>
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

export default function NarrativeShift({ wsMessage }) {
  const avgSentiment = SHIFTS.reduce((s, sh) => s + (sh.direction === 'positive' ? sh.magnitude : -sh.magnitude), 0) / SHIFTS.length;

  return (
    <div className="fade-in">
      <div className="page-title">&#9650; Cambios de Narrativa</div>

      <div className="dashboard-grid-2">
        {/* Sentiment gauge */}
        <div className="card" style={{ textAlign: 'center' }}>
          <SentimentGauge value={avgSentiment} />
        </div>

        {/* Shift alerts */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9888; Cambios Detectados ({SHIFTS.length})</h3>
          </div>
          {SHIFTS.map(shift => (
            <div key={shift.id} className="alert-card" style={{
              borderLeftColor: shift.direction === 'positive' ? '#4CAF50' : '#F44336',
            }}>
              <span className="alert-icon" style={{ color: shift.direction === 'positive' ? '#4CAF50' : '#F44336' }}>
                {shift.direction === 'positive' ? '\u2197' : '\u2198'}
              </span>
              <div className="alert-content" style={{ flex: 1 }}>
                <div className="alert-title">{shift.topic}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ textDecoration: 'line-through', opacity: 0.6 }}>{shift.from}</span>
                  <span style={{ color: 'var(--text-muted)' }}>&#10132;</span>
                  <span style={{ color: shift.direction === 'positive' ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 500 }}>
                    {shift.to}
                  </span>
                </div>
                <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {shift.afterTerms.map(t => (
                    <span key={t} className="tag tag-green" style={{ fontSize: '0.7rem' }}>{t}</span>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                <MagnitudeBar value={shift.magnitude} />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{shift.date}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Terms comparison table */}
        <div className="card">
          <div className="card-header">
            <h3>&#8644; Terminos: Antes vs Ahora</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>Termino</th>
                <th style={{ textAlign: 'center' }}>Antes</th>
                <th style={{ textAlign: 'center' }}>Ahora</th>
                <th>Tendencia</th>
              </tr>
            </thead>
            <tbody>
              {TERMS_COMPARISON.map(t => (
                <tr key={t.term}>
                  <td style={{ fontWeight: 500 }}>{t.term}</td>
                  <td style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>{t.before}</td>
                  <td style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>{t.after}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: '1rem', color: t.trend === 'up' ? '#4CAF50' : '#F44336' }}>
                        {t.trend === 'up' ? '\u2197' : '\u2198'}
                      </span>
                      <div className="progress-bar" style={{ maxWidth: 80 }}>
                        <div className="progress-fill" style={{
                          width: `${(t.after / 100) * 100}%`,
                          background: t.trend === 'up' ? '#4CAF50' : '#F44336'
                        }} />
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Timeline */}
        <div className="card">
          <div className="card-header">
            <h3>&#9787; Timeline de Cambios</h3>
          </div>
          <div className="timeline">
            {[...SHIFTS].reverse().map(shift => (
              <div key={shift.id} className="timeline-item">
                <div className="timeline-date">{shift.date}</div>
                <div className="timeline-content">
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{shift.topic}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                    Magnitud: <strong style={{ color: shift.magnitude >= 0.7 ? '#F44336' : '#FF9800' }}>
                      {(shift.magnitude * 100).toFixed(0)}%
                    </strong>
                    {' · '}
                    Direccion: <span style={{ color: shift.direction === 'positive' ? '#4CAF50' : '#F44336' }}>
                      {shift.direction === 'positive' ? 'Positiva' : 'Negativa'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
