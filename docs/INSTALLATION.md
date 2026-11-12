# Installation Guide — VEO v2.0.5

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Linux Installation](#2-linux-installation)
3. [Windows 11 Installation](#3-windows-11-installation)
4. [Manual Installation](#4-manual-installation)
5. [Dashboard Build](#5-dashboard-build)
6. [Verification](#6-verification)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Disk | 500 MB | 2 GB SSD |
| Network | Internet connection | Stable |

### Software

| Software | Version | Notes |
|----------|---------|-------|
| Python | 3.11+ | 3.12 recommended |
| Git | 2.30+ | For cloning |
| Node.js | 20.20.2+ | Only for Dashboard build |
| npm | 11.19.0+ | Only for Dashboard build |

---

## 2. Linux Installation

### Option A: Automated (`install.sh`)

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
chmod +x install.sh
./install.sh
source venv/bin/activate
```

The script performs:
- Virtual environment creation
- Dependency installation
- Test execution

### Option B: Manual

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

---

## 3. Windows 11 Installation

### Option A: Automated (`install.bat`)

```cmd
git clone https://github.com/YosuGem/VEO.git
cd VEO
install.bat
```

The script performs:
- Virtual environment creation (`venv`)
- Dependency installation
- Directory structure creation (`data/`, `logs/`, `backups/`)
- Test execution

### Option B: Manual

```cmd
git clone https://github.com/YosuGem/VEO.git
cd VEO
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python -m pytest tests/ -q
```

---

## 4. Manual Installation (Advanced)

If you need full control over each step:

### Step 1: Clone Repository

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux
venv\Scripts\activate.bat       # Windows
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
python -m pytest tests/ -q
```

Expected output: 293 tests passed.

---

## 5. Dashboard Build

The React Dashboard must be built once (or after modifying source code):

```bash
cd dashboard
npm install
npm run build
```

On Windows:
```cmd
cd dashboard
npm install
npm run build
```

This generates static files in `dashboard/build/` that FastAPI serves automatically at `/dashboard/`.

**Note:** The `npm install` step may fail in some environments (e.g., sandbox filesystems) due to symlink limitations. In such cases, build the Dashboard on a standard filesystem (Windows 11 or Linux desktop).

---

## 6. Verification

### 6.1 Start the API Server

```bash
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000
```

Or via CLI:
```bash
python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000
```

### 6.2 Check Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/system/health
```

### 6.3 Test CLI Commands

```bash
python cli/hermes_cli.py version
python cli/hermes_cli.py health
python cli/hermes_cli.py status
```

### 6.4 Test Hypothesis Creation

```bash
python cli/hermes_cli.py hypothesis create "Test hypothesis for verification"
python cli/hermes_cli.py hypothesis list
```

### 6.5 Open Dashboard

Navigate to `http://localhost:8000/dashboard/` in your browser.

---

## 7. Troubleshooting

### Problem: "Python not found"

**Solution:**
```bash
# Linux
which python3
# If not found, install Python 3.11+ from your package manager

# Windows
where python
# If not found, add Python to PATH or use the Python Launcher:
py -3.12 --version
```

### Problem: "Port 8000 already in use"

**Solution:**
```bash
# Linux
lsof -ti:8000 | xargs kill -9
# Or use another port:
python -m uvicorn api.api_server:app --port 8080

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Problem: "Tests fail"

**Solution:**
```bash
# Clean reinstall
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

### Problem: "Dashboard shows blank page"

**Solution:**
```bash
cd dashboard
npm install
npm run build
# Ensure the build completed without errors
```

### Problem: "click incompatible with typer"

**Cause:** click >= 8.2.0 with typer < 0.16.0.

**Solution:**
```bash
pip install "click<8.2.0"
```

The `requirements.txt` already pins `click<8.2.0`. If you installed manually, run the above command.

### Problem: "ModuleNotFoundError: No module named 'veo_v2'"

**Cause:** Virtual environment not activated.

**Solution:**
```bash
source venv/bin/activate        # Linux
venv\Scripts\activate.bat       # Windows
```

### Problem: npm install fails (Linux sandbox)

**Cause:** Some filesystems do not support symlinks, which npm requires.

**Solution:** Build the Dashboard on a standard filesystem (Windows 11 or Linux desktop with standard ext4). The API and CLI work without the Dashboard build.

---

*Last updated: 2026-11-11*
