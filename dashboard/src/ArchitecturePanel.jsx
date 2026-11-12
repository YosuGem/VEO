import React, { useState } from 'react';

/* ─────────────── Mock Data ─────────────── */
const MOTORS = [
  { name: 'Motor NEI', id: 'nei', version: '2.1.0', status: 'healthy', dependencies: ['motor_scraper', 'motor_validacion'], phase: 'produccion', description: 'Narrative Emergence Index - calcula el indice de emergencia narrativa' },
  { name: 'Motor Scraper', id: 'scraper', version: '2.0.3', status: 'healthy', dependencies: [], phase: 'produccion', description: 'Recoleccion de datos de multiples fuentes (12 activas)' },
  { name: 'Motor Narrativa', id: 'narrativa', version: '2.0.1', status: 'healthy', dependencies: ['motor_scraper'], phase: 'produccion', description: 'Deteccion y tracking de cambios en narrativas' },
  { name: 'Motor Validacion', id: 'validacion', version: '2.1.2', status: 'healthy', dependencies: ['motor_nei'], phase: 'produccion', description: 'Validacion dual (cientifico + esceptico) de hipotesis' },
  { name: 'Motor Prediccion', id: 'prediccion', version: '2.0.0', status: 'healthy', dependencies: ['motor_narrativa', 'motor_nei'], phase: 'produccion', description: 'Mercados de prediccion y simulacion Monte Carlo' },
  { name: 'Motor Alertas', id: 'alertas', version: '1.9.0', status: 'healthy', dependencies: ['motor_narrativa', 'motor_nei'], phase: 'produccion', description: 'Sistema de alertas por cascada y anomalias' },
  { name: 'HermesCommander', id: 'commander', version: '2.0.0', status: 'healthy', dependencies: ['*'], phase: 'produccion', description: 'UNICO punto de entrada - orquesta todos los motores' },
];

const LAWS = [
  { id: 1, text: 'Interfaz -> Commander: Toda comunicacion pasa por HermesCommander', active: true },
  { id: 2, text: 'Hipotesis -> Escenario -> Prediccion: Flujo obligatorio de datos', active: true },
  { id: 3, text: 'Validacion Dual: Cientifico + Esceptico para toda hipotesis', active: true },
  { id: 4, text: 'NEI como metrica unica de calidad narrativa', active: true },
  { id: 5, text: 'Ciclos autonomos: Reasoning, Forecast, Executive, Operations', active: true },
  { id: 6, text: 'Auditoria completa: Toda operacion queda registrada', active: true },
  { id: 7, text: 'Trust Score por motor: Transparencia en confiabilidad', active: true },
];

const PHASES = [
  { name: 'Diseno', status: 'completed' },
  { name: 'Auditoria', status: 'completed' },
  { name: 'Implementacion', status: 'completed' },
  { name: 'Produccion', status: 'current' },
];

/* ─────────────── ASCII Architecture ─────────────── */
function ArchDiagram() {
  return (
    <div className="arch-diagram">
      <div style={{ marginBottom: 8, fontWeight: 600, color: '#E0E0E0' }}>
        [VEO v2 - Arquitectura de Capas]
      </div>

      {/* Layer: Interfaces */}
      <div className="arch-layer" style={{ background: 'rgba(33,150,243,0.1)', borderColor: 'rgba(33,150,243,0.3)' }}>
        <span style={{ color: '#2196F3', minWidth: 100 }}>INTERFACES</span>
        <span style={{ color: '#aaa' }}>API REST + WebSocket</span>
        <span style={{ marginLeft: 'auto', color: '#aaa' }}>CLI Typer+Rich</span>
        <span style={{ marginLeft: 8, color: '#aaa' }}>Dashboard React</span>
      </div>

      <div className="arch-connector">&#9660; &#9660; &#9660;  [ Todas las interfaces ]  &#9660; &#9660; &#9660;</div>

      {/* Layer: Commander */}
      <div className="arch-layer command" style={{ background: 'rgba(76,175,80,0.1)', borderColor: 'rgba(76,175,80,0.3)' }}>
        <span style={{ color: '#4CAF50', minWidth: 100, fontWeight: 600 }}>COMMANDER</span>
        <span style={{ color: '#aaa' }}>HermesCommander (UNICO punto de entrada)</span>
      </div>

      <div className="arch-connector">&#9660; &#9660; &#9660;  [ Orquestacion ]  &#9660; &#9660; &#9660;</div>

      {/* Layer: Cycles */}
      <div className="arch-layer cycle" style={{ background: 'rgba(255,152,0,0.1)', borderColor: 'rgba(255,152,0,0.3)' }}>
        <span style={{ color: '#FF9800', minWidth: 100 }}>CYCLES</span>
        <span style={{ color: '#aaa' }}>Reasoning</span>
        <span style={{ color: '#aaa' }}>Forecast</span>
        <span style={{ color: '#aaa' }}>Executive</span>
        <span style={{ color: '#aaa' }}>Operations</span>
      </div>

      <div className="arch-connector">&#9660; &#9660; &#9660;  [ Procesamiento ]  &#9660; &#9660; &#9660;</div>

      {/* Layer: Motors */}
      <div className="arch-layer motor" style={{ background: 'rgba(156,39,176,0.1)', borderColor: 'rgba(156,39,176,0.3)' }}>
        <span style={{ color: '#9C27B0', minWidth: 100 }}>MOTORS</span>
        <span style={{ color: '#aaa' }}>NEI</span>
        <span style={{ color: '#aaa' }}>Scraper</span>
        <span style={{ color: '#aaa' }}>Narrativa</span>
        <span style={{ color: '#aaa' }}>Validacion</span>
        <span style={{ color: '#aaa' }}>Prediccion</span>
        <span style={{ color: '#aaa' }}>Alertas</span>
      </div>

      <div className="arch-connector">&#9660; &#9660; &#9660;  [ Persistencia ]  &#9660; &#9660; &#9660;</div>

      {/* Layer: Data */}
      <div className="arch-layer data" style={{ background: 'rgba(0,188,212,0.1)', borderColor: 'rgba(0,188,212,0.3)' }}>
        <span style={{ color: '#00BCD4', minWidth: 100 }}>DATA</span>
        <span style={{ color: '#aaa' }}>Base de Datos (solo via Commander)</span>
      </div>
    </div>
  );
}

/* ─────────────── Motor Registry ─────────────── */
function MotorRegistry({ motors }) {
  return (
    <div className="motor-table">
      <div className="motor-row header">
        <span>Motor</span>
        <span>Version</span>
        <span>Estado</span>
        <span>Dependencias</span>
      </div>
      {motors.map(m => (
        <div key={m.id} className="motor-row">
          <div>
            <div className="motor-name">{m.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{m.description}</div>
          </div>
          <span className="motor-version">{m.version}</span>
          <span>
            <span className="status-badge" style={{
              background: m.status === 'healthy' ? 'rgba(76,175,80,0.15)' : 'rgba(255,152,0,0.15)',
              color: m.status === 'healthy' ? '#4CAF50' : '#FF9800',
            }}>
              {m.status.toUpperCase()}
            </span>
          </span>
          <span className="motor-deps">
            {m.dependencies.length === 0 ? '-' : m.dependencies.map(d =>
              <span key={d} className="tag tag-blue" style={{ marginRight: 4, fontSize: '0.7rem' }}>{d.replace('motor_', '')}</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ─────────────── Governance Laws ─────────────── */
function GovernanceLaws({ laws }) {
  return (
    <div>
      {laws.map(law => (
        <div key={law.id} className="law-item">
          <span className="law-number">L{law.id}</span>
          <span className="law-text">{law.text}</span>
          <span className={`law-status ${law.active ? 'active' : ''}`}>
            {law.active ? 'ACTIVE' : 'INACTIVE'}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ─────────────── Phase Pipeline ─────────────── */
function PhasePipeline({ phases }) {
  return (
    <div className="phase-pipeline">
      {phases.map((p, i) => (
        <React.Fragment key={p.name}>
          <div className={`phase-step ${p.status}`}>
            {p.name}
          </div>
          {i < phases.length - 1 && <span className="phase-arrow">&#10132;</span>}
        </React.Fragment>
      ))}
    </div>
  );
}

/* ─────────────── Main Panel ─────────────── */
export default function ArchitecturePanel() {
  const [expandedMotor, setExpandedMotor] = useState(null);

  return (
    <div className="fade-in">
      <div className="page-title">&#9638; Arquitectura VEO v2</div>

      <div className="dashboard-grid-2">
        {/* Architecture Diagram */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9638; Diagrama de Arquitectura</h3>
            <span className="tag tag-blue">Capas</span>
          </div>
          <ArchDiagram />
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 12 }}>
            Arquitectura de capas de VEO v2. Interfaces &#8594; Commander &#8594; Cycles &#8594; Motors &#8594; Data.
            HermesCommander es el UNICO punto de entrada - nunca se accede a la DB directamente.
          </p>
        </div>

        {/* Motor Registry */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9874; Registro de Motores</h3>
            <span className="tag tag-purple">{MOTORS.length} motores</span>
          </div>
          <MotorRegistry motors={MOTORS} />
        </div>

        {/* Governance Laws */}
        <div className="card">
          <div className="card-header">
            <h3>&#9878; 7 Leyes de Gobernanza</h3>
            <span className="tag tag-green">{LAWS.filter(l => l.active).length}/{LAWS.length} activas</span>
          </div>
          <GovernanceLaws laws={LAWS} />
        </div>

        {/* Rules */}
        <div className="card">
          <div className="card-header">
            <h3>&#9881; Reglas Obligatorias</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              ['Interfaz', 'HermesCommander', 'Toda comunicacion pasa por el Commander', '#2196F3'],
              ['Hipotesis', 'Escenario', 'Toda hipotesis genera un escenario', '#4CAF50'],
              ['Escenario', 'Prediccion', 'Todo escenario genera una prediccion', '#FF9800'],
              ['DB', 'Solo via Commander', 'Nunca acceder a la DB directamente', '#F44336'],
            ].map(([from, to, desc, color]) => (
              <div key={from} style={{
                padding: '12px 16px',
                background: 'rgba(0,0,0,0.15)',
                borderRadius: 6,
                borderLeft: `3px solid ${color}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', fontWeight: 600, color }}>
                  <span>{from}</span>
                  <span style={{ color: 'var(--text-muted)' }}>&#10132;</span>
                  <span>{to}</span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4 }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Phase Pipeline */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>&#9654; Pipeline de Fases</h3>
            <span className="tag tag-green">En produccion</span>
          </div>
          <PhasePipeline phases={PHASES} />
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 12 }}>
            Fases de desarrollo: Diseno &#8594; Auditoria &#8594; Implementacion &#8594; Produccion.
            Todas las fases completadas, sistema operativo en produccion.
          </p>
        </div>
      </div>
    </div>
  );
}
