# INSTRUCCIONES DE BUILD DEL DASHBOARD — Windows 11
## VEO v2.0.5

**Fecha:** 2026-11-10  
**Objetivo:** Reconstruir `dashboard/build/` con el codigo fuente actualizado en Windows 11.

---

## 1. PRERREQUISITOS EN WINDOWS 11

Antes de comenzar, verifica que tienes instalados:

```cmd
node --version
npm --version
```

Esperado:
- Node.js: v20.20.2 (o superior)
- npm: 11.19.0 (o superior)

Si no los tienes, descarga el instalador LTS de https://nodejs.org/ (version 20.x).

---

## 2. ARCHIVOS QUE SE VAN A MODIFICAR

### 2.1 Archivos fuente ya modificados (correctos)

Estos archivos ya fueron actualizados en esta sesion y contienen la logica correcta:

| Archivo | Estado |
|---------|--------|
| `dashboard/src/App.jsx` | WebSocket hook con reconexion (sin cambios de esta sesion) |
| `dashboard/src/DashboardOverview.jsx` | **MODIFICADO** — consume API real, elimina datos mock |
| `dashboard/src/HypothesisPanel.jsx` | **MODIFICADO** — consume API real, validacion real |
| `dashboard/src/SystemHealthPanel.jsx` | Sin cambios (ya consumia API real) |

### 2.2 Archivos fuente con datos mock (aun no modificados)

Estos paneles aun contienen datos hardcodeados. Se compilaran pero mostraran datos de ejemplo:

| Archivo | Estado |
|---------|--------|
| `dashboard/src/PredictionMarket.jsx` | Datos mock (mercados de ejemplo) |
| `dashboard/src/CausalGraph.jsx` | Datos mock (grafo de ejemplo) |
| `dashboard/src/ScenarioSimulator.jsx` | Datos mock (simulaciones de ejemplo) |
| `dashboard/src/DiscoveryJournal.jsx` | Datos mock (diario de ejemplo) |
| `dashboard/src/NarrativeShift.jsx` | Datos mock (narrativas de ejemplo) |
| `dashboard/src/ArchitecturePanel.jsx` | Datos mock (arquitectura de ejemplo) |

**Nota:** Los paneles con datos mock se visualizaran con datos de ejemplo hasta que se modifiquen en futuras sesiones. Los paneles principales (Vision General, Hipotesis, Salud) mostraran datos reales de la API.

### 2.3 Archivos que se SUSTITUIRAN completamente

```
dashboard/build/index.html
dashboard/build/assets/index-*.js
dashboard/build/assets/index-*.css
```

El directorio `dashboard/build/` se vaciara y regenerara completamente.

### 2.4 Archivos que se CONSERVAN

```
dashboard/package.json
 dashboard/vite.config.js
 dashboard/src/          (todo el codigo fuente)
```

---

## 3. BACKUP DEL BUILD ANTERIOR

Antes de hacer nada, crea una copia de seguridad del build actual:

```cmd
REM Desde el directorio raiz del proyecto VEO (donde esta install.bat)
cd dashboard
xcopy /E /I /H build build_BACKUP_v2.0.4H
```

**Verifica que el backup se creo:**
```cmd
dir build_BACKUP_v2.0.4H\assets\
```

Debes ver:
- `index-CVbM_Xbm.js` (aprox. 653 KB)
- `index-CWV9aruS.css` (aprox. 21 KB)

---

## 4. PROCEDIMIENTO DE BUILD

### Paso 4.1 — Navegar al directorio del dashboard

```cmd
cd C:\ruta\a\tu\VEO\dashboard
```

(Reemplaza `C:\ruta\a\tu\VEO` con la ruta real donde descomprimiste el ZIP.)

### Paso 4.2 — Verificar node_modules

```cmd
if exist node_modules\react\package.json (
    echo node_modules ya existe
) else (
    echo node_modules NO existe — se instalara
)
```

### Paso 4.3 — Instalar dependencias (si es necesario)

Si `node_modules` NO existe o tienes dudas, ejecuta:

```cmd
npm install
```

**Espera a que termine.** npm descargara:
- react ^18.2.0
- react-dom ^18.2.0
- react-router-dom ^6.20.0
- recharts ^2.10.0
- @vitejs/plugin-react ^4.2.0
- vite ^5.0.0

**Tiempo estimado:** 1-3 minutos (depende de la conexion).

**Verificacion:**
```cmd
npm list react recharts vite
```

Debe mostrar las versiones instaladas sin errores.

### Paso 4.4 — Verificar vite.config.js

Abre `dashboard\vite.config.js` y confirma que contiene:

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/dashboard/',
  build: {
    outDir: 'build',
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
});
```

**Puntos clave:**
- `base: '/dashboard/'` — FastAPI sirve el dashboard en `/dashboard`
- `outDir: 'build'` — El build se genera en `dashboard/build/`
- `emptyOutDir: true` — Se borra el contenido anterior antes de compilar
- Proxy: `/api` y `/ws` redirigen a `localhost:8000` (el servidor FastAPI)

### Paso 4.5 — Compilar el build de produccion

```cmd
npm run build
```

**Espera a que termine.** Vite generara:
- `dashboard/build/index.html`
- `dashboard/build/assets/index-*.js` (bundle JavaScript)
- `dashboard/build/assets/index-*.css` (estilos)

**Tiempo estimado:** 10-30 segundos.

**Salida esperada (ejemplo):**
```
vite v5.x.x building for production...
transforming...
✓ 47 modules transformed.
rendering chunks...
computing gzip size...
build/index.html                     1.01 kB │ gzip: 0.47 kB
build/assets/index-XXXXXXX.js      185.4 kB │ gzip: 55.2 kB
build/assets/index-XXXXXXX.css      21.3 kB │ gzip: 5.1 kB
✓ built in 1.23s
```

**Importante:** Los nombres de los archivos `.js` y `.css` tendran un hash diferente al anterior (`index-CVbM_Xbm.js` → `index-XXXXXXXX.js`). Esto es normal.

---

## 5. VERIFICACION POST-BUILD

### 5.1 Verificar archivos generados

```cmd
dir dashboard\build\
dir dashboard\build\assets\
```

Debes ver:
- `index.html` (aprox. 1 KB)
- `assets\index-*.js` (aprox. 180-200 KB)
- `assets\index-*.css` (aprox. 20-25 KB)

### 5.2 Verificar que index.html apunta a los nuevos assets

Abre `dashboard\build\index.html` con un editor de texto y confirma que:
- La ruta del script apunta al nuevo archivo `.js` (no al antiguo `index-CVbM_Xbm.js`)
- La ruta del CSS apunta al nuevo archivo `.css` (no al antiguo `index-CWV9aruS.css`)

Ejemplo de como debe verse:
```html
<script type="module" crossorigin src="/dashboard/assets/index-ABC123DE.js"></script>
<link rel="stylesheet" crossorigin href="/dashboard/assets/index-XYZ789AB.css">
```

### 5.3 Verificar que FastAPI sirve el nuevo build

1. Inicia el servidor API:
```cmd
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000
```

2. Abre en el navegador:
```
http://localhost:8000/dashboard/
```

3. Debes ver el dashboard cargar (fondo oscuro, sidebar con iconos, titulo "VEO v2").

---

## 6. VERIFICACION FUNCIONAL EN NAVEGADOR

Abre las herramientas de desarrollador del navegador (F12) y verifica lo siguiente:

### 6.1 Consola JavaScript — Sin errores de importacion

Ve a la pestana **Console**. Debe haber:
- **0 errores rojos** de tipo `Failed to load module script` o `404 Not Found`
- Mensajes de log normales como `[VEO v2 WS]` cuando llegan eventos

Si ves errores 404 para `/dashboard/assets/index-*.js`, significa que el `index.html` apunta a archivos que no existen. Revisa el paso 5.2.

### 6.2 Pestaña "Vision General" (DashboardOverview)

1. Ve a **Vision General** en el sidebar.
2. Debes ver:
   - Tarjetas de metricas con valores numericos reales (o `--` si no hay datos)
   - Grafico NEI vacio con mensaje: "No hay datos de NEI disponibles" (si no hay hipotesis)
   - Seccion "Estado de Servicios" con datos reales de `/api/v2/system/health`
   - Seccion "Actividad en Tiempo Real" vacia o con eventos reales

3. En **Network** (pestaña del navegador), filtra por `api` y verifica:
   - `GET /api/v1/hipotesis` → Status 200, response con array (vacio o con hipotesis)
   - `GET /api/v1/alertas` → Status 200, response con array
   - `GET /api/v2/system/health` → Status 200, response con datos de componentes

### 6.3 Pestaña "Hipotesis" (HypothesisPanel)

1. Ve a **Hipotesis** en el sidebar.
2. Si no hay hipotesis creadas, debe mostrar:
   - "No hay hipotesis registradas. Crea una hipotesis via API o CLI para verla aqui."
3. En **Network**, verifica:
   - `GET /api/v1/hipotesis` → Status 200

### 6.4 Pestaña "Salud" (SystemHealthPanel)

1. Ve a **Salud** en el sidebar.
2. Debes ver:
   - Health Score con valor real (o gauge vacio si hay error)
   - Estado del sistema con version, modo, componentes
   - Estado de los 4 ciclos (o mensaje de error si el endpoint falla)
3. En **Network**, verifica:
   - `GET /api/v2/system/health` → Status 200
   - `GET /api/v2/system/status` → Status 200
   - `GET /api/v2/cycles/status` → Status 200 (o 500 si esta en mock)

### 6.5 WebSocket

1. En **Network** del navegador, filtra por `WS`.
2. Debes ver una conexion a `ws://localhost:8000/ws` con estado `101 Switching Protocols`.
3. En la pestana **Messages** del WS, debes ver:
   - Mensaje de tipo `conexion` con version y modo
   - Heartbeats cada 30 segundos (tipo `heartbeat`)
   - Eventos reales cuando se crean/validan hipotesis

4. Prueba crear una hipotesis via CLI en otra terminal:
```cmd
python cli\hermes_cli.py hypothesis create "Test de WebSocket" --mock
```

5. Debe aparecer un evento `hipotesis_nueva` en el WebSocket del navegador.

### 6.6 Datos vacios honestos

Si no hay datos en el sistema, los paneles deben mostrar mensajes claros como:
- "No hay hipotesis registradas."
- "No hay datos de NEI disponibles."
- "No hay alertas activas."
- "No hay actividad reciente."

**NO debes ver:** datos inventados como "H#42 confirmada", graficos con valores aleatorios, o alertas ficticias.

---

## 7. VERIFICACION DE PANELES CON DATOS MOCK

Los siguientes paneles aun muestran datos de ejemplo (se corregiran en futuras sesiones):

| Panel | Estado esperado |
|-------|----------------|
| Mercado | Datos de mercados de ejemplo |
| Grafo | Grafo causal de ejemplo |
| Simulacion | Datos de simulacion de ejemplo |
| Diario | Entradas de diario de ejemplo |
| Narrativa | Narrativas de ejemplo |
| Arquitectura | Diagrama de arquitectura de ejemplo |

**Esto es normal.** Estos paneles aun no estan conectados a la API real.

---

## 8. POSIBLES ERRORES Y SOLUCIONES

### Error 1: `vite is not recognized`

**Sintoma:**
```
'vite' is not recognized as an internal or external command
```

**Causa:** `node_modules` no esta instalado o `.bin` no esta en PATH.

**Solucion:**
```cmd
npm install
```
Si persiste, usa npx:
```cmd
npx vite build
```

---

### Error 2: `Cannot find module 'react'`

**Sintoma:**
```
Error: Cannot find module 'react'
```

**Causa:** `node_modules` esta incompleto o corrupto.

**Solucion:**
```cmd
rmdir /S /Q node_modules
npm install
npm run build
```

---

### Error 3: Build genera archivos con hash diferente pero index.html apunta al antiguo

**Sintoma:** El navegador muestra 404 para `/dashboard/assets/index-XXXX.js`.

**Causa:** `vite.config.js` tiene `emptyOutDir: true` pero algo fallo.

**Solucion:**
```cmd
rmdir /S /Q build
npm run build
```

---

### Error 4: FastAPI no sirve el dashboard

**Sintoma:** `http://localhost:8000/dashboard/` devuelve 404.

**Causa:** El directorio `dashboard/build` no existe o FastAPI no lo encuentra.

**Verificacion:**
```cmd
dir dashboard\build\index.html
```

Si existe, reinicia el servidor uvicorn. Si no existe, ejecuta `npm run build`.

---

### Error 5: La API no responde (CORS o conexion)

**Sintoma:** El dashboard muestra errores de red o "CORS policy".

**Causa:** El servidor FastAPI no esta corriendo o CORS no esta configurado.

**Verificacion:**
```cmd
curl http://localhost:8000/health
```

Debe devolver un JSON con estado del sistema. Si no responde, inicia uvicorn:
```cmd
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000
```

---

### Error 6: WebSocket no conecta

**Sintoma:** En la consola del navegador: `WebSocket connection to 'ws://localhost:8000/ws' failed`.

**Causas posibles:**
1. El servidor FastAPI no esta corriendo
2. Un firewall bloquea el puerto 8000
3. El proxy de `vite.config.js` no esta activo (solo aplica en `npm run dev`, no en build)

**Solucion:**
- Confirma que uvicorn esta corriendo en `localhost:8000`
- En el build de produccion, el WebSocket se conecta directamente a `ws://localhost:8000/ws` (no pasa por proxy de Vite)
- Si usas `npm run dev` (modo desarrollo), el proxy de Vite redirige `/ws` a `ws://localhost:8000`

---

### Error 7: El dashboard muestra datos mock en Vision General o Hipotesis

**Sintoma:** Ves alertas como "Cambio abrupto en narrativa 'IA regulacion'" o hipotesis como "H#42 La adopcion de IA generativa...".

**Causa:** El build no se reconstruyo correctamente y sigue sirviendo los archivos antiguos.

**Verificacion:**
1. Abre `dashboard\build\assets\index-*.js` con un editor de texto
2. Busca el texto `"Cambio abrupto en narrativa"`
3. Si lo encuentras, el build es antiguo

**Solucion:**
```cmd
rmdir /S /Q build
npm run build
```

Verifica que la fecha de los archivos en `build\assets\` sea reciente.

---

## 9. COMO REVERTIR SI ALGO FALLA

Si el nuevo build no funciona y quieres volver al anterior:

```cmd
cd dashboard
rmdir /S /Q build
xcopy /E /I /H build_BACKUP_v2.0.4H build
```

Reinicia uvicorn y verifica que el dashboard carga correctamente.

---

## 10. RESUMEN DE COMANDOS

```cmd
REM 1. Ir al directorio del dashboard
cd C:\ruta\a\tu\VEO\dashboard

REM 2. Backup del build anterior
xcopy /E /I /H build build_BACKUP_v2.0.4H

REM 3. Instalar dependencias (si es necesario)
npm install

REM 4. Verificar vite.config.js (manual)

REM 5. Compilar
npm run build

REM 6. Verificar archivos generados
dir build\assets\

REM 7. Iniciar FastAPI (en otra terminal)
cd C:\ruta\a\tu\VEO
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000

REM 8. Abrir navegador en http://localhost:8000/dashboard/
```

---

## 11. CRITERIOS PARA DAR LA SESION 2 POR TERMINADA

La Sesion 2 se considera completada cuando se cumplan TODOS estos criterios:

- [ ] `npm run build` completa sin errores
- [ ] `dashboard/build/` contiene archivos con fecha reciente
- [ ] `index.html` apunta a los nuevos assets (hash diferente al anterior)
- [ ] FastAPI sirve el dashboard en `http://localhost:8000/dashboard/`
- [ ] El dashboard carga visualmente correcto (modo oscuro, sidebar, iconos)
- [ ] **Vision General** muestra metricas reales o mensajes de vacio honestos
- [ ] **Hipotesis** muestra la lista real o "No hay hipotesis registradas"
- [ ] **Salud** muestra health/status reales o mensajes de error claros
- [ ] WebSocket se conecta (`ws://localhost:8000/ws` en Network → WS)
- [ ] Crear una hipotesis via CLI genera un evento WS visible en el navegador
- [ ] Los paneles con datos mock se identifican como tales (no se confunden con datos reales)

**NO se da por terminada la Sesion 2 solo porque `npm run build` compile correctamente.** La integracion funcional en el navegador es obligatoria.

---

*Documento preparado para ejecucion en Windows 11.*
