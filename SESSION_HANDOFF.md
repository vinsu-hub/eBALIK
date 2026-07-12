# eBALIK Session Handoff

**Date:** 2026-07-11
**Platform:** Windows (PowerShell), Python 3.14.6

---

## What Was Accomplished This Session

### 1. Local Development Environment Setup
- Installed MySQL 8.4.9 via winget (`Oracle.MySQL`)
- Initialized MySQL data directory manually with `--initialize-insecure` (empty root password)
- MySQL path: `C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe`
- MySQL config: `C:\ProgramData\MySQL\MySQL Server 8.4\my.ini`
- **MySQL is NOT installed as a Windows service** — must be started manually each session
- Created `ebalik_db` database with schema (`schema.sql`) and seed data (`seed_data.sql`)
- 5 books, 3 borrow records, admin user (`admin` / `admin123`)
- All 5 books currently in `borrowed` status (reset for demo testing)
- Created `D:\eBALIK\backend\.env` with MySQL config and `SERIAL_ENABLED=false`
- Installed Python dependencies (Flask, SQLAlchemy, SocketIO, PyMySQL, pyserial, eventlet, etc.)
- Flask running on port 5000, MySQL on port 3306

### 2. Wokwi Simulation
- Created `D:\eBALIK\wokwi\` with `diagram.json`, `libraries.txt`, `eBALIK_wokwi.ino`
- IR obstacle sensors replaced with pushbuttons; `IR_ACTIVE_STATE` changed from `LOW` to `HIGH`
- MFRC522 part type is `board-mfrc522` (not `wokwi-mfrc522`)
- RFID scanning uses `SIMULATE_UID,<uid>` debug serial command
- Wokwi cannot connect to Flask backend — tested independently

### 3. Serial Terminal Simulator (`sim_terminal.py`)
- Interactive CMD terminal for simulating Arduino RFID scans
- Commands: `<uid>` scan, `list`, `borrowed`, `reset`, `help`, `quit`
- Connects to MySQL + Socket.IO directly, emits live dashboard events
- Requires `pymysql` and `python-socketio` (auto-installed on first run)
- Window title: "Arduino Serial Terminal (Simulated) - eBALIK"

### 4. Hardware Monitor (`hw_monitor.py`)
- Standalone serial port scanner + real-time traffic monitor for physical Arduino
- Scans COM ports, connects at 115200 baud, sends PING/HELLO handshake
- Color-coded real-time serial traffic display with timestamps
- Commands: `PING`, `RESET`, `reconnect`, `quit`, or raw commands forwarded to Arduino
- Auto-connects if single port found, prompts if multiple ports
- **Does NOT close if no Arduino found** — waits for user to plug in and press Enter
- **Does NOT close on connection loss** — prompts to rescan and reconnect
- Uses `msvcrt.kbchew()` for non-blocking input — Windows-only

### 5. API Endpoints Added
- `POST /api/terminal/launch` — spawns `sim_terminal.py` in new CMD window (`CREATE_NEW_CONSOLE`), tracks PID to prevent duplicates
- `POST /api/hw-monitor/launch` — spawns `hw_monitor.py` in new CMD window, tracks PID to prevent duplicates

### 6. Complete Frontend Redesign
- Rewrote `style.css` (~1260 lines) — full design token system, CSS Grid, fluid `clamp()` typography, 5 breakpoints, mobile card layout for tables, stacked FABs
- Rewrote `base.html` — sidebar + topbar layout, collapsible sidebar (chevron toggle, localStorage persistence), two FAB buttons (USB + Terminal)
- Rewrote `login.html` — standalone with Inter font, decorative elements
- Rewrote `dashboard.html` — CSS Grid stat cards (`auto-fill minmax(200px, 1fr)`), grid-content, pill badges, data-label attributes
- Rewrote `books.html` — data-table, search-wrap, pill status badges, responsive columns, data-label attributes
- Rewrote `borrow_records.html` — data-table, pills, responsive columns, data-label attributes
- Rewrote `return_records.html` — data-table, pills, responsive columns, data-label attributes
- Rewrote `system_logs.html` — data-table, pill event types, responsive columns, data-label attributes
- Updated `dashboard.js` — selectors for `.stat-card .stat-value`, pill classes, `refreshStats()`
- Updated `socket_client.js` — sidebar device status updates alongside topbar badge

### 7. Bug Fixes
- Fixed content obscured by sidebar — added `main-content` class to `container-fluid` div in `base.html`
- Collapsible sidebar with auto-collapse on 992-1199px screens

---

## How to Restart Services

### MySQL (not a Windows service — manual start required)
```powershell
Start-Process "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=C:\ProgramData\MySQL\MySQL Server 8.4\my.ini" -WindowStyle Minimized
```
Wait ~3 seconds for initialization, then verify:
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -e "SHOW DATABASES;"
```

### Flask Server
```powershell
cd D:\eBALIK\backend
python run.py
```
Flask will be available at `http://localhost:5000`

---

## How to Stop Services

### Flask
Kill the Python process on port 5000:
```powershell
Get-Process python* | Where-Object { $_.Id -eq (Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue).OwningProcess } | Stop-Process -Force
```
Or simply close the terminal window running Flask.

### MySQL
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -e "SHUTDOWN;"
```
Or kill the mysqld process:
```powershell
Get-Process mysqld* | Stop-Process -Force
```

### All Python Processes (nuclear option)
```powershell
Get-Process python* | Stop-Process -Force
```

---

## Active Configuration

### `D:\eBALIK\backend\.env`
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=ebalik_db
SERIAL_ENABLED=false
SERIAL_PORT=COM3
SERIAL_BAUD=115200
```

### Database Credentials
- Host: `127.0.0.1:3306`
- User: `root`
- Password: (empty)
- Database: `ebalik_db`

### Demo Account
- Username: `admin`
- Password: `admin123`

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `D:\eBALIK\backend\app.py` or `run.py` | Flask entry point |
| `D:\eBALIK\backend\config.py` | Config class — MySQL URI, serial settings |
| `D:\eBALIK\backend\app\__init__.py` | App factory — registers blueprints, starts serial bridge |
| `D:\eBALIK\backend\app\extensions.py` | db, login_manager, socketio |
| `D:\eBALIK\backend\app\models.py` | SQLAlchemy models |
| `D:\eBALIK\backend\app\routes\api.py` | REST endpoints including terminal/launch and hw-monitor/launch |
| `D:\eBALIK\backend\app\routes\dashboard.py` | Dashboard + records pages |
| `D:\eBALIK\backend\app\routes\books.py` | Book CRUD |
| `D:\eBALIK\backend\app\routes\auth.py` | Login/logout |
| `D:\eBALIK\backend\app\serial_reader.py` | SerialBridge class |
| `D:\eBALIK\backend\sim_terminal.py` | Interactive CMD terminal simulator |
| `D:\eBALIK\backend\hw_monitor.py` | Standalone serial port scanner + monitor |
| `D:\eBALIK\backend\schema.sql` | MySQL schema |
| `D:\eBALIK\backend\seed_data.sql` | Demo data |
| `D:\eBALIK\backend\.env` | Active config |
| `D:\eBALIK\backend\app\static\css\style.css` | Full design system |
| `D:\eBALIK\backend\app\templates\base.html` | Sidebar + topbar layout |
| `D:\eBALIK\wokwi\eBALIK_wokwi.ino` | Wokwi-adapted firmware |
| `D:\eBALIK\wokwi\diagram.json` | Wokwi circuit |
| `D:\eBALIK\TOOLS\eBALIK_project_context.md` | Full project specification |

---

## Known Issues / Notes

- **MySQL not as service**: Must be started manually after each reboot
- **Windows console encoding**: Unicode box-drawing characters replaced with ASCII equivalents in CLI tools
- **Flask template caching**: Templates are cached in memory — server restart needed to pick up CSS/HTML changes
- **Only one process per COM port**: SerialBridge and hw_monitor.py cannot both be open on the same port
- **hw_monitor.py is Windows-only**: Uses `msvcrt.kbchew()` for non-blocking input
- **Wokwi limitation**: Cannot connect to Flask backend — Arduino simulation and web dashboard tested independently

---

## Next Steps

1. Plug in physical Arduino via USB
2. Test `hw_monitor.py` — verify COM port detection, PING/HELLO handshake, real-time serial traffic
3. Test `sim_terminal.py` alongside browser to confirm live Socket.IO dashboard updates work with the new UI
4. Enable `SERIAL_ENABLED=true` in `.env` and test full SerialBridge integration with real hardware
5. Any remaining UI polish based on real usage
