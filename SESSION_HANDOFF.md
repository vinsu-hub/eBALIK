# eBALIK Session Handoff

**Last updated:** 2026-07-12
**Platform:** Windows (PowerShell), Python 3.14.6

---

## Session 1 — 2026-07-11 (Initial Setup)

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
- Rewrote `style.css` (~1340 lines) — full design token system, CSS Grid, fluid `clamp()` typography, 5 breakpoints, mobile card layout for tables, stacked FABs
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

## Session 2 — 2026-07-12 (System Hardening + Deployment)

### 8. System Hardening (11 tasks completed)

#### P0 — Critical Fixes
- **UID normalization verified** at all 8 entry points (serial_reader, api simulate_scan, books add_book) — `.upper().strip()` applied consistently
- **Malformed UID validation** — regex `^[0-9A-F]{8}$|^[0-9A-F]{14}$` (4-byte or 7-byte MIFARE) added to `serial_reader.py`, `api.py`, `books.py`. Malformed UIDs log a WARNING to `system_logs` and are never silently accepted.
- **Duplicate-state UX fix** (`book_rfid_scan.js`) — warning icon instead of green checkmark, UID stays visible in disabled input, save button disabled, "Reassign to this book" button shown. UID input `input` event resets duplicate/error state back to idle.

#### P1 — Protocol Hardening
- **INVALID reason field** — backend now sends 3-field format: `INVALID,<uid>,<reason>` with reasons `UNKNOWN_TAG`, `NOT_BORROWED`, `MALFORMED_UID`. Firmware parses 3rd field and displays distinct LCD messages ("Unknown tag", "Not borrowed", "Malformed UID").
- **RETURN_FAILED audit** — all 4 firmware timeout paths verified to send `RETURN_FAILED` (no change needed, audit only)
- **Late VALID/INVALID race guard** — already existed at firmware line 261 (audit only)
- **RFID debounce** — 3-second cooldown on `pollForCard()` in firmware prevents duplicate scans when tag is held on reader. New constant `RFID_DEBOUNCE_MS = 3000`.

#### P2 — Production Hardening
- **DEBUG_MODE gating** — dev endpoints (`/api/simulate/scan`, `/api/terminal/launch`, `/api/hw-monitor/launch`) require `DEBUG_MODE=true` in `.env`. Returns 403 when not set. New config in `config.py`.
- **Reassign tag flow** — new `POST /api/books/reassign-tag` endpoint moves RFID tag between books in a single transaction (clears old binding, assigns to new book). UI button in duplicate state of `book_rfid_scan.js`. `rfid_uid` column altered to allow NULL (`ALTER TABLE books MODIFY rfid_uid VARCHAR(32) NULL`).
- **Reconnect staleness fix** — `socket_client.js` `connect` handler now fetches `/api/hw-status` and calls `refreshStats()` to resync stale dashboard data after reconnect.
- **Port re-resolution on reconnect** — `_connect()` in `serial_reader.py` now calls `_resolve_port()` on each retry in the reconnect loop, so the bridge can find the Arduino if it moved to a different COM port after replug.

### 9. Architecture Documentation
- Updated `currentsystemarchitecture.md` (12 edits across all sections):
  - Header: date + "system hardening" scope line
  - Section 3: debounce timeout added
  - Section 4.2: INVALID format updated to 3-field with reasons
  - Section 5.3: `rfid_uid` nullable + reassignment note
  - Section 5.4: SerialBridge structure rewritten (UID validation, reconnect, re-resolve)
  - Section 5.5: `reassign-tag` endpoint row + DEBUG_MODE footnote
  - Section 6.3: reconnect refresh note
  - Section 8.2: duplicate state row rewritten + 2 new bullets
  - Section 9.1: return flow step 5 expanded with malformed/reason branches
  - Section 10: 5 new design decision rows
  - Section 11: firmware ~365 lines, `install_mysql_service.bat`, updated comments

### 10. Git Repository + GitHub
- Initialized git repo in `D:\eBALIK`
- Pushed to **https://github.com/vinsu-hub/eBALIK** (public)
- 79 files, 20909 insertions
- Commit: `a25bf8a` — "Initial commit: eBALIK full system with hardening"

### 11. Bug Fixes
- Fixed Flask 500 errors — MySQL wasn't running. `Start-Process` was splitting path at spaces in `C:\Program Files\MySQL\...`. Fixed by using PowerShell job with proper quoting.
- Added `DEBUG_MODE=true` to `.env` to re-enable dev endpoints after gating was added.
- All pages verified working: `/`, `/books/`, `/logs`, `/records/borrow`, `/records/return`

---

## How to Restart Services

### MySQL (not a Windows service — manual start required)
```powershell
Start-Job -ScriptBlock { & "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" "--defaults-file=C:\ProgramData\MySQL\MySQL Server 8.4\my.ini" }; Start-Sleep -Seconds 8
```
Verify:
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

---

## Active Configuration

### `D:\eBALIK\backend\.env`
```
SECRET_KEY=ebalik-dev-secret-key-change-in-production
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=ebalik_db
SERIAL_PORT=
SERIAL_BAUD=115200
SERIAL_ENABLED=false
DEFAULT_LOAN_DAYS=7
DEBUG_MODE=true
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
| `backend/run.py` | Flask entry point |
| `backend/config.py` | Config class — MySQL URI, serial settings, DEBUG_MODE |
| `backend/app/__init__.py` | App factory — registers blueprints, starts serial bridge |
| `backend/app/extensions.py` | db, login_manager, socketio singletons |
| `backend/app/models.py` | SQLAlchemy models (rfid_uid nullable for reassign) |
| `backend/app/serial_reader.py` | SerialBridge — UID validation, INVALID reasons, reconnect, debounce |
| `backend/app/hw_utils.py` | CH340 port detection (shared module) |
| `backend/app/routes/api.py` | REST endpoints — DEBUG_MODE gated, reassign-tag |
| `backend/app/routes/books.py` | Book CRUD + UID format validation |
| `backend/app/routes/dashboard.py` | Dashboard + records pages |
| `backend/app/routes/auth.py` | Login/logout |
| `backend/sim_terminal.py` | Interactive CMD terminal simulator |
| `backend/hw_monitor.py` | Standalone serial port scanner + monitor |
| `backend/schema.sql` | MySQL schema |
| `backend/seed_data.sql` | Demo data |
| `backend/.env` | Active config (excluded from git) |
| `backend/app/static/css/style.css` | Full design system (~1340 lines) |
| `backend/app/static/js/book_rfid_scan.js` | RFID registration + duplicate state + reassign |
| `backend/app/static/js/socket_client.js` | Socket.IO + reconnect refresh |
| `backend/app/templates/base.html` | Sidebar + topbar layout |
| `arduino/eBALIK_arduino/eBALIK_arduino.ino` | Arduino firmware (~365 lines) |
| `wokwi/eBALIK_wokwi.ino` | Wokwi-adapted firmware |
| `wokwi/diagram.json` | Wokwi circuit |
| `TOOLS/install_ch340_driver.bat` | CH340 driver installer |
| `TOOLS/install_mysql_service.bat` | MySQL service installer |
| `TOOLS/eBALIK_project_context.md` | Full project specification |
| `currentsystemarchitecture.md` | System architecture (all hardening documented) |
| `docs/PROTOCOL.md` | Serial protocol spec (INVALID reasons documented) |
| `setup.bat` | Full environment setup script |

---

## Known Issues / Notes

- **MySQL not as service**: Must be started manually after each reboot. Use `Start-Job` with proper quoting for paths with spaces.
- **MySQL start timing**: Wait ~8 seconds after `Start-Job` before running queries.
- **Windows console encoding**: Unicode box-drawing characters replaced with ASCII equivalents in CLI tools
- **Flask template caching**: Templates are cached in memory — server restart needed to pick up CSS/HTML changes
- **Only one process per COM port**: SerialBridge and hw_monitor.py cannot both be open on the same port
- **hw_monitor.py is Windows-only**: Uses `msvcrt.kbchew()` for non-blocking input
- **Wokwi limitation**: Cannot connect to Flask backend — Arduino simulation and web dashboard tested independently
- **CDN dependency**: Bootstrap/Socket.IO loaded from CDN in `base.html` — download locally if no wifi at demo venue

---

## Demo Laptop Deployment

```powershell
git clone https://github.com/vinsu-hub/eBALIK.git
cd eBALIK
setup.bat                          # venv, deps, CH340 driver, schema
python backend\create_admin.py     # create admin user
python backend\run.py              # start server
# Open http://localhost:5000
```

Requires: Python 3.11+, MySQL 8.4, Arduino Uno R3 with CH340 USB-serial.

---

## Next Steps

1. Deploy on demo laptop — clone, setup, test with real hardware
2. Plug in physical Arduino via USB and verify COM port auto-detection
3. Test full return flow: scan borrowed book → VALID → servo → RETURN_SUCCESS → dashboard update
4. Test registration flow: scan new tag → assign to book → verify binding
5. Test reassign flow: scan tag belonging to other book → click reassign → verify UID moved
6. Test debounce: hold tag on reader for >3s, verify only one scan processed
7. Test reconnect: unplug/replug Arduino, verify dashboard re-syncs
8. Download Bootstrap/Socket.IO locally if demo venue has no wifi
