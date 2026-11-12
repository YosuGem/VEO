import React, { useState, useEffect } from 'react';
import {
  ComposedChart, Line, Bar, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const API_BASE = '';

/* ─────────────── WS Indicator ─────────────── */
function WSIndicator({ message }) {
  if (!message) return null;
  const typeColors = {
    hipotesis_nueva: '#2196F3',
    validacion_completada: '#4CAF50',
    mercado_nuevo: '#FF9800',
    trade: '#9C27B0',
    mercado_resuelto: '#00BCD4',
    alerta: '#F44336',
    narrativa_cambio: '#FF9800',
    cycle_triggered: '#4CAF50',
    backup_created: '#2196F3',
    default: '#777',
  };
  const color = typeColors[message.tipo] || typeColors.default;
  return (
    <div style={{
      position: 'fixed', bottom: 12, right: 12,
      background: '#1E1E1E', border: `1px solid ${color}`,
      borderRadius: 6, padding: '8px 12px', fontSize: '0.75rem',
      color, zIndex: 1000, maxWidth: 280,
      boxShadow: `0 2px 8px ${color}33`, animation: 'fadeIn 0.3s ease',
    }}>
      <strong>WS:</strong> {message.tipo} &middot; {new Date(message.timestamp).toLocaleTimeString()}
    </div>
  );
}

/* ─────────────── Custom Tooltip ─────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload) return null;
  return (
    <div style={{
      background: '#1E1E1E', border: '1px solid #333', borderRadius: 6,
      padding: '10px 14px', fontSize: '0.8rem', boxShadow: '0 4px 16px rgba(0,0,0,0.5)'
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </div>
      ))}
    </div>
  );
}

/* ─────────────── Metric Card ─────────────── */
function MetricCard({ label, value, change, positive, loading }) {
  if (loading) {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <div className="metric-value" style={{ color: 'var(--text-muted)' }}>--</div>
        <div className="metric-label">{label}</div>
        <div className="metric-change" style={{ color: 'var(--text-muted)' }}>Cargando...</div>
      </div>
    );
  }
  if (value === null || value === undefined) {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <div className="metric-value" style={{ color: 'var(--text-muted)' }}>--</div>
        <div className="metric-label">{label}</div>
        <div className="metric-change" style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Sin datos</div>
      </div>
    );
  }
  return (
    <div className="card" style={{ textAlign: 'center' }}>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {change && (
        <div className={`metric-change${positive ? ' positive' : ' negative'}`}>
          {positive ? '\u2191' : '\u2193'} {change}
        </div>
      )}
    </div>
  );
}

/* ─────────────── Alert Item ─────────────── */
function AlertItem({ alert }) {
  const severity = alert.severity || alert.nivel || 'medium';
  return (
    <div className={`alert-card severity-${severity}`}>
      <span className="alert-icon">
        {severity === 'high' || severity === 'alta' ? '\u26A0' : severity === 'medium' || severity === 'media' ? '\u25CF' : '\u2139'}
      </span>
      <div className="alert-content">
        <div className="alert-title">{alert.msg || alert.mensaje || JSON.stringify(alert)}</div>
        <div className="alert-meta">{alert.time || alert.fecha || 'Sin fecha'}</div>
      </div>
      <span className={`status-badge severity-${severity}`}>
        {severity.toUpperCase()}
      </span>
    </div>
  );
}

/* ─────────────── Service Status from Health API ─────────────── */
function ServiceStatusGrid({ health, loading, error }) {
  if (loading) {
    return <p style={{ color: 'var(--text-muted)' }}>Cargando estado de servicios...</p>;
  }
  if (error) {
    return <p style={{ color: '#FF9800' }}>Error: {error}</p>;
  }
  if (!health || !health.components) {
    return <p style={{ color: 'var(--text-muted)' }}>No hay datos de servicios. El health check no ha devuelto componentes.</p>;
  }

  const components = health.components;
  return (
    <div>
      {Object.entries(components).map(([name, info]) => {
        const status = info.status || 'unknown';
        const isOk = status === 'healthy' || status === 'ok' || status === 'running';
        return (
          <div key={name} className="service-status">
            <span className="status-dot" style={{
              background: isOk ? '#4CAF50' : '#FF9800',
              boxShadow: isOk ? '0 0 6px #4CAF50' : '0 0 6px #FF9800'
            }} />
            <span className="service-name">{name.replace(/_/g, ' ')}</span>
            <span className="status-badge" style={{
              background: isOk ? 'rgba(76,175,80,0.15)' : 'rgba(255,152,0,0.15)',
              color: isOk ? '#4CAF50' : '#FF9800',
            }}>
              {status.toUpperCase()}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────── Main Panel ─────────────── */
export default function DashboardOverview({ wsMessage }) {
  const [hipotesis, setHipotesis] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState({ hipotesis: true, alertas: true, health: true });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    // Cargar hipotesis reales
    fetch(`${API_BASE}/api/v1/hipotesis`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setHipotesis(Array.isArray(data) ? data : []);
        setLoading(prev => ({ ...prev, hipotesis: false }));
      })
      .catch(err => {
        setErrors(prev => ({ ...prev, hipotesis: err.message }));
        setLoading(prev => ({ ...prev, hipotesis: false }));
      });

    // Cargar alertas reales
    fetch(`${API_BASE}/api/v1/alertas`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setAlertas(Array.isArray(data) ? data : []);
        setLoading(prev => ({ ...prev, alertas: false }));
      })
      .catch(err => {
        setErrors(prev => ({ ...prev, alertas: err.message }));
        setLoading(prev => ({ ...prev, alertas: false }));
      });

    // Cargar health real
    fetch(`${API_BASE}/api/v2/system/health`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        setHealth(data);
        setLoading(prev => ({ ...prev, health: false }));
      })
      .catch(err => {
        setErrors(prev => ({ ...prev, health: err.message }));
        setLoading(prev => ({ ...prev, health: false }));
      });
  }, []);

  // Calcular metricas reales
  const hipActivas = hipotesis.filter(h => h.estado === 'activa' || h.estado === 'pendiente').length;
  const hipConfirmadas = hipotesis.filter(h => h.estado === 'confirmada' || h.estado === 'confirmado').length;
  const hipRefutadas = hipotesis.filter(h => h.estado === 'refutada' || h.estado === 'refutado').length;
  const neiPromedio = hipotesis.length > 0
    ? (hipotesis.reduce((sum, h) => sum + (h.nei || 0), 0) / hipotesis.length).toFixed(2)
    : null;

  const metrics = [
    { label: 'Hipotesis Totales', value: hipotesis.length || null, loading: loading.hipotesis },
    { label: 'Hipotesis Activas', value: hipActivas || null, loading: loading.hipotesis },
    { label: 'Confirmadas', value: hipConfirmadas || null, loading: loading.hipotesis },
    { label: 'Refutadas', value: hipRefutadas || null, loading: loading.hipotesis },
    { label: 'NEI Promedio', value: neiPromedio, loading: loading.hipotesis },
    { label: 'Alertas', value: alertas.length || null, loading: loading.alertas },
  ];

  // Datos del grafico NEI (solo si hay hipotesis con fecha)
  const neiData = hipotesis
    .filter(h => h.nei !== undefined && h.nei !== null)
    .slice(-30)
    .map((h, i) => ({
      dia: h.id || `H${i}`,
      nei: h.nei,
      confianza: h.confianza || h.confidence || 0.5,
    }));

  // Feed de actividad real (basado en WebSocket)
  const [activityFeed, setActivityFeed] = useState([]);
  useEffect(() => {
    if (!wsMessage) return;
    const tipo = wsMessage.tipo;
    if (!tipo || tipo === 'heartbeat' || tipo === 'conexion' || tipo === 'historial') return;

    const newItem = {
      icon: tipo === 'hipotesis_nueva' ? '\u{1F4A1}' :
            tipo === 'validacion_completada' ? '\u2705' :
            tipo === 'mercado_nuevo' ? '\u{1F4C8}' :
            tipo === 'trade' ? '\u{1F4B0}' :
            tipo === 'mercado_resuelto' ? '\u{1F3C6}' :
            tipo === 'cycle_triggered' ? '\u{1F504}' :
            '\u26A1',
      text: wsMessage.datos?.mensaje || `${tipo}: ${JSON.stringify(wsMessage.datos || {})}`,
      time: new Date().toLocaleTimeString(),
    };
    setActivityFeed(prev => [newItem, ...prev].slice(0, 20));
  }, [wsMessage]);

  return (
    <div className="fade-in">
      <div className="page-title">&#9788; Vision General</div>

      {/* Metric cards */}
      <div className="dashboard-grid" style={{ marginBottom: 20 }}>
        {metrics.map((m, i) => (
          <MetricCard key={i} {...m} />
        ))}
      </div>

      <div className="dashboard-grid-2">
        {/* NEI Chart */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#128200; Evolucion NEI y Confianza</h3>
            <span className="tag tag-blue">{neiData.length} puntos</span>
          </div>
          {neiData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={neiData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="dia" stroke="#777" fontSize={11} tickLine={false} />
                <YAxis yAxisId="left" stroke="#777" fontSize={11} tickLine={false} domain={[0, 1]} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
                <Line yAxisId="left" type="monotone" dataKey="nei" name="NEI" stroke="#4CAF50" strokeWidth={2} dot={false} />
                <Line yAxisId="left" type="monotone" dataKey="confianza" name="Confianza" stroke="#2196F3" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <p>No hay datos de NEI disponibles.</p>
              <p style={{ fontSize: '0.85rem', marginTop: 8 }}>Las hipotesis creadas apareceran aqui automaticamente.</p>
            </div>
          )}
        </div>

        {/* Alerts */}
        <div className="card">
          <div className="card-header">
            <h3>&#9888; Alertas</h3>
            <span className="status-badge severity-high">{alertas.length}</span>
          </div>
          {loading.alertas ? (
            <p style={{ color: 'var(--text-muted)' }}>Cargando alertas...</p>
          ) : alertas.length > 0 ? (
            alertas.map((a, i) => <AlertItem key={i} alert={a} />)
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>No hay alertas activas.</p>
          )}
        </div>

        {/* Service Status from real Health API */}
        <div className="card">
          <div className="card-header">
            <h3>&#9881; Estado de Servicios</h3>
          </div>
          <ServiceStatusGrid health={health} loading={loading.health} error={errors.health} />
        </div>

        {/* Activity Feed */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#8635; Actividad en Tiempo Real (WebSocket)</h3>
            {wsMessage && <span className="tag tag-green" style={{ fontSize: '0.7rem' }}>WS CONECTADO</span>}
          </div>
          {activityFeed.length > 0 ? (
            <div className="activity-feed">
              {activityFeed.map((item, i) => (
                <div key={i} className="activity-item">
                  <span className="activity-icon">{item.icon}</span>
                  <span className="activity-text">{item.text}</span>
                  <span className="activity-time">{item.time}</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>
              No hay actividad reciente. Los eventos apareceran cuando se realicen operaciones
              (crear hipotesis, validar, trade, etc.).
            </p>
          )}
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
