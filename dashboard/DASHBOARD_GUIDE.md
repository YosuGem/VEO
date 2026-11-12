# VEO Dashboard — User Guide

The VEO Dashboard is a pre-built React application that provides a visual interface to the VEO system. It is served automatically by the API server and requires no separate installation or build step.

---

## Starting the Dashboard

1. Start the API server:
   ```bash
   python api/api_server.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:8000/dashboard/
   ```

The root path (`http://localhost:8000/`) automatically redirects to the dashboard.

---

## Interface Overview

### Dark Mode

The dashboard uses dark mode by default. This is not configurable — the design decision is to reduce eye strain during extended analysis sessions. All charts, tables, and forms are optimized for dark backgrounds.

### Sidebar Navigation

| Section | Description |
|---------|-------------|
| **Resumen / Overview** | System status, active hypotheses count, metrics summary |
| **Hipótesis / Hypotheses** | List, create, and view hypothesis details |
| **Predicción / Prediction** | Prediction markets overview |
| **Simulación / Simulation** | Scenario simulation interface |
| **Mercados / Markets** | Active prediction markets |
| **Sistema / System** | Health checks, configuration viewer |

### Main Content Area

- **Hypotheses Table:** Sortable list with ID, title, status, confidence, and creation date
- **Detail Panel:** When a hypothesis is selected, shows full metadata, validation status, and evidence
- **Charts:** Recharts-based visualizations for confidence distributions and temporal trends
- **Auto-refresh:** Data refreshes automatically every 30 seconds

---

## Using the Dashboard

### Viewing Hypotheses

1. Click "Hipótesis" in the sidebar
2. The main area shows a table of all hypotheses
3. Click on any row to see the detail panel

### Creating a Hypothesis

1. Navigate to "Hipótesis"
2. Click the "Nueva Hipótesis" button
3. Fill in the text and optional metadata
4. Click "Crear"

### Checking System Health

1. Navigate to "Sistema"
2. View the health indicators and recent log entries

---

## API Documentation from the Browser

While the API is running, you can also access the interactive API documentation:

- **Swagger UI:** `http://localhost:8000/docs` — Test endpoints directly from the browser
- **ReDoc:** `http://localhost:8000/redoc` — Alternative documentation format

Both interfaces are styled in dark mode for consistency.

---

## Troubleshooting

### Blank Page

If the dashboard shows a blank page:
1. Verify the API server is running: `curl http://localhost:8000/health`
2. Check browser console for JavaScript errors
3. Ensure you are using the correct URL: `http://localhost:8000/dashboard/` (with trailing slash)

### Charts Not Loading

If charts appear empty:
1. Check that hypotheses exist in the system
2. Verify the API is responding to data requests
3. Refresh the page (F5)

### Dark Mode Too Dark

The dashboard is designed exclusively for dark mode. If text is difficult to read:
1. Ensure your monitor brightness is adequate
2. Check for browser extensions that might override CSS (e.g., dark mode extensions)
3. The dashboard uses `filter: invert()` on Swagger/ReDoc — this is intentional

---

## Technical Details

- **Framework:** React 18 + Vite
- **Charts:** Recharts
- **Routing:** React Router with basename `/dashboard/`
- **Build:** Pre-compiled static files in `dashboard/dist/`
- **Serving:** FastAPI StaticFiles mount at `/dashboard`
- **No build required:** The distributed package contains pre-built assets
