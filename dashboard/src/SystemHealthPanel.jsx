import React, { useState, useEffect } from 'react';

const API_BASE = '';

/* ─────────────── Color Helpers ─────────────── */
const statusColor = (s) => {
  if (!s) return '#777';
  if (s === 'healthy' || s === 'running' || s === 'confirmed' || s === 'available') return '#4CAF50';
  if (s === 'idle') return '#2196F3';
  if (s === 'degraded' || s === 'pending' || s === 'mock') return '#FF9800';
  if (s === 'unhealthy' || s === 'error') return '#F44336';
  if (s === 'not_implemented') return '#9E9E9E';
  return '#777';
};

const gaugeAngle = (score) => (score / 100) * 360;

/* ─────────────── Component: Health Gauge ─────────────── */
function HealthGauge({ score, status }) {
  const color = statusColor(status);
  const angle = gaugeAngle(score || 0);

  return (
    <div className="health-gauge-container">
      <div className="health-gauge-circle" style={{ '--health-angle': `${angle}deg`, background: `conic-gradient(${color} 0deg ${angle}deg, #2A2A2A ${angle}deg 360deg)` }}>
        <div className="health-ginner">
          <div className="score-value" style={{ color }}>{score !== null ? score : '--'}</div>
          <div className="score-label">HEALTH</div>
        </div>
      </div>
      <div style={{ fontSize: '0.85rem', fontWeight: 600, color, textTransform: 'uppercase' }}>
        {status || 'unknown'}
      </div>
    </div>
  );
}

/* ─────────────── Component: Component Status ─────────────── */
function ComponentStatusGrid({ components }) {
  if (!components || Object.keys(components).length === 0) {
    return <p style={{ color: 'var(--text-muted)' }}>No hay datos de componentes disponibles.</p>;
  }
  return (
    <div className="component-grid">
      {Object.entries(components).map(([name, info]) => {
        const color = statusColor(info.status);
        const displayName = name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const details = [];
        if (info.latency_ms !== undefined && info.latency_ms !== null) details.push(`latency: ${info.latency_ms}ms`);
        if (info.connections !== undefined && info.connections !== null) details.push(`conns: ${info.connections}`);
        if (info.mode) details.push(`mode: ${info.mode}`);
        if (info.last_run) details.push(`last: ${info.last_run?.slice(11, 16)}`);
        if (info.sources_active !== undefined && info.sources_active !== null) details.push(`sources: ${info.sources_active}`);
        if (info.narratives_tracked !== undefined && info.narratives_tracked !== null) details.push(`narratives: ${info.narratives_tracked}`);
        if (info.queue_size !== undefined && info.queue_size !== null) details.push(`queue: ${info.queue_size}`);
        if (info.messages_sent !== undefined && info.messages_sent !== null) details.push(`msgs: ${info.messages_sent}`);
        if (info.note) details.push(info.note);

        return (
          <div key={name} className="component-card">
            <div className="component-semaforo" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
            <div className="component-info">
              <div className="component-name">{displayName}</div>
              <div className="component-detail">{details.join(' | ') || info.status || 'unknown'}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────── Component: Cycle Cards ─────────────── */
function CycleGrid({ cycles }) {
  const CYCLE_NAMES = {
    reasoning: 'Razonamiento',
    forecast: 'Pronostico',
    executive: 'Ejecutivo',
    operations: 'Operaciones',
  };
  const CYCLE_ICONS = {
    reasoning: '\u{1F9E0}',
    forecast: '\u{1F52E}',
    executive: '\u{1F3AF}',
    operations: '\u{2699}',
  };

  if (!cycles || Object.keys(cycles).length === 0) {
    return <p style={{ color: 'var(--text-muted)' }}>No hay datos de ciclos disponibles.</p>;
  }

  return (
    <div className="cycle-grid">
      {Object.entries(cycles).map(([id, info]) => {
        const color = statusColor(info.status);
        return (
          <div key={id} className="cycle-card">
            <div className="cycle-icon">{CYCLE_ICONS[id] || '?'}</div>
            <div className="cycle-name">{CYCLE_NAMES[id] || id}</div>
            <div className="cycle-status" style={{ color }}>{(info.status || 'unknown').toUpperCase()}</div>
            <div className="cycle-last-run">Last: {info.last_run ? info.last_run.slice(11, 16) : '--'}</div>
            <div className="cycle-last-run">Next: {info.next_run ? info.next_run.slice(11, 16) : '--'}</div>
            <div className="cycle-success">
              {info.success_rate !== null && info.success_rate !== undefined
                ? `${(info.success_rate * 100).toFixed(0)}% success`
                : 'Sin datos'}
            </div>
            {info.note && <div style={{ fontSize: '0.75rem', color: '#9E9E9E', marginTop: 4 }}>{info.note}</div>}
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────── Component: Realtime Metrics ─────────────── */
function RealtimeMetrics({ metrics }) {
  if (!metrics) {
    return <p style={{ color: 'var(--text-muted)' }}>No hay metricas disponibles.</p>;
  }

  const metricDefs = [
    { key: 'cpu_percent', label: 'CPU', color: '#2196F3', format: v => `${v.toFixed(1)}%`, max: 100 },
    { key: 'memory_percent', label: 'Memoria', color: '#4CAF50', format: v => `${v.toFixed(1)}%`, max: 100 },
    { key: 'disk_percent', label: 'Disco', color: '#FF9800', format: v => `${v.toFixed(1)}%`, max: 100 },
  ];

  return (
    <div className="rt-metrics-grid">
      {metricDefs.map(m => {
        const val = metrics[m.key];
        if (val === undefined || val === null) return null;
        return (
          <div key={m.key} className="rt-metric-card">
            <div className="rt-metric-value" style={{ color: m.color }}>{m.format(val)}</div>
            <div className="rt-metric-label">{m.label}</div>
            <div className="rt-metric-bar">
              <div className="rt-metric-fill" style={{ width: `${(val / m.max) * 100}%`, background: m.color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────── Component: Event Feed ─────────────── */
function EventFeed({ events }) {
  const levelColor = (l) => {
    if (l === 'warn') return '#FF9800';
    if (l === 'error') return '#F44336';
    return '#2196F3';
  };

  if (!events || events.length === 0) {
    return <p style={{ color: 'var(--text-muted)' }}>No hay eventos recientes. Los eventos aparecen cuando ocurren operaciones en el sistema (crear hipotesis, validar, etc.).</p>;
  }

  return (
    <div className="event-feed">
      {events.map((e, i) => (
        <div key={i} className="event-item">
          <span className="event-icon" style={{ color: levelColor(e.level) }}>{e.icon || '\u26A1'}</span>
          <div className="event-content">
            <div className="event-message">{e.message || e.tipo || 'Evento'}</div>
            <div className="event-meta">{e.component || e.datos?.component || 'sistema'} &middot; {e.time || e.timestamp?.slice(11, 16) || 'ahora'}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─────────────── Component: Error Box ─────────────── */
function ErrorBox({ message, onRetry }) {
  return (
    <div style={{ color: '#FF9800', padding: 16, background: 'rgba(255,152,0,0.1)', borderRadius: 8, marginBottom: 16 }}>
      <strong>Error al cargar datos:</strong> {message}
      {onRetry && (
        <button onClick={onRetry} style={{ marginLeft: 12, padding: '4px 12px', cursor: 'pointer' }}>
          Reintentar
        </button>
      )}
    </div>
  );
}

/* ─────────────── Main Panel ─────────────── */
export default function SystemHealthPanel({ wsMessage }) {
  const [health, setHealth] = useState(null);
  const [status, setStatus] = useState(null);
  const [cycles, setCycles] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState({ health: true, status: true, cycles: true });
  const [errors, setErrors] = useState({});

  const fetchData = async () => {
    setLoading({ health: true, status: true, cycles: true });
    setErrors({});

    // Health
    try {
      const r = await fetch(`${API_BASE}/api/v2/system/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setHealth(data);
    } catch (err) {
      setErrors(prev => ({ ...prev, health: err.message }));
    } finally {
      setLoading(prev => ({ ...prev, health: false }));
    }

    // Status
    try {
      const r = await fetch(`${API_BASE}/api/v2/system/status`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setStatus(data);
    } catch (err) {
      setErrors(prev => ({ ...prev, status: err.message }));
    } finally {
      setLoading(prev => ({ ...prev, status: false }));
    }

    // Cycles
    try {
      const r = await fetch(`${API_BASE}/api/v2/cycles/status`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setCycles(data.cycles || {});
    } catch (err) {
      setErrors(prev => ({ ...prev, cycles: err.message }));
    } finally {
      setLoading(prev => ({ ...prev, cycles: false }));
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh cada 30s
    return () => clearInterval(interval);
  }, []);

  // Procesar eventos del WebSocket
  useEffect(() => {
    if (!wsMessage) return;
    const tipo = wsMessage.tipo;
    if (!tipo || tipo === 'heartbeat' || tipo === 'conexion' || tipo === 'historial') return;

    const newEvent = {
      icon: tipo === 'hipotesis_nueva' ? '\u{1F4A1}' :
            tipo === 'validacion_completada' ? '\u2705' :
            tipo === 'mercado_nuevo' ? '\u{1F4C8}' :
            tipo === 'trade' ? '\u{1F4B0}' :
            tipo === 'mercado_resuelto' ? '\u{1F3C6}' :
            tipo === 'cycle_triggered' ? '\u{1F504}' :
            '\u26A1',
      message: wsMessage.datos?.mensaje || `${tipo}: ${JSON.stringify(wsMessage.datos || {})}`,
      component: wsMessage.datos?.component || tipo,
      time: new Date().toLocaleTimeString(),
      level: 'info',
      ...wsMessage,
    };

    setEvents(prev => [newEvent, ...prev].slice(0, 50));
  }, [wsMessage]);

  const anyLoading = loading.health || loading.status || loading.cycles;

  return (
    <div className="fade-in">
      <div className="page-title">&#9829; Salud del Sistema</div>

      {anyLoading && (
        <div style={{ color: 'var(--text-muted)', marginBottom: 12, fontSize: '0.9rem' }}>
          Cargando datos del sistema...
        </div>
      )}

      <div className="dashboard-grid-2">
        {/* Health Score Gauge */}
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="card-header">
            <h3>&#9788; Health Score Global</h3>
            {health && (
              <span className={`tag tag-${health.status === 'healthy' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}`}>
                {(health.status || 'unknown').toUpperCase()}
              </span>
            )}
          </div>
          {errors.health ? (
            <ErrorBox message={errors.health} onRetry={fetchData} />
          ) : (
            <>
              <HealthGauge score={health?.health_score} status={health?.status} />
              {health?.timestamp && (
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 8 }}>
                  Actualizado: {new Date(health.timestamp).toLocaleTimeString()}
                </p>
              )}
            </>
          )}
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 12 }}>
            Health score basado en el estado real de los componentes disponibles.
          </p>
        </div>

        {/* System Status */}
        <div className="card">
          <div className="card-header">
            <h3>&#128200; Estado del Sistema</h3>
            <div className="ws-indicator">
              <span className="ws-dot" />
              <span>API</span>
            </div>
          </div>
          {errors.status ? (
            <ErrorBox message={errors.status} onRetry={fetchData} />
          ) : status ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-color)' }}>
                <span>Version</span>
                <strong style={{ color: 'var(--accent-blue)' }}>{status.version || '--'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-color)' }}>
                <span>Modo</span>
                <strong style={{ color: 'var(--accent-green)' }}>{status.mode || '--'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-color)' }}>
                <span>Commander</span>
                <strong style={{ color: status.commander_available ? '#4CAF50' : '#FF9800' }}>
                  {status.commander_available ? 'Disponible' : 'Mock fallback'}
                </strong>
              </div>
              {status.components && Object.entries(status.components).map(([name, info]) => (
                <div key={name} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: '0.8rem' }}>
                  <span>{name.replace(/_/g, ' ')}</span>
                  <span style={{ color: statusColor(info.status) }}>{info.status} {info.note ? `(${info.note})` : ''}</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>Sin datos de estado.</p>
          )}
        </div>

        {/* Component Status */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9874; Estado de Componentes</h3>
            <span className="tag tag-blue">{health?.components ? Object.keys(health.components).length : 0} componentes</span>
          </div>
          {errors.health ? (
            <ErrorBox message={errors.health} onRetry={fetchData} />
          ) : (
            <ComponentStatusGrid components={health?.components} />
          )}
        </div>

        {/* Cycles */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#8635; Estado de los 4 Ciclos</h3>
            <span className="tag tag-blue">Via HermesCommander</span>
          </div>
          {errors.cycles ? (
            <ErrorBox message={errors.cycles} onRetry={fetchData} />
          ) : (
            <CycleGrid cycles={cycles} />
          )}
        </div>

        {/* Event Feed */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#128227; Eventos en Tiempo Real (WebSocket)</h3>
            <span className="tag tag-blue">{events.length} eventos</span>
          </div>
          <EventFeed events={events} />
        </div>
      </div>
    </div>
  );
}
