import React, { useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

/* ─────────────── Mock Data ─────────────── */
const MARKETS = [
  {
    id: 'MP-08', name: 'IA Generativa: regulacion UE antes de julio 2024',
    volume: 45230, scenarios: [
      { name: 'Si', price: 0.72, color: '#4CAF50' },
      { name: 'No', price: 0.28, color: '#F44336' },
      { name: 'Parcial', price: 0.45, color: '#FF9800' },
    ],
    history: Array.from({ length: 20 }, (_, i) => ({
      dia: `D${i + 1}`, Si: 0.5 + Math.sin(i * 0.4) * 0.2 + Math.random() * 0.1,
      No: 0.5 - Math.sin(i * 0.4) * 0.2 + Math.random() * 0.1, Parcial: 0.35 + Math.random() * 0.2
    })),
  },
  {
    id: 'MP-09', name: 'Fed baja tipos en marzo 2024',
    volume: 89100, scenarios: [
      { name: 'Si', price: 0.35, color: '#4CAF50' },
      { name: 'No', price: 0.65, color: '#F44336' },
    ],
    history: Array.from({ length: 20 }, (_, i) => ({
      dia: `D${i + 1}`, Si: 0.45 - i * 0.01 + Math.random() * 0.08,
      No: 0.55 + i * 0.01 - Math.random() * 0.08
    })),
  },
  {
    id: 'MP-10', name: 'Open-source alcanza paridad con GPT-4 (LMSYS)',
    volume: 32150, scenarios: [
      { name: 'Si', price: 0.58, color: '#4CAF50' },
      { name: 'No', price: 0.42, color: '#F44336' },
      { name: 'Empate', price: 0.20, color: '#FF9800' },
    ],
    history: Array.from({ length: 20 }, (_, i) => ({
      dia: `D${i + 1}`, Si: 0.35 + i * 0.015 + Math.random() * 0.05,
      No: 0.65 - i * 0.015 - Math.random() * 0.05, Empate: 0.15 + Math.random() * 0.1
    })),
  },
  {
    id: 'MP-11', name: 'Crisis de deuda corporativa en China',
    volume: 67800, scenarios: [
      { name: 'Si', price: 0.41, color: '#4CAF50' },
      { name: 'No', price: 0.59, color: '#F44336' },
    ],
    history: Array.from({ length: 20 }, (_, i) => ({
      dia: `D${i + 1}`, Si: 0.3 + Math.sin(i * 0.3) * 0.15 + Math.random() * 0.1,
      No: 0.7 - Math.sin(i * 0.3) * 0.15 - Math.random() * 0.1
    })),
  },
];

const RECENT_TRADES = [
  { market: 'MP-08', scenario: 'Si', amount: 500, price: 0.72, user: 'Trader_A', time: '2m ago' },
  { market: 'MP-09', scenario: 'No', amount: 1200, price: 0.65, user: 'Oraculo22', time: '5m ago' },
  { market: 'MP-10', scenario: 'Si', amount: 300, price: 0.58, user: 'BayesFan', time: '8m ago' },
  { market: 'MP-08', scenario: 'Parcial', amount: 750, price: 0.45, user: 'HedgeMax', time: '12m ago' },
  { market: 'MP-11', scenario: 'No', amount: 2000, price: 0.59, user: 'MacroView', time: '18m ago' },
  { market: 'MP-09', scenario: 'Si', amount: 450, price: 0.35, user: 'DoveHunter', time: '25m ago' },
  { market: 'MP-10', scenario: 'No', amount: 600, price: 0.42, user: 'GPTSkeptic', time: '32m ago' },
];

const TRADER_RANKING = [
  { rank: 1, name: 'Oraculo22', pnl: 12450, accuracy: 78, trades: 342 },
  { rank: 2, name: 'BayesFan', pnl: 10200, accuracy: 74, trades: 289 },
  { rank: 3, name: 'HedgeMax', pnl: 8950, accuracy: 71, trades: 198 },
  { rank: 4, name: 'MacroView', pnl: 7600, accuracy: 69, trades: 267 },
  { rank: 5, name: 'NarrativaPro', pnl: 6540, accuracy: 67, trades: 310 },
];

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
        <div key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed(3)}</div>
      ))}
    </div>
  );
}

/* ─────────────── Price Bar ─────────────── */
function PriceBar({ scenario }) {
  return (
    <div className="price-bar-row">
      <span className="price-bar-label">{scenario.name}</span>
      <div className="price-bar-track">
        <div className="price-bar-fill" style={{ width: `${scenario.price * 100}%`, background: scenario.color }}>
          {(scenario.price * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
}

/* ─────────────── Market Card ─────────────── */
function MarketCard({ market, selected, onSelect }) {
  const [buyScenario, setBuyScenario] = useState(market.scenarios[0].name);
  const [buyAmount, setBuyAmount] = useState('');

  return (
    <div className="card" style={{ cursor: 'pointer', border: selected ? '1px solid var(--accent-blue)' : undefined }}
      onClick={() => onSelect(market.id)}>
      <div className="card-header">
        <div>
          <strong style={{ color: 'var(--accent-blue)', fontSize: '0.85rem' }}>{market.id}</strong>
          <div style={{ fontSize: '0.9rem', marginTop: 2 }}>{market.name}</div>
        </div>
        <span className="tag tag-blue">Vol: ${market.volume.toLocaleString()}</span>
      </div>

      <div className="price-bar-container" style={{ marginBottom: 14 }}>
        {market.scenarios.map(s => <PriceBar key={s.name} scenario={s} />)}
      </div>

      {selected && (
        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 12 }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontWeight: 600 }}>
            Comprar participacion:
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Escenario</label>
              <select value={buyScenario} onChange={e => setBuyScenario(e.target.value)} onClick={e => e.stopPropagation()}>
                {market.scenarios.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Cantidad ($)</label>
              <input type="number" value={buyAmount} onChange={e => setBuyAmount(e.target.value)}
                placeholder="0" onClick={e => e.stopPropagation()} />
            </div>
            <button className="btn-success btn-small" onClick={e => {
              e.stopPropagation();
              console.log(`[SOIS] Trade: ${market.id} / ${buyScenario} / $${buyAmount}`);
            }}>
              &#9654; Comprar
            </button>
          </div>
        </div>
      )}
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

export default function PredictionMarket({ wsMessage }) {
  const [selectedMarket, setSelectedMarket] = useState('MP-08');

  const activeMarket = MARKETS.find(m => m.id === selectedMarket);

  return (
    <div className="fade-in">
      <div className="page-title">&#9733; Mercado de Predicciones</div>

      <div className="dashboard-grid-2">
        {/* Markets list */}
        <div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 10, fontWeight: 600 }}>
            Mercados Abiertos ({MARKETS.length})
          </div>
          {MARKETS.map(m => (
            <div key={m.id} style={{ marginBottom: 10 }}>
              <MarketCard
                market={m}
                selected={selectedMarket === m.id}
                onSelect={setSelectedMarket}
              />
            </div>
          ))}
        </div>

        <div>
          {/* Price evolution chart */}
          {activeMarket && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <h3>&#128200; {activeMarket.id} - Evolucion de Precios</h3>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={activeMarket.history}>
                  <defs>
                    {activeMarket.scenarios.map(s => (
                      <linearGradient key={s.name} id={`grad${s.name}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={s.color} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="dia" stroke="#777" fontSize={10} tickLine={false} />
                  <YAxis domain={[0, 1]} stroke="#777" fontSize={10} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
                  {activeMarket.scenarios.map(s => (
                    <Area key={s.name} type="monotone" dataKey={s.name} stroke={s.color}
                      fill={`url(#grad${s.name})`} strokeWidth={2} />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Recent trades */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <h3>&#8635; Trades Recientes</h3>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Mercado</th>
                  <th>Esc.</th>
                  <th>$</th>
                  <th>Precio</th>
                  <th>Trader</th>
                  <th>Tiempo</th>
                </tr>
              </thead>
              <tbody>
                {RECENT_TRADES.map((t, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--accent-blue)', fontSize: '0.8rem' }}>{t.market}</td>
                    <td><span className="tag">{t.scenario}</span></td>
                    <td>${t.amount}</td>
                    <td>{(t.price * 100).toFixed(0)}%</td>
                    <td style={{ fontSize: '0.8rem' }}>{t.user}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{t.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Trader Ranking */}
          <div className="card">
            <div className="card-header">
              <h3>&#9733; Ranking de Traders</h3>
            </div>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Trader</th>
                  <th>PnL</th>
                  <th>Acc.</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {TRADER_RANKING.map(t => (
                  <tr key={t.rank}>
                    <td style={{ fontWeight: 700, color: t.rank <= 3 ? 'var(--accent-orange)' : 'var(--text-secondary)' }}>
                      {t.rank}
                    </td>
                    <td style={{ fontWeight: 600 }}>{t.name}</td>
                    <td style={{ color: '#4CAF50', fontWeight: 600 }}>+${t.pnl.toLocaleString()}</td>
                    <td>{t.accuracy}%</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{t.trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <WSIndicator message={wsMessage} />
    </div>
  );
}
