# eBALIK Session Handoff

**Last updated:** 2026-07-18
**Platform:** Windows (PowerShell), Python 3.13.14

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

## Session 3 — 2026-07-13 (Full System Setup + hw_monitor.py Bugfixes)

### 1. Full System Setup on This Machine
- Installed MySQL 8.4.9 via winget (`Oracle.MySQL`), initialized data dir at `C:\Users\Renato Cabahug\Documents\Queen Lee\eBALIK\eBALIK\mysql_data`
- MySQL root password set to `ebalik123`
- MySQL started manually (not as a service — must be restarted each session)
- Loaded `schema.sql` + `seed_data.sql` into `ebalik_db`
- Updated admin hash with real werkzeug scrypt hash (password: `admin123`)
- Installed Python deps from `backend\requirements.txt` (26 packages) into `backend\venv` (venv reuses existing)
- Updated `backend\.env`: `DB_PASSWORD=ebalik123`, `SERIAL_ENABLED=false`, `DEBUG_MODE=true`
- Flask started on port **5001** (port 5000 was taken by PID 4)

### 2. hw_monitor.py Bugfixes (both confirmed)
#### Issue 1 — kbchew() typo
- **Line 324**: `msvcrt.kbchew()` → `msvcrt.kbhit()` — confirmed single occurrence in code, no downstream impact
- Also confirmed `kbchew` mentioned in `SESSION_HANDOFF.md` lines 45 and 228 (cosmetic, documentation only)

#### Issue 2 — No HELLO response
- **Cause**: Timing — CH340 DTR toggle resets Arduino on serial open. Existing 2s boot delay was too short for Uno R3 bootloader (~1.5-2.5s) + sketch startup. `reset_input_buffer()` at 2s would also discard any `HELLO` sent during `setup()`.
- **Fix**: Added `BOOT_DELAY = 3.5` constant (line 52), replaced `time.sleep(2)` + `buffer flush` with `time.sleep(BOOT_DELAY)` in both initial connect (line 206-208) and reconnect path (line 310-312)
- **Fix**: Rewrote `try_ping()` to retry PING every 1s within the 3s timeout window with buffer flush between attempts, instead of a single shot
- **Firmware uploaded?**: Not yet — Arduino IDE not installed on this machine

### 3. Services Shutdown
- MySQL process stopped
- Flask process stopped
- Created `TODO_TOMORROW.md` for next session

---

## Session 4 — 2026-07-14 (Arduino Integration + FAB Scan + Badge Fix)

### 1. Arduino Physical Setup
- CH340 USB-serial driver installed (CH341SER_A64 v3.90)
- Arduino Uno on **COM6** at 115200 baud
- `SERIAL_ENABLED=true` set in `backend/.env`
- SerialBridge in Flask holds COM6 — hw_monitor.py cannot coexist

### 2. FAB Button COM6 Conflict Fix
- **Problem**: "Scan for Arduino" FAB button launched hw_monitor.py which fought SerialBridge for COM6
- **Fix** (`api.py:216-227`): `/api/hw-monitor/launch` now checks if SerialBridge already has the port, returns `{"connected": true}` instead of launching conflicting process
- **Fix** (`base.html`): FAB click handler shows green checkmark when Arduino already connected via SerialBridge

### 3. Topbar Badge Race Condition Fix
- **Problem**: Badge showed "Arduino offline" despite SerialBridge being connected. Root cause: `socket_client.js` `connect` handler fetched `/api/hw-status` which returned stale module-level `_hw_status` dict (never updated by SerialBridge, only by hw_monitor.py POSTs), overwriting the correct state from the earlier `/api/device/status` fetch.
- **Fix** (`api.py:62-65`): `GET /api/hw-status` now checks `bridge.ser.is_open` live state first, returns accurate connection info. Falls back to `_hw_status` dict only for hw_monitor.py connections.
- **Impact**: This unblocked the Add Book modal's "Scan to Register" button (disabled when badge lacks `bg-success` class)

### 4. RFID Scan-to-Register FAB Button
- **New FAB button** (`base.html:104-106`): Blue primary-colored button with RFID icon (`bi-r-circle`), sits at top of FAB stack
- **Click behavior** (`base.html:226-253`):
  - On Books page → opens Add Book modal directly, sets `autoScan` data attribute
  - On any other page → redirects to `/books?auto_scan=1`
  - Listens for `hw_status_update` events to enable/disable button based on Arduino connection
- **Auto-scan handler** (`book_rfid_scan.js:212-229`): On page load, checks for `?auto_scan=1` query param → auto-opens Add Book modal → on `shown.bs.modal`, starts `startScanListen()` (15s countdown) if Arduino is online
- **CSS** (`style.css:1023-1030`): `.fab-scan` variant with primary blue color

### 5. Complete RFID Registration Flow (End-to-End)
```
Click blue FAB → Add Book modal opens → "Listening..." countdown (15s)
  → Tap RFID tag on reader → Arduino sends "RFID,<uid>" via serial
  → SerialBridge captures (listening_for_registration mode)
  → Socket.IO emits rfid_registration_scan
  → Frontend fills RFID UID input → shows success state
  → User fills Title/Author/etc. → clicks "Add Book"
  → POST /books/add → Book saved to database
```

### 6. Session End State
- Flask running on port 5001, SerialBridge connected on COM6
- Arduino online with green LED (D7), red LED (D8), buzzer wired
- All frontend pages verified (200): dashboard, books, borrow records, return records, system logs
- All API endpoints verified: stats, device/status, hw-status, logs/recent
- Dashboard open in browser showing live connection
- **FAB stack**: Blue scan FAB (top) → Green HW monitor FAB → Gray terminal FAB (bottom)

---

## How to Restart Services

### MySQL (not a Windows service — manual start required)
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --datadir="C:\Users\Renato Cabahug\Documents\Queen Lee\eBALIK\eBALIK\mysql_data"
```
Wait ~8s, then verify:
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -pebalik123 -e "SHOW DATABASES;"
```

### Flask Server
```powershell
cd C:\Users\Renato Cabahug\Documents\Queen Lee\eBALIK\eBALIK
.\backend\venv\Scripts\activate
python .\backend\run.py
```
Flask available at `http://localhost:5001`

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

### `C:\Users\Renato Cabahug\Documents\Queen Lee\eBALIK\eBALIK\backend\.env`
```
SECRET_KEY=ebalik-dev-secret-key-change-in-production
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=ebalik123
DB_NAME=ebalik_db
SERIAL_PORT=
SERIAL_BAUD=115200
SERIAL_ENABLED=true
DEFAULT_LOAN_DAYS=7
DEBUG_MODE=true
```

### Database Credentials
- Host: `127.0.0.1:3306`
- User: `root`
- Password: `ebalik123`
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
| `backend/app/static/js/book_rfid_scan.js` | RFID registration + duplicate state + reassign + auto_scan |
| `backend/app/static/js/socket_client.js` | Socket.IO + reconnect refresh + device badge |
| `backend/app/templates/base.html` | Sidebar + topbar layout + 3 FAB buttons (scan, hw, terminal) |
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
- **hw_monitor.py is Windows-only**: Uses `msvcrt.kbhit()` for non-blocking input
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

1. **Upload firmware** — Install Arduino IDE, upload `arduino\eBALIK_arduino\eBALIK_arduino.ino`, install MFRC522 + LiquidCrystal I2C libs
2. **Test hw_monitor.py** — `python backend\hw_monitor.py`, verify PING/HELLO handshake with 3.5s boot delay fix
3. ~~Enable serial~~ — **Done** — `SERIAL_ENABLED=true` in `.env`, SerialBridge connected on COM6
4. Test full return flow: scan borrowed book → VALID → servo → RETURN_SUCCESS → dashboard update
5. Test registration flow via FAB button: click blue FAB → modal opens → scan tag → UID fills input → save book
6. Test reassign flow: scan tag belonging to other book → click reassign → verify UID moved
7. Test debounce: hold tag on reader for >3s, verify only one scan processed
8. Test reconnect: unplug/replug Arduino, verify dashboard re-syncs
9. Download Bootstrap/Socket.IO locally if demo venue has no wifi

---

## Session 5 — 2026-07-18 (Full Environment Setup, Obstruction Removal, Servo Calibration, Firmware Update)

### 1. Full Development Environment Setup (from scratch)
- Installed Python 3.13.14 via winget
- Created venv at `backend/venv` + installed all 10 direct + 20 transitive pip dependencies
- Created `backend/.env` from `.env.example` (SECRET_KEY, DB_PASSWORD=ebalik123, SERIAL_ENABLED=true, DEBUG_MODE=true)
- Initialized MySQL 8.4.9 data directory, started server, set root password, loaded `schema.sql` + `seed_data.sql`
- Created admin user (`admin` / `admin123`) — fixed truncated scrypt password hash
- CH340 driver installed via `SETUP.EXE /S`
- Installed arduino-cli v1.5.1, AVR core 1.8.8, libraries: MFRC522 v1.4.12, LiquidCrystal I2C v1.1.2, Servo v1.3.0
- Firmware compiles clean (45% flash, 53% RAM) and uploaded to COM4
- Flask server running on `http://localhost:5001`, SerialBridge connected to COM4

### 2. Safety Obstruction Sensor Removal Propagation
The original design had 3 IR sensors (Entrance, Full Entry, Safety Obstruction). Safety Obstruction (pin D4) was removed from firmware. A closing warning module (2s delay, double beep, LCD message) replaced the sensor-verified clearance check.

**Files updated:**
- `docs/PROTOCOL.md` — removed STATUS,OBSTRUCTION + OBSTRUCTION_TIMEOUT, added STATE_CLOSING_WARNING
- `backend/app/serial_reader.py` — removed OBSTRUCTION handler branch + docstring reference
- `backend/app/static/js/dashboard.js` — removed OBSTRUCTION from labelMap/clsMap
- `backend/hw_monitor.py` — removed OBSTRUCTION color override
- `backend/simulate_return.py` — replaced obstruction step with closing warning
- `README.md` — updated to 2 IR sensors, updated return flow
- `WIRING_GUIDE.md` — 2 sensors, pin D4 free, all diagrams/tables updated
- `currentsystemarchitecture.md` — state machine, BOM, pin map, protocols, flow diagrams
- `TOOLS/eBALIK_project_context.md` — BOM, modules, workflow, comparison table
- `wokwi/diagram.json` — removed btn_obstruction, r3, and all their wires
- `wokwi/eBALIK_wokwi.ino` — updated to match real firmware (2 buttons, closing warning, debounce, LED stubs)
- `arduino/eBALIK_arduino/eBALIK_arduino.ino` — replaced with final firmware (v1.0 with obstruction removal + closing warning)

### 3. Servo Calibration — Physical Testing
- Created `arduino/servo_calibration/servo_calibration.ino` — standalone test sketch for servo angle calibration
- Uses Serial Monitor commands: type 0-180 for manual angle, 'o' for open, 'c' for closed, 's' for sweep
- **Calibrated angles (confirmed by physical testing):**
  - `SERVO_CLOSED_ANGLE = 10` (door flap closed, default on boot)
  - `SERVO_OPEN_ANGLE = 80` (door flap open, book can enter)
- Mechanism is a **door flap** (not a tilt-drop shelf as previously documented)

### 4. Servo Calibration Propagation
Updated all firmware, backend, and documentation to reflect calibrated values:

**Firmware:**
- `arduino/eBALIK_arduino/eBALIK_arduino.ino` — angles 10/80, "door flap" comments, calibrated date
- `wokwi/eBALIK_wokwi.ino` — angles 10/80, "door flap" comments

**Backend:**
- `backend/simulate_return.py` — log messages: open = 80°, closed = 10°

**Documentation (all updated from "tilt-drop shelf" → "door flap", angles 80/20 → 10/80):**
- `WIRING_GUIDE.md` — angle table, firmware #define table, BOM, diagrams, checklist
- `currentsystemarchitecture.md` — BOM, state machine diagram, intro, mechanism descriptions
- `TOOLS/eBALIK_project_context.md` — module descriptions, workflow, BOM
- `README.md` — intro, return flow description
- `PROJECT_CURRENT_STATE.md` — angle table, mechanism description, all references

### 5. Firmware Logic Change — Servo Opens on IR Detection
Changed the return flow so the door flap only opens when the entrance IR sensor confirms the book is at the slot:

**Old flow:** VALID → servo opens immediately → waits for entrance IR → full entry → closing warning → close
**New flow:** VALID → servo stays closed, shows "Book approved" → entrance IR detects book → **NOW servo opens** → full entry IR → closing warning (2s) → servo closes

**Code changes in `eBALIK_arduino.ino`:**
- Renamed `STATE_SLOT_OPEN_AWAIT_ENTRANCE` → `STATE_AWAITING_ENTRANCE`
- On VALID: show "Book approved / Insert when ready", servo stays closed (10°), enter STATE_AWAITING_ENTRANCE
- In STATE_AWAITING_ENTRANCE: when entrance IR triggers, NOW open servo (80°), show "Book detected / Keep pushing..."
- Rest of flow unchanged: full entry → closing warning → servo close

### 6. Port Mismatch Fix
Fixed `localhost:5000` → `localhost:5001` in three standalone scripts:
- `backend/simulate_return.py`
- `backend/sim_terminal.py`
- `backend/hw_monitor.py`

### 7. Key System State at End of Session

| Component | Status |
|-----------|--------|
| MySQL | Running (port 3306), root/ebalik123 |
| Flask + Socket.IO | Running (port 5001) |
| SerialBridge | Auto-started in Flask, COM4 |
| Arduino | Firmware uploaded (COM4), door flap angles 10/80 |
| Dashboard | http://localhost:5001, admin/admin123 |

**Books with active borrows (test these):**
| RFID UID | Book | Borrower |
|----------|------|----------|
| 04A1B2C3 | Data Structures and Algorithms | Juan Dela Cruz |
| 04D4E5F6 | Operating System Concepts | Maria Santos |
| 04A3B4C5 | Database System Concepts | Pedro Reyes |

**Do NOT start `hw_monitor.py`** — it conflicts with SerialBridge for COM4.

### 8. Files Created This Session
- `PROJECT_CURRENT_STATE.md` — full project state snapshot
- `arduino/servo_calibration/servo_calibration.ino` — standalone servo test sketch
