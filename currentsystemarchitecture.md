# eBALIK — Current System Architecture

> Last updated: 2026-07-12
> Covers hardware, firmware, backend, frontend, serial protocol, data flow,
> CH340 integration, RFID tag registration, and system hardening
> (UID validation, INVALID reason field, debounce, reconnect, DEBUG_MODE gating).

---

## 1. System Overview

**eBALIK** (Book Automated Library Inventory Keeper) is an RFID-based automated
book return station. A physical return box with sensors, a servo-controlled slot,
an RFID reader, LCD, and buzzer is controlled by an Arduino Uno R3. The Arduino
communicates over USB Serial to a local Flask + MySQL web dashboard running on a
single laptop. Librarians manage the catalog and watch returns happen in real
time via Socket.IO.

```
  ┌──────────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
  │  RFID    │     │         │     │  Flask   │     │  MySQL   │
  │  RC522   │────▶│ Arduino │────▶│  Server  │────▶│  DB      │
  │  (SPI)   │     │  Uno R3 │     │ (Python) │     │  8.4.9   │
  └──────────┘     │         │     └────┬─────┘     └──────────┘
                   │  USB    │          │ Socket.IO
   ┌──────────┐    │  Serial │     ┌────▼─────┐
   │  3x IR   │    │ (115200)│     │  Browser │
   │ Sensors  │◀───│         │     │  (Admin)  │
   └──────────┘    │         │     └──────────┘
   ┌──────────┐    │  PWM    │
   │  Servo   │◀───│  pin 6  │
   │  SG90    │    │         │
   └──────────┘    │         │
   ┌──────────┐    │  I2C    │
   │  16x2    │◀───│  addr   │
   │  LCD     │    │  0x27   │
   └──────────┘    │         │
   ┌──────────┐    │  pin 5  │
   │  Buzzer  │◀───│         │
   └──────────┘    │         │
   ┌──────────┐    │  pin 7  │
   │  Green   │◀───│  (LED)  │
   │  LED     │    │         │
   └──────────┘    │         │
   ┌──────────┐    │  pin 8  │
   │  Red     │◀───│  (LED)  │
   │  LED     │    │         │
   └──────────┘    └─────────┘
```

---

## 2. Hardware Architecture

### 2.1 Bill of Materials

| Component | Specification | Function |
|-----------|--------------|----------|
| Arduino Uno R3 | ATmega328P, 5V, 16 MHz | Main MCU, runs state machine |
| RFID Reader | RC522, 13.56 MHz (SPI) | Reads RFID tag UIDs |
| RFID Tags | 13.56 MHz sticker/card | Unique ID per book |
| Servo Motor | SG90, 5V | Opens/closes return slot |
| IR Sensor (Entrance) | Obstacle sensor | Detects book entering slot |
| IR Sensor (Full Entry) | Obstacle sensor | Confirms full insertion |
| IR Sensor (Safety) | Obstacle sensor | Detects obstructions before closing |
| LCD Display | 16x2, I2C (addr 0x27) | User feedback messages |
| Buzzer | Active, 5V | Audible confirmation/alerts |
| Green LED | 5mm, with 220Ω resistor | Visual: return approved (pin D7) |
| Red LED | 5mm, with 220Ω resistor | Visual: return rejected (pin D8) |

### 2.2 Pin Assignments

| Arduino Pin | Component | Notes |
|-------------|-----------|-------|
| SS=10, RST=9 | MFRC522 RFID | SPI bus |
| 6 | SG90 Servo | PWM signal |
| 2 | IR Sensor 1 (Entrance) | Active LOW |
| 3 | IR Sensor 2 (Full Entry) | Active LOW |
| 4 | IR Sensor 3 (Safety) | Active LOW |
| 5 | Active Buzzer | Digital HIGH = on |
| 7 | Green LED | Return approved indicator (220Ω to GND) |
| 8 | Red LED | Return rejected indicator (220Ω to GND) |
| A4 (SDA), A5 (SCL) | I2C LCD | Address 0x27 |

---

## 3. Firmware State Machine (Arduino)

The Arduino firmware (`arduino/eBALIK_arduino/eBALIK_arduino.ino`) implements
a 7-state machine. The Wokwi variant (`wokwi/eBALIK_wokwi.ino`) is identical
except `IR_ACTIVE_STATE = HIGH` (pushbuttons replace IR sensors) and adds a
`SIMULATE_UID` debug command.

```
                    ┌──────────────────────────────────────────────┐
                    │                                              ▼
  ┌─────────┐  RFID  ┌───────────────┐  VALID   ┌───────────────┐
  │  IDLE   │───────▶│   AWAITING    │─────────▶│  SLOT_OPEN    │
  │         │        │  VALIDATION   │          │ AWAIT_ENTRANCE │
  └─────────┘        └───────┬───────┘          └───────┬───────┘
       ▲                     │                          │
       │                     │ INVALID                  │ Entrance IR
       │                     ▼                          │ triggered
       │              ┌───────────────┐                 ▼
       │              │  ERROR_DISPLAY│     ┌──────────────────────┐
       │              │  (5s, then    │     │  AWAIT_FULL_ENTRY    │
       │              │   go idle)    │     │  (Full Entry IR)     │
       │              └───────────────┘     └───────────┬──────────┘
       │                                                │ Full IR
       │                                                ▼
       │                              ┌──────────────────────────────┐
       │                              │  AWAIT_OBSTRUCTION_CLEAR     │
       │                              │  (Safety IR clear)           │
       │                              └───────────┬──────────────────┘
       │                                            │ Clear
       │                                            ▼
       │                              ┌──────────────────────────────┐
       │                              │  CLOSING                     │
       │                              │  (servo close, send          │
       │                              │   RETURN_SUCCESS, then idle) │
       └──────────────────────────────┴──────────────────────────────┘
```

**Timeouts:**
- AWAITING_VALIDATION: 5s → ERROR_DISPLAY
- SLOT_OPEN: 15s → IDLE (no entry detected)
- AWAIT_FULL_ENTRY: 8s → IDLE
- AWAIT_OBSTRUCTION_CLEAR: 10s → IDLE
- RFID debounce: 3s cooldown on same UID after scan (prevents duplicate scans)

---

## 4. Serial Protocol

Line-based, comma-separated, `\n` terminated at 115200 baud.

### 4.1 Arduino → PC

| Message | Format | When |
|---------|--------|------|
| HELLO | `HELLO,EBALIK,<version>` | On boot / after PING |
| RFID | `RFID,<uid>` | Tag scanned at slot |
| STATUS | `STATUS,<state>` | Sensor state change |
| RETURN_SUCCESS | `RETURN_SUCCESS,<uid>` | Slot closed, book accepted |
| RETURN_FAILED | `RETURN_FAILED,<uid>,<reason>` | Validation/flow failure |

### 4.2 PC → Arduino

| Message | Format | When |
|---------|--------|------|
| VALID | `VALID,<uid>` | UID exists + has open borrow |
| INVALID | `INVALID,<uid>,<reason>` | UID unknown or not borrowed. Reasons: `UNKNOWN_TAG`, `NOT_BORROWED`, `MALFORMED_UID` |
| PING | `PING` | Connection check |
| RESET | `RESET` | Return to IDLE state |

---

## 5. Backend Architecture

### 5.1 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Flask | 3.0.3 |
| ORM | Flask-SQLAlchemy | 3.1.1 |
| Auth | Flask-Login | 0.6.3 |
| Live Updates | Flask-SocketIO | 5.3.6 (threading mode) |
| Database | MySQL (PyMySQL) | 8.4.9 |
| Serial | pyserial | 3.5 |
| Templates | Jinja2 + Bootstrap 5.3 | — |
| Frontend JS | Socket.IO client 4.7.5 | — |

### 5.2 App Factory (`app/__init__.py`)

```
create_app()
  ├── Init extensions (db, login_manager, socketio)
  ├── Register blueprints:
  │   ├── auth_bp      → /login, /logout
  │   ├── dashboard_bp → /, /logs, /records/borrow, /records/return
  │   ├── books_bp     → /books/ (CRUD + borrow)
  │   └── api_bp       → /api/* (stats, logs, hw-status, rfid, launch)
  └── Start SerialBridge background thread
       └── init_serial_bridge(app)
            └── SerialBridge(app, port, baud, enabled)
                 └── daemon thread → _run()
```

### 5.3 Database Models (5 tables)

```
users
  user_id (PK), username (unique), password_hash, full_name, role (ENUM)

books
  book_id (PK), rfid_uid (nullable, unique), title, author, accession_number,
  category, status (ENUM), created_at, updated_at
  └── FK relationships: borrow_records, return_records
  └── rfid_uid nullable to support tag reassignment between books

borrow_records
  borrow_id (PK), book_id (FK→books), borrower_name, borrower_id,
  borrow_date, due_date, is_returned, returned_at

return_records
  return_id (PK), book_id (FK→books), borrow_id (FK→borrow_records),
  rfid_uid, returned_at, verified_by_sensors

system_logs
  log_id (PK), event_type (ENUM), source, message, rfid_uid, created_at
```

### 5.4 SerialBridge (`app/serial_reader.py`)

Runs as a daemon thread. Structure:

```
SerialBridge
  ├── Attributes: app, port, baud, enabled, ser, mode, _reg_timer
  ├── start() / stop()
  ├── start_registration_mode(timeout=15) / cancel_registration_mode()
  ├── _connect()       → auto-resolves port, re-resolves on each retry
  ├── _run()           → threaded loop: read line → _handle_line()
  │   └── On SerialException: emit hw_status_update(false), reconnect
  ├── _handle_line()   → dispatches: HELLO/RFID/STATUS/RETURN_SUCCESS/RETURN_FAILED
  │   └── RFID check: if mode=="listening_for_registration"
  │       → emit rfid_registration_scan, skip return flow
  │       else → _handle_rfid_scan()
  ├── _handle_rfid_scan()     → validate UID format (regex), query DB, send VALID/INVALID+reason
  ├── _handle_return_success() → update DB, emit book_returned
  └── _handle_return_failed()  → log error, emit return_failed
```

**UID validation:** `_handle_rfid_scan()` validates UIDs against `^[0-9A-F]{8}$|^[0-9A-F]{14}$`
(4-byte or 7-byte MIFARE). Malformed UIDs log a WARNING to `system_logs` and emit
`MALFORMED_UID` reason — never silently accepted.

**Auto-detection logic in `init_serial_bridge`:** if `SERIAL_PORT` is empty or
`"COM3"` (the old default), calls `find_arduino_port()` from `app/hw_utils.py`
to locate the first CH340 device. Falls back gracefully if none found.

**Reconnect logic:** on `SerialException` in `_run()`, the bridge emits
`hw_status_update(connected: false)`, closes the port, and retries `_connect()`.
Each retry re-calls `_resolve_port()` so the bridge can find the Arduino if it
moved to a different COM port after replug.

### 5.5 API Endpoint Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/login` | Authenticate |
| GET | `/logout` | Log out |
| GET | `/` | Dashboard (stats, returns, log) |
| GET | `/logs` | System logs page |
| GET | `/records/borrow` | Borrow records page |
| GET | `/records/return` | Return records page |
| GET | `/books/` | Book catalog (search via `?q=`) |
| POST | `/books/add` | Add book |
| POST | `/books/<id>/edit` | Edit book |
| POST | `/books/<id>/delete` | Delete book |
| POST | `/books/<id>/borrow` | Manual borrow |
| GET | `/api/stats` | JSON: book counts |
| GET | `/api/logs/recent` | JSON: 20 recent logs |
| GET | `/api/device/status` | JSON: SerialBridge connected |
| GET/POST | `/api/hw-status` | CH340 handshake state |
| POST | `/api/rfid/start-listen` | Enter registration mode |
| POST | `/api/rfid/cancel-listen` | Exit registration mode |
| GET | `/api/books/check-uid` | Duplicate tag check |
| POST | `/api/books/reassign-tag` | Move RFID tag between books (transactional) |
| POST | `/api/simulate/scan` | Dev: fake RFID scan (DEBUG_MODE only) |
| POST | `/api/terminal/launch` | Spawn sim_terminal.py (DEBUG_MODE only) |
| POST | `/api/hw-monitor/launch` | Spawn hw_monitor.py (DEBUG_MODE only) |

> **Dev-only endpoints** (`/api/simulate/scan`, `/api/terminal/launch`,
> `/api/hw-monitor/launch`) require `DEBUG_MODE=true` in `.env`. They return
> 403 when `DEBUG_MODE` is not set.

---

## 6. Frontend Architecture

### 6.1 Stack

| Layer | Technology |
|-------|-----------|
| HTML Templates | Jinja2 (7 files) extending base.html |
| CSS | Custom design system (~1340 lines, 30KB) |
| CSS Framework | Bootstrap 5.3.3 (grid, modals, alerts) |
| Icons | Bootstrap Icons 1.11.3 |
| Font | Inter (Google Fonts) |
| Real-time | Socket.IO 4.7.5 |
| Sidebar State | localStorage (key: `ebalik-sidebar-collapsed`) |

### 6.2 Design System (`style.css`)

- CSS custom properties for colors, typography, spacing, shadows, transitions
- Navy (#1e293b) primary, Forest Green (#059669) accent, Slate neutrals
- Fluid `clamp()` typography across 5 breakpoints
- Data tables with responsive card layout (<768px hides thead, uses `data-label`)
- Status pills: success/warning/danger/info/neutral/secondary
- FAB stack (bottom-right) for hw-monitor and terminal launchers
- Login page: gradient background with decorative circles

### 6.3 JS Event Architecture (2-layer)

```
Server (Socket.IO)
  │
  ├── device_status
  ├── hw_status_update ─────────────────────────────────────────────────┐
  ├── scan_result                                                       │
  ├── hardware_status                                                   │
  ├── book_returned                                                     │
  ├── return_failed                                                     │
  ├── rfid_registration_scan ────┐                                     │
  └── rfid_registration_timeout ──┤                                     │
                                  │                                     │
                     ┌────────────▼────────────┐                       │
                     │  socket_client.js       │                       │
                     │  (loaded on all auth     │                       │
                     │   pages via base.html)   │                       │
                     │                          │                       │
                     │  dispatches window       │                       │
                     │  CustomEvents:           │                       │
                     │  ebalik:scan_result      │                       │
                     │  ebalik:hw_status_update─┼───────────────────────┘
                     │  ebalik:rfid_reg...      │
                     └────────────┬────────────┘
                                  │
          ┌───────────────────────┼───────────────────────────────┐
          │                       │                               │
          ▼                       ▼                               ▼
  dashboard.js              book_rfid_scan.js              (future pages)
  (dashboard.html only)     (books.html only)

  Listens to:               Listens to:
  ebalik:scan_result        ebalik:rfid_registration_scan
  ebalik:hw_status_update   ebalik:rfid_registration_timeout
  ebalik:book_returned
  ebalik:return_failed

- `socket_client.js`: on `connect` event (fires on reconnect too), fetches
  `/api/hw-status` and calls `refreshStats()` to resync stale dashboard data.
```

### 6.4 Pages

| Page | Template | Key Features |
|------|----------|-------------|
| Login | `login.html` | Standalone, gradient, decorative circles |
| Dashboard | `dashboard.html` | 4 stat cards, recent returns, overdue, live log |
| Books | `books.html` | Search, data table, Add modal with "Scan to Register" button |
| Borrow Records | `borrow_records.html` | Data table with responsive columns |
| Return Records | `return_records.html` | Data table with sensor verification column |
| System Logs | `system_logs.html` | Data table with color-coded event type pills |

---

## 7. CH340 Integration

### 7.1 Shared Module (`app/hw_utils.py`)

```python
CH340_IDS = {("1A86", "7523"), ("1A86", "5523")}

list_candidate_ports()
  → Filters out ports without VID/PID (e.g. COM1)
  → Returns list of dicts: {device, description, vid_pid, is_ch340}
  → Sorted: CH340 matches first

find_arduino_port()
  → Returns first CH340 device.device or None
```

### 7.2 hw_monitor.py (P0 Fix)

- **Window-stays-open:** top-level `try/except Exception` + `input()` on all exits
- **Port detection:** uses `list_candidate_ports()` instead of raw `comports()`
- **POST to Flask:** on HELLO → `POST /api/hw-status {"connected": true, "port": ..., "vid_pid": ...}`
- **Disconnect cleanup:** POSTs `{"connected": false}` on exit / connection loss
- **Launch:** spawned with `cmd /K python hw_monitor.py` so CMD window persists

### 7.3 `/api/hw-status` Endpoint

- In-memory `_hw_status = {"connected": False, "port": "", "vid_pid": ""}`
- `POST`: stores state, emits `hw_status_update` + `device_status` via Socket.IO
- `GET`: returns current cached state
- Frontend badge updates via `hw_status_update` listener in `socket_client.js`

### 7.4 Setup Scripts

- `tools/install_ch340_driver.bat` — self-elevating, launches WCH CH341SER.EXE
- `setup.bat` — full env setup: Python venv + deps, CH340 driver, MySQL check, .env + schema

---

## 8. RFID Tag Registration

### 8.1 Flow

```
User clicks "Scan to Register" button
  │
  ├── fetch POST /api/rfid/start-listen
  │   └── Bridge.mode = "listening_for_registration"
  │   └── Timer starts (15s)
  │   └── Returns {"listening": True}
  │
  ├── Frontend shows spinner + countdown
  │
  ├── User scans physical tag
  │   └── Arduino sends "RFID,<uid>" over serial
  │   └── Bridge._handle_line() sees mode == "listening_for_registration"
  │       ├── Cancel timer
  │       ├── Reset mode to "idle"
  │       ├── Emit socket.io "rfid_registration_scan" with UID
  │       └── Skip return-flow logic (no DB validation, no servo)
  │
  ├── Frontend receives event
  │   ├── Fill UID input
  │   ├── Fetch GET /api/books/check-uid?uid=<uid>
  │   │   └── If duplicate → red warning with existing book title
  │   ├── Show "Tag <UID> will be assigned to <Title>"
  │   └── User clicks Save
  │
  └── On modal close / page navigate:
      └── fetch POST /api/rfid/cancel-listen
```

### 8.2 State Machine (`book_rfid_scan.js`)

| State | Button | Status Area |
|-------|--------|-------------|
| idle | "Scan to Register" enabled | empty |
| disabled | greyed out, tooltip "Connect Arduino first" | "Arduino not connected" |
| listening | spinner + "Listening..." | "Waiting for tag scan... 15s" (countdown) |
| success | green checkmark | green: "Tag <UID> → <Title>" |
| timeout | warning icon | yellow: "No tag detected — try again" |
| duplicate | warning icon (disabled) + "Reassign to this book" button | red: "Tag belongs to <other book>" + UID stays visible |
| error | red warning | red: error message |

- `hidden.bs.modal` event fires `cancelScanListen()` and resets all state
- Title input `input` event updates the binding text live on success state
- UID input `input` event resets duplicate/error state back to idle
- "Reassign to this book" button calls `POST /api/books/reassign-tag`
  (single-transaction UID move, clears old binding, assigns to new book)
- Server-side duplicate check on save still applies (section 3.3 of original plan)

---

## 9. Data Flow Diagrams

### 9.1 Return Flow (normal operation)

```
1. User taps RFID-tagged book at reader
2. Arduino reads UID, sends "RFID,<uid>" over serial
3. SerialBridge receives line
4. SerialBridge._handle_line() → _handle_rfid_scan()
5. Validate UID format (^[0-9A-F]{8}$ or ^[0-9A-F]{14}$)
   ├── Malformed → log WARNING, emit scan_result {MALFORMED_UID},
   │               send "INVALID,<uid>,MALFORMED_UID", skip
   ├── Not found → emit scan_result {valid: false, UNKNOWN_TAG}
   │             → send "INVALID,<uid>,UNKNOWN_TAG"
   │             → Arduino goes to ERROR_DISPLAY state
   ├── Found, no open borrow → emit scan_result {valid: false, NOT_BORROWED}
   │                         → send "INVALID,<uid>,NOT_BORROWED"
   │                         → Arduino goes to ERROR_DISPLAY state
   └── Found, open borrow exists → emit scan_result {valid: true}
                                 → send "VALID,<uid>"
                                 → Arduino opens servo slot (IR sequence)
6. Arduino tracks: Entrance IR → Full Entry IR → Safety Clear
7. Arduino sends "RETURN_SUCCESS,<uid>"
8. SerialBridge._handle_return_success():
   ├── Close borrow record (is_returned=True, returned_at=now)
   ├── Create return_record row
   ├── Set book.status = "available"
   ├── log_event "INFO"
   └── emit "book_returned" via Socket.IO
9. Frontend dashboard.js receives event:
   ├── Prepend to live log
   ├── Prepend to recent returns table
   └── refreshStats() from /api/stats
```

### 9.2 Registration Flow (new tag binding)

```
1. User opens Add Book modal on /books/ page
2. UI checks Arduino badge → if offline, button disabled
3. User clicks "Scan to Register"
4. Frontend POST /api/rfid/start-listen
5. SerialBridge.mode = "listening_for_registration", timer starts
6. User scans tag at reader
7. Arduino sends "RFID,<uid>"
8. SerialBridge._handle_line() intercepts at cmd=="RFID":
   ├── Cancel timer
   ├── Set mode = "idle"
   ├── Emit "rfid_registration_scan" with UID
   └── Return (no VALID/INVALID sent, no servo action)
9. Frontend receives event:
   ├── Fill UID input
   ├── GET /api/books/check-uid for duplicate check
   └── Show binding confirmation text
10. User fills title/author/etc and clicks Submit
11. POST /books/add — server validates duplicate UID again, saves
```

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Socket.IO threading mode | Avoids eventlet monkey-patch issues; fine for single-laptop demo |
| SerialBridge daemon thread | Gracefully skips if SERIAL_ENABLED=false or pyserial missing |
| Mode A for CH340 (diagnostic → handoff) | Single source of truth (SerialBridge inside Flask); lower risk than Mode B |
| Registration mode on bridge (not separate endpoint) | Ensures atomic scan routing; no race between registration and return flow |
| 15s timeout with threading.Timer | Prevents bridge getting stuck in registration mode if user walks away |
| Two-layer JS events (socket_client → window CustomEvent) | Decouples connection from page logic; future pages just listen for events |
| localStorage sidebar state | Survives page navigation without server round-trip |
| cmd /K for CLI tool launch | P0 fix: CMD window no longer closes instantly on script exit |
| VID:PID filtering for CH340 | Ignores COM1-style phantom ports; only matches real USB-serial adapters |
| UID format validation at all entry points | Prevents malformed reads from being silently accepted; logs WARNING for reader hardware diagnostics |
| DEBUG_MODE gating for dev endpoints | Simulate/terminal/hw-monitor endpoints blocked in production; prevents process injection from network |
| RFID debounce (3s same-UID cooldown) | Prevents duplicate scans when tag is held on reader; firmware-level guard |
| Port re-resolution on reconnect | `_connect()` re-calls `_resolve_port()` on each retry, handles Arduino moving to different COM port after replug |
| Tag reassignment in single transaction | `POST /api/books/reassign-tag` clears old book's UID and assigns to new book atomically; prevents half-completed state |

---

## 11. Complete File Map

```
D:\eBALIK\
├── .gitignore                        # Python, .env, venv, __pycache__
├── README.md                         # Setup guide + architecture overview
├── SESSION_HANDOFF.md                # Session notes (restart/stop commands)
├── setup.bat                         # Full environment setup script
├── WIRING_GUIDE.md                   # Complete wiring guide with pin map + wire colors
├── currentsystemarchitecture.md      # This file
│
├── arduino/
│   └── eBALIK_arduino/
│       └── eBALIK_arduino.ino        # Physical Arduino firmware (~365 lines)
│
├── backend/
│   ├── .env                          # Active config (SERIAL_PORT, DEBUG_MODE, etc.)
│   ├── .env.example                  # Template with defaults
│   ├── config.py                     # Config class via python-dotenv
│   ├── create_admin.py              # CLI admin user creator
│   ├── hw_monitor.py                # Standalone serial monitor + CH340 POST
│   ├── requirements.txt             # 9 Python dependencies
│   ├── run.py                       # Entry point: socketio.run(app, port=5000)
│   ├── schema.sql                   # MySQL schema (5 tables + indexes)
│   ├── seed_data.sql                # Demo data (5 books, 3 borrows, admin)
│   ├── sim_terminal.py              # Interactive CMD RFID simulator
│   ├── simulate_return.py           # Batch return simulator
│   │
│   └── app/
│       ├── __init__.py              # App factory + blueprint registration
│       ├── extensions.py            # db, login_manager, socketio singletons
│       ├── hw_utils.py              # CH340 port detection (shared module)
│       ├── models.py                # 5 SQLAlchemy models + log_event()
│       ├── serial_reader.py         # SerialBridge (daemon thread, UID validation, reconnect)
│       │
│       ├── routes/
│       │   ├── __init__.py          # Empty
│       │   ├── api.py               # REST endpoints (stats, hw-status, rfid, reassign-tag; dev endpoints gated behind DEBUG_MODE)
│       │   ├── auth.py              # /login, /logout
│       │   ├── books.py             # Book CRUD + manual borrow
│       │   └── dashboard.py         # Dashboard + records pages
│       │
│       ├── static/
│       │   ├── css/
│       │   │   └── style.css        # Full design system (~1340 lines)
│       │   └── js/
│       │       ├── book_rfid_scan.js   # RFID registration scan button logic
│       │       ├── dashboard.js        # Live dashboard updates
│       │       └── socket_client.js    # Socket.IO connection + event dispatch
│       │
│       └── templates/
│           ├── base.html             # Sidebar + topbar layout, FABs
│           ├── login.html            # Standalone login page
│           ├── dashboard.html        # Stat cards, returns, overdue, live log
│           ├── books.html            # Book catalog + Add modal with scan button
│           ├── borrow_records.html   # Borrow history
│           ├── return_records.html   # Return history
│           └── system_logs.html      # System log table
│
├── docs/
│   └── PROTOCOL.md                  # Serial protocol specification
│
├── tools/
│   ├── install_ch340_driver.bat     # Self-elevating CH340 driver installer
│   ├── install_mysql_service.bat    # MySQL 8.4 Windows service installer
│   └── drivers/
│       └── README.md                # Driver source tracking
│
└── wokwi/
    ├── diagram.json                 # Wokwi circuit (11 parts, 27 connections)
    ├── eBALIK_wokwi.ino             # Wokwi-adapted firmware
    └── libraries.txt                # MFRC522, LiquidCrystal I2C
```
