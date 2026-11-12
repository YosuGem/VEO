import React, { useState, useEffect, useMemo } from 'react';

const API_BASE = '';

/* ─────────────── Color helpers ─────────────── */
const confidenceColor = (v) => {
  if (v === undefined || v === null) return '#777';
  if (v >= 0.7) return '#4CAF50';
  if (v >= 0.45) return '#FF9800';
  return '#F44336';
};

const statusBadgeClass = (s) => {
  if (!s) return 'status-pending';
  const sl = s.toLowerCase();
  if (sl === 'activa' || sl === 'active' || sl === 'pendiente') return 'status-active';
  if (sl === 'confirmada' || sl === 'confirmado' || sl === 'confirmed') return 'status-confirmed';
  if (sl === 'refutada' || sl === 'refutado' || sl === 'refuted') return 'status-refuted';
  return 'status-pending';
};

/* ─────────────── Confidence Bar ─────────────── */
function ConfidenceBar({ value }) {
  const color = confidenceColor(value);
  const pct = value !== undefined && value !== null ? (value * 100).toFixed(0) : '--';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 120 }}>
      <div className="progress-bar" style={{ flex: 1 }}>
        <div className="progress-fill" style={{ width: `${(value || 0) * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.75rem', fontWeight: 600, color, minWidth: 36 }}>
        {pct}%
      </span>
    </div>
  );
}

/* ─────────────── WS Indicator ─────────────── */
function WSIndicator({ message }) {
  if (!message) return null;
  return (
    <div style={{ position: 'fixed', bottom: 12, right: 12, background: '#1E1E1E', border: '1px solid var(--accent-green)', borderRadius: 6, padding: '8px 12px', fontSize: '0.75rem', color: '#4CAF50', zIndex: 1000, animation: 'fadeIn 0.3s ease' }}>
      <strong>WS:</strong> {message.tipo}
    </div>
  );
}

/* ─────────────── Main Component ─────────────── */
export default function HypothesisPanel({ wsMessage }) {
  const [hipotesis, setHipotesis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('todas');
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/hipotesis`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setHipotesis(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Actualizar lista cuando llega un evento WS de nueva hipotesis
  useEffect(() => {
    if (!wsMessage || wsMessage.tipo !== 'hipotesis_nueva') return;
    fetch(`${API_BASE}/api/v1/hipotesis`)
      .then(r => r.ok ? r.json() : [])
      .then(data => setHipotesis(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, [wsMessage]);

  const filtered = useMemo(() => {
    if (statusFilter === 'todas') return hipotesis;
    return hipotesis.filter(h => {
      const s = (h.estado || h.status || '').toLowerCase();
      return s === statusFilter || (statusFilter === 'activa' && (s === 'activa' || s === 'active' || s === 'pendiente'));
    });
  }, [hipotesis, statusFilter]);

  const avgNEI = hipotesis.length > 0
    ? hipotesis.reduce((s, h) => s + (h.nei || h.confianza || h.confidence || 0), 0) / hipotesis.length
    : 0;

  const handleValidate = async (id) => {
    try {
      const r = await fetch(`${API_BASE}/api/v1/hipotesis/${id}/validar`, { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const updated = await r.json();
      setHipotesis(prev => prev.map(h => h.id === id ? updated : h));
    } catch (err) {
      alert(`Error al validar: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="fade-in">
        <div className="page-title">&#8265; Panel de Hipotesis</div>
        <p style={{ color: 'var(--text-muted)' }}>Cargando hipotesis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fade-in">
        <div className="page-title">&#8265; Panel de Hipotesis</div>
        <div style={{ color: '#FF9800', padding: 16, background: 'rgba(255,152,0,0.1)', borderRadius: 8 }}>
          <strong>Error al cargar hipotesis:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="page-title">&#8265; Panel de Hipotesis</div>

      {/* Filters */}
      <div className="filters-bar">
        <div className="filter-group">
          <label>Estado:</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="todas">Todas</option>
            <option value="activa">Activas</option>
            <option value="confirmada">Confirmadas</option>
            <option value="refutada">Refutadas</option>
            <option value="pendiente">Pendientes</option>
          </select>
        </div>
        <div className="filter-group" style={{ marginLeft: 'auto' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {filtered.length} de {hipotesis.length} hipotesis
          </span>
        </div>
      </div>

      <div className="dashboard-grid-2">
        {/* Hypothesis list */}
        <div style={{ gridColumn: '1 / -1' }}>
          {hipotesis.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40 }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>No hay hipotesis registradas.</p>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 8 }}>
                Crea una hipotesis via API o CLI para verla aqui.
              </p>
            </div>
          ) : (
            filtered.map(h => (
              <div key={h.id} className="expandable">
                <div className="expandable-header" onClick={() => setExpanded(expanded === h.id ? null : h.id)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', flex: 1 }}>
                    <strong style={{ color: 'var(--accent-blue)', fontSize: '0.85rem' }}>{h.id}</strong>
                    <span style={{ fontSize: '0.9rem', flex: 1, minWidth: 200 }}>{h.texto || h.text || 'Sin texto'}</span>
                    <span className={`status-badge ${statusBadgeClass(h.estado || h.status)}`}>
                      {(h.estado || h.status || 'PENDIENTE').toUpperCase()}
                    </span>
                    {h.tags && h.tags[0] && <span className="tag tag-blue">{h.tags[0]}</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginLeft: 16 }}>
                    <ConfidenceBar value={h.nei || h.confianza || h.confidence} />
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {(h.evidencias || h.evidenceCount || 0)} evidencias
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {expanded === h.id ? '\u25B2' : '\u25BC'}
                    </span>
                  </div>
                </div>
                {expanded === h.id && (
                  <div className="expandable-body">
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600 }}>
                        Detalle:
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                        <p><strong>ID:</strong> {h.id}</p>
                        <p><strong>Texto:</strong> {h.texto || h.text}</p>
                        <p><strong>Confianza:</strong> {((h.confianza || h.confidence || 0) * 100).toFixed(1)}%</p>
                        <p><strong>NEI:</strong> {h.nei !== undefined ? h.nei.toFixed(2) : 'N/A'}</p>
                        <p><strong>Estado:</strong> {h.estado || h.status || 'pendiente'}</p>
                        <p><strong>Evidencias:</strong> {h.evidencias || 0}</p>
                        <p><strong>Creador:</strong> {h.creador || 'N/A'}</p>
                        <p><strong>Fecha:</strong> {h.fecha_creacion || 'N/A'}</p>
                      </div>
                    </div>

                    {(h.cientifico || h.esceptico) && (
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600 }}>
                          Validacion:
                        </div>
                        {h.cientifico && (
                          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                            <strong>Cientifico:</strong> {h.cientifico.veredicto} (score: {h.cientifico.score})
                          </p>
                        )}
                        {h.esceptico && (
                          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                            <strong>Esceptico:</strong> {h.esceptico.veredicto} (score: {h.esceptico.score})
                          </p>
                        )}
                      </div>
                    )}

                    <button className="btn-primary btn-small" onClick={() => handleValidate(h.id)}>
                      &#10003; Validar (Dual Source)
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* NEI Summary */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9733; NEI Score del Sistema</h3>
            <span className="tag tag-green">{(avgNEI * 100).toFixed(0)}% promedio</span>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
            El NEI (Narrative Emergence Index) mide la calidad promedio de todas las hipotesis.
          </p>
          {hipotesis.length > 0 ? (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12, marginTop: 16
            }}>
              {[
                ['Activas', hipotesis.filter(h => ['activa','active','pendiente'].includes((h.estado||h.status||'').toLowerCase())).length, 'var(--accent-green)'],
                ['Confirmadas', hipotesis.filter(h => ['confirmada','confirmado','confirmed'].includes((h.estado||h.status||'').toLowerCase())).length, 'var(--accent-blue)'],
                ['Refutadas', hipotesis.filter(h => ['refutada','refutado','refuted'].includes((h.estado||h.status||'').toLowerCase())).length, 'var(--accent-red)'],
                ['Pendientes', hipotesis.filter(h => ['pendiente','pending'].includes((h.estado||h.status||'').toLowerCase())).length, 'var(--accent-orange)'],
              ].map(([label, count, color]) => (
                <div key={label} style={{ textAlign: 'center', padding: '10px', background: 'rgba(0,0,0,0.15)', borderRadius: 6 }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{count}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>No hay hipotesis para calcular NEI.</p>
          )}
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
