import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import DashboardOverview from './DashboardOverview';
import HypothesisPanel from './HypothesisPanel';
import PredictionMarket from './PredictionMarket';
import CausalGraph from './CausalGraph';
import ScenarioSimulator from './ScenarioSimulator';
import DiscoveryJournal from './DiscoveryJournal';
import NarrativeShift from './NarrativeShift';
import SystemHealthPanel from './SystemHealthPanel';
import ArchitecturePanel from './ArchitecturePanel';

/* ─────────────── WebSocket Hook ─────────────── */
function useWebSocket(url) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ws;
    let reconnectTimer;

    const connect = () => {
      try {
        ws = new WebSocket(url);

        ws.onopen = () => {
          setConnected(true);
          setError(null);
          // Subscribe to all channels
          ws.send(JSON.stringify({ accion: 'subscribe', channel: 'all' }));
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setLastMessage(data);
          } catch {
            setLastMessage({ tipo: 'raw', datos: event.data });
          }
        };

        ws.onclose = () => {
          setConnected(false);
          // Reconnect after 3 seconds
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = (e) => {
          setError('WebSocket error');
          setConnected(false);
        };
      } catch (e) {
        setError(e.message);
        setConnected(false);
      }
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [url]);

  return { connected, lastMessage, error };
}

/* ─────────────── Navigation items ─────────────── */
const NAV_ITEMS = [
  { path: '/', label: 'Vision General', icon: '\u263C' },           // ☼
  { path: '/hypothesis', label: 'Hipotesis', icon: '\u2047' },      // ⁇
  { path: '/market', label: 'Mercado', icon: '\u2606' },            // ☆
  { path: '/simulation', label: 'Simulacion', icon: '\u2699' },     // ⚙
  { path: '/graph', label: 'Grafo', icon: '\u25CB' },               // ○
  { path: '/journal', label: 'Diario', icon: '\u270E' },            // ✎
  { path: '/narrative', label: 'Narrativa', icon: '\u25B2' },       // ▲
  { path: '/system', label: 'Salud', icon: '\u2665' },              // ♥  (NEW V2)
  { path: '/architecture', label: 'Arquitectura', icon: '\u2638' }, // ☸  (NEW V2)
  { path: '/config', label: 'Config', icon: '\u2691' },             // ⚑
];

/* ─────────────── Sidebar Component ─────────────── */
function Sidebar({ mobileOpen, onClose }) {
  const location = useLocation();

  return (
    <>
      <div className={`sidebar-overlay${mobileOpen ? ' open' : ''}`} onClick={onClose} />
      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        <div className="sidebar-header">
          <span className="logo-icon" style={{ color: 'var(--accent-green)' }}>&#9670;</span>
          <span className="logo-text">VEO v2</span>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                'sidebar-nav-item' + (isActive ? ' active' : '')
              }
              onClick={() => {
                if (window.innerWidth <= 768) onClose();
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          VEO v2.0.4I &middot; HermesCommander
        </div>
      </aside>
    </>
  );
}

/* ─────────────── Header Component ─────────────── */
function Header({ wsConnected, onMenuToggle }) {
  return (
    <header className="app-header">
      <div className="app-header-left">
        <button className="menu-toggle" onClick={onMenuToggle} title="Menu">
          &#9776;
        </button>
        <span className="header-title">VEO v2</span>
      </div>
      <div className="header-status">
        <span
          className={`status-dot${wsConnected ? ' connected' : ' disconnected'}${wsConnected ? ' pulse' : ''}`}
        />
        <span>{wsConnected ? 'Conectado' : 'Conectando...'}</span>
        <span style={{ marginLeft: 8, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          WebSocket
        </span>
      </div>
    </header>
  );
}

/* ─────────────── Config Panel (datos reales de la API) ─────────────── */
function ConfigPanel() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/v2/system/config')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setConfig(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <h3>&#9874; Configuracion</h3>
      </div>
      <p style={{ color: 'var(--text-secondary)' }}>
        Panel de configuracion del sistema VEO v2. Datos obtenidos via API.
      </p>
      {loading && <p style={{ color: 'var(--text-muted)' }}>Cargando configuracion...</p>}
      {error && (
        <div style={{ color: '#FF9800', marginTop: 12, padding: 12, background: 'rgba(255,152,0,0.1)', borderRadius: 8 }}>
          <strong>Error:</strong> No se pudo obtener la configuracion del servidor.<br/>
          <span style={{ fontSize: '0.85rem' }}>{error}</span>
        </div>
      )}
      {config && (
        <div style={{ marginTop: 20 }}>
          <pre style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.2)', padding: 12, borderRadius: 8, overflow: 'auto', maxHeight: 400 }}>
            {JSON.stringify(config, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/* ─────────────── Main App ─────────────── */
function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { connected: wsConnected, lastMessage } = useWebSocket('ws://localhost:8000/ws');

  // Log WebSocket messages for debug
  useEffect(() => {
    if (lastMessage) {
      console.log('[VEO v2 WS]', lastMessage.tipo, lastMessage);
    }
  }, [lastMessage]);

  return (
    <div className="app-layout">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="main-content">
        <Header wsConnected={wsConnected} onMenuToggle={() => setMobileOpen(o => !o)} />
        <main className="page-content">
          <Routes>
            <Route path="/" element={<DashboardOverview wsMessage={lastMessage} />} />
            <Route path="/hypothesis" element={<HypothesisPanel wsMessage={lastMessage} />} />
            <Route path="/market" element={<PredictionMarket wsMessage={lastMessage} />} />
            <Route path="/simulation" element={<ScenarioSimulator wsMessage={lastMessage} />} />
            <Route path="/graph" element={<CausalGraph wsMessage={lastMessage} />} />
            <Route path="/journal" element={<DiscoveryJournal wsMessage={lastMessage} />} />
            <Route path="/narrative" element={<NarrativeShift wsMessage={lastMessage} />} />
            <Route path="/system" element={<SystemHealthPanel wsMessage={lastMessage} />} />
            <Route path="/architecture" element={<ArchitecturePanel wsMessage={lastMessage} />} />
            <Route path="/config" element={<ConfigPanel />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename="/dashboard">
      <AppLayout />
    </BrowserRouter>
  );
}
