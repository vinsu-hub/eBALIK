# eBALIK — Current System Context

> Last updated: 2026-07-19
> Firmware: v1.1 (servo opens on VALID)
> Covers complete demo flow end-to-end: startup, scan, validation, gate open, IR sensors, closing, database update, dashboard live refresh.

---

## Complete Demo Flow — Line by Line

### Phase 0 — Startup

**Arduino boots** (`setup()`, `eBALIK_arduino.ino:119`):
1. `Serial.begin(115200)` — opens USB serial
2. `SPI.begin()` + `rfid.PCD_Init()` — starts the RFID reader
3. Sets IR pins as INPUT, buzzer/LEDs as OUTPUT (all LOW)
4. `returnSlotServo.attach(6)` → `write(10)` — gate flap starts **closed**
5. LCD shows `"eBALIK Return / Scan your book"`
6. `sendHello()` → prints `HELLO,EBALIK,1.0` to serial

**Flask starts** (`run.py` → `create_app()`):
1. Connects to MySQL (`ebalik_db`)
2. `init_serial_bridge(app)` starts a daemon thread
3. `SerialBridge._resolve_port()` calls `find_arduino_port()` from `hw_utils.py` — finds CH340 on COM4
4. `SerialBridge._connect()` opens COM4 at 115200 baud
5. Waits 2 seconds for Arduino boot, emits `hw_status_update(connected: true)` via Socket.IO
6. Dashboard badge flips to green "Arduino online"

---

### Phase 1 — User Scans RFID Tag

**Arduino** (`pollForCard()`, `eBALIK_arduino.ino:226`):
1. `rfid.PICC_IsNewCardPresent()` → true (tag detected)
2. `rfid.PICC_ReadCardSerial()` → reads UID bytes
3. `uidToString()` converts bytes → uppercase hex string, e.g. `"27FD6F9E"`
4. Debounce check: if same UID scanned within 3 seconds, ignore
5. `Serial.print("RFID,27FD6F9E\n")` → sends to Flask
6. LCD: `"Checking book... / 27FD6F9E"`
7. `currentState = STATE_AWAITING_VALIDATION` (5-second timeout starts)

**SerialBridge** (`serial_reader.py:150` → `_handle_rfid_scan()`, `serial_reader.py:188`):
1. Parses `"RFID,27FD6F9E"` → extracts UID `"27FD6F9E"`
2. **UID validation** — regex `^[0-9A-F]{8}$|^[0-9A-F]{14}$` → passes (8 hex chars)
3. `Book.query.filter_by(rfid_uid="27FD6F9E")` → finds book in database
4. `BorrowRecord.query.filter_by(book_id=..., is_returned=False)` → finds active borrow
5. **Book found + has open borrow** → `self._send("VALID,27FD6F9E")`
6. `socketio.emit("scan_result", {valid: true, title: ..., borrower: ...})`
7. `log_event("INFO", "RFID", "Book '...' validated for return")`

---

### Phase 2 — Arduino Receives VALID (Gate Opens)

**Arduino** (`handleCommand()`, `eBALIK_arduino.ino:282`):
1. Parses `"VALID,27FD6F9E"` → `cmd = "VALID"`
2. Checks `currentState == STATE_AWAITING_VALIDATION` → yes, proceeds
3. `blinkGreen()` → green LED on D7 blinks (300ms)
4. `beepApproved()` → buzzer: 1800 Hz, 100ms chirp
5. LCD: `"Book approved / Insert when ready"`
6. **`returnSlotServo.write(80)`** → gate flap **OPENS**
7. `currentState = STATE_AWAITING_ENTRANCE` (15-second timeout starts)

---

### Phase 3 — Book Enters Slot (IR1 Triggers)

**Arduino** (main `loop()`, `eBALIK_arduino.ino:161`):
1. `irTriggered(IR_ENTRANCE_PIN)` → reads pin D2, checks if == `LOW` (active state)
2. Book is physically passing the entrance IR sensor → D2 goes LOW → returns true
3. `Serial.println("STATUS,ENTRANCE_DETECTED")` → sent to Flask
4. LCD: `"Book detected / Keep pushing..."`
5. `currentState = STATE_AWAIT_FULL_ENTRY` (8-second timeout starts)

**SerialBridge** (`serial_reader.py:171`):
1. Parses `"STATUS,ENTRANCE_DETECTED"`
2. `socketio.emit("hardware_status", {status: "ENTRANCE_DETECTED"})` → dashboard live indicator updates

---

### Phase 4 — Book Lands in Storage (IR2 Triggers)

**Arduino** (main `loop()`, `eBALIK_arduino.ino:175`):
1. `irTriggered(IR_FULL_ENTRY_PIN)` → reads pin D3, checks if == `LOW`
2. Book has fallen into the storage area → D3 goes LOW → returns true
3. `Serial.println("STATUS,FULL_ENTRY")` → sent to Flask
4. LCD: `"Book received! / Closing shortly"`
5. `beepClosingPulse()` → two beeps at 1200 Hz (first closing warning)
6. `closingPulse2Fired = false`
7. `currentState = STATE_CLOSING_WARNING` (2-second timer starts)

**SerialBridge** (`serial_reader.py:171`):
1. `socketio.emit("hardware_status", {status: "FULL_ENTRY"})` → dashboard updates

---

### Phase 5 — Closing Warning (2 seconds)

**Arduino** (main `loop()`, `eBALIK_arduino.ino:191`):
1. Non-blocking timer — keeps reading serial during the warning
2. At 1 second: `beepClosingPulse()` fires second double-beep (only once per cycle via `closingPulse2Fired` flag)
3. At 2 seconds: `currentState = STATE_CLOSING`

---

### Phase 6 — Gate Closes + Return Success

**Arduino** (main `loop()`, `eBALIK_arduino.ino:208`):
1. `returnSlotServo.write(10)` → gate flap **CLOSES**
2. `Serial.println("STATUS,SLOT_CLOSED")` → sent to Flask
3. `Serial.println("RETURN_SUCCESS,27FD6F9E")` → sent to Flask
4. `blinkGreen()` → green LED blinks
5. `beepSuccess()` → two-tone sweep: 1500 Hz → 2000 Hz
6. LCD: `"Return success! / Thank you."`
7. `goIdleAfterDelay(2000)` → waits 2 seconds → LCD back to `"eBALIK Return / Scan your book"` → `currentState = STATE_IDLE`

**SerialBridge** (`serial_reader.py:224` → `_handle_return_success()`):
1. Finds book by UID in database
2. Finds open `BorrowRecord` for that book
3. **Database commit** (single transaction):
   - `borrow_record.is_returned = True`
   - `borrow_record.returned_at = now()`
   - `book.status = "available"`
   - New `ReturnRecord` inserted (verified_by_sensors=True)
4. `log_event("INFO", "RETURN", "Book '...' returned successfully")`
5. `socketio.emit("book_returned", {uid, title, borrower, returned_at})`

---

### Phase 7 — Dashboard Live Update

**`socket_client.js`** (loaded on all authenticated pages via `base.html`):
1. Receives Socket.IO `book_returned` event
2. Dispatches `window` CustomEvent `ebalik:book_returned`

**`dashboard.js`**:
1. `ebalik:book_returned` listener fires
2. Sets live indicator to green "Return successful"
3. Prepends a new row to "Recent Returns" table
4. `refreshStats()` → fetches `GET /api/stats` → updates 4 stat cards (total, available, borrowed, returns today)

---

## Visual Flow Diagram

```
USER                  ARDUINO              USB SERIAL           FLASK              MYSQL
 │                      │                     │                   │                   │
 │  tap RFID tag        │                     │                   │                   │
 ├─────────────────────>│                     │                   │                   │
 │                      │  RFID,<uid>          │                   │                   │
 │                      ├────────────────────>│                   │                   │
 │                      │                     │  validate UID     │  SELECT books     │
 │                      │                     ├──────────────────>│                   │
 │                      │                     │                   │  SELECT borrows   │
 │                      │                     │                   ├──────────────────>│
 │                      │  VALID,<uid>         │                   │                   │
 │                      │<────────────────────┤                   │                   │
 │  gate FLAP OPENS     │                     │                   │                   │
 │<─────────────────────┤                     │                   │                   │
 │                      │                     │                   │                   │
 │  push book in        │                     │                   │                   │
 ├─────────────────────>│                     │                   │                   │
 │                      │  STATUS,ENTRANCE_DETECTED              │                   │
 │                      ├────────────────────>│                   │                   │
 │                      │                     │  emit hw_status   │                   │
 │                      │                     ├──────────────────>│──> dashboard live  │
 │                      │                     │                   │                   │
 │  book falls in       │                     │                   │                   │
 ├─────────────────────>│                     │                   │                   │
 │                      │  STATUS,FULL_ENTRY  │                   │                   │
 │                      ├────────────────────>│                   │                   │
 │  closing warning     │                     │                   │                   │
 │  (2s, double beep)   │                     │                   │                   │
 │<─────────────────────┤                     │                   │                   │
 │                      │                     │                   │                   │
 │  gate FLAP CLOSES    │                     │                   │                   │
 │<─────────────────────┤                     │                   │                   │
 │  LCD: "Return success!"                   │                   │                   │
 │                      │  RETURN_SUCCESS     │                   │                   │
 │                      ├────────────────────>│                   │                   │
 │                      │                     │  UPDATE borrow    │  UPDATE books     │
 │                      │                     ├──────────────────>│                   │
 │                      │                     │  INSERT return    │                   │
 │                      │                     ├──────────────────>│                   │
 │                      │                     │  emit book_returned                   │
 │                      │                     ├──────────────────>│──> dashboard live  │
 │                      │                     │                   │                   │
 │  back to idle        │                     │                   │                   │
 │<─────────────────────┤                     │                   │                   │
```

---

## State Machine Reference

```
STATE_IDLE ──(RFID scanned)──> STATE_AWAITING_VALIDATION
                                    │
                              ┌─────┴─────┐
                              │            │
                           VALID        INVALID/TIMEOUT
                              │            │
                              ▼            ▼
                    STATE_AWAITING_ENTRANCE   STATE_ERROR_DISPLAY → IDLE
                              │
                        ┌─────┴─────┐
                        │            │
                    IR1 trigger   15s TIMEOUT
                        │            │
                        ▼            ▼
              STATE_AWAIT_FULL_ENTRY  RETURN_FAILED → IDLE
                        │
                  ┌─────┴─────┐
                  │            │
              IR2 trigger   8s TIMEOUT
                  │            │
                  ▼            ▼
        STATE_CLOSING_WARNING  RETURN_FAILED → IDLE
                  │
              2s timer
                  │
                  ▼
            STATE_CLOSING
           (servo closes,
            RETURN_SUCCESS)
                  │
                  ▼
             STATE_IDLE
```

---

## Timeout Reference

| Constant | Value | What happens on timeout |
|----------|-------|------------------------|
| `RFID_VALIDATION_TIMEOUT` | 5000 ms | `RETURN_FAILED,PC_TIMEOUT` → red LED → IDLE |
| `INSERT_TIMEOUT` | 15000 ms | `RETURN_FAILED,INSERT_TIMEOUT` → servo closes → IDLE |
| `FULL_ENTRY_TIMEOUT` | 8000 ms | `RETURN_FAILED,INCOMPLETE_ENTRY` → servo closes → IDLE |
| `CLOSE_WARNING_MS` | 2000 ms | Transitions to CLOSING (servo closes) |
| `RFID_DEBOUNCE_MS` | 3000 ms | Ignores same UID within cooldown |

---

## Hardware Pin Map

| Pin | Component | Direction |
|-----|-----------|-----------|
| D2 | IR Sensor 1 (Entrance) | INPUT |
| D3 | IR Sensor 2 (Full Entry) | INPUT |
| D4 | *(free — previously safety obstruction)* | — |
| D5 | Active Buzzer | OUTPUT |
| D6 | SG90 Servo (gate flap) | OUTPUT (PWM) |
| D7 | Green LED | OUTPUT |
| D8 | Red LED | OUTPUT |
| D9 | MFRC522 RST | OUTPUT |
| D10 | MFRC522 SS (CS) | OUTPUT |
| D11 | MFRC522 MOSI | OUTPUT |
| D12 | MFRC522 MISO | INPUT |
| D13 | MFRC522 SCK | OUTPUT |
| A4 | LCD SDA | I2C |
| A5 | LCD SCL | I2C |

---

## Serial Protocol Reference

### Arduino → PC (115200 baud, `\n` terminated)

| Message | Format | When |
|---------|--------|------|
| HELLO | `HELLO,EBALIK,<version>` | Boot / PING response |
| RFID | `RFID,<uid>` | Tag scanned |
| STATUS | `STATUS,ENTRANCE_DETECTED` | Entrance IR triggered |
| STATUS | `STATUS,FULL_ENTRY` | Full entry IR triggered |
| STATUS | `STATUS,SLOT_CLOSED` | Servo closes |
| RETURN_SUCCESS | `RETURN_SUCCESS,<uid>` | Full cycle completed |
| RETURN_FAILED | `RETURN_FAILED,<uid>,<reason>` | Timeout or error |

### PC → Arduino

| Message | Format | Effect |
|---------|--------|--------|
| VALID | `VALID,<uid>` | Green LED, servo opens, await insertion |
| INVALID | `INVALID,<uid>,<reason>` | Red LED, error LCD, return to IDLE |
| PING | `PING` | Arduino replies HELLO |
| RESET | `RESET` | Force state machine to IDLE |

**INVALID reasons:** `UNKNOWN_TAG`, `NOT_BORROWED`, `MALFORMED_UID`
**RETURN_FAILED reasons:** `PC_TIMEOUT`, `INSERT_TIMEOUT`, `INCOMPLETE_ENTRY`

---

## Servo Calibration

| State | Angle | Description |
|-------|-------|-------------|
| Closed | 10° | Gate flap shut (default on boot) |
| Open | 80° | Gate flap open, book can enter |

Calibrated: 2026-07-18. Mechanism: **door flap / gate flap**.

---

## Software Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| MCU | Arduino Uno R3 (CH340) | ATmega328P |
| Firmware | Arduino C++ | v1.1 |
| Web Framework | Flask | 3.0.3 |
| ORM | Flask-SQLAlchemy | 3.1.1 |
| Auth | Flask-Login | 0.6.3 |
| Live Updates | Flask-SocketIO | 5.3.6 (threading mode) |
| Database | MySQL (PyMySQL) | 8.4.9 |
| Serial | pyserial | 3.5 |
| Frontend | Jinja2 + Bootstrap 5.3 | — |
| Socket.IO Client | Socket.IO | 4.7.5 |

---

## Database Schema (5 tables)

```
users          → user_id, username, password_hash, full_name, role, created_at
books          → book_id, rfid_uid (nullable, unique), title, author, accession_number, category, status, created_at, updated_at
borrow_records → borrow_id, book_id (FK), borrower_name, borrower_id, borrow_date, due_date, is_returned, returned_at
return_records → return_id, book_id (FK), borrow_id (FK, nullable), rfid_uid, returned_at, verified_by_sensors
system_logs    → log_id, event_type, source, message, rfid_uid, created_at
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `arduino/eBALIK_arduino/eBALIK_arduino.ino` | Arduino firmware (436 lines) |
| `backend/run.py` | Flask entry point (port 5001) |
| `backend/app/__init__.py` | App factory + blueprint registration |
| `backend/app/extensions.py` | db, login_manager, socketio singletons |
| `backend/app/models.py` | SQLAlchemy models (5 tables) |
| `backend/app/serial_reader.py` | SerialBridge — UID validation, reconnect, DB updates |
| `backend/app/hw_utils.py` | CH340 port detection |
| `backend/app/routes/api.py` | REST API (stats, hw-status, rfid, reassign-tag) |
| `backend/app/routes/auth.py` | Login/logout |
| `backend/app/routes/books.py` | Book CRUD + manual borrow |
| `backend/app/routes/dashboard.py` | Dashboard + records pages |
| `backend/app/static/js/socket_client.js` | Socket.IO connection + CustomEvent dispatch |
| `backend/app/static/js/dashboard.js` | Live dashboard updates |
| `backend/app/static/js/book_rfid_scan.js` | RFID registration + duplicate state |
| `backend/app/static/css/style.css` | Full design system (~1340 lines) |
| `backend/app/templates/base.html` | Sidebar + topbar layout, 3 FAB buttons |
| `backend/schema.sql` | MySQL schema |
| `backend/seed_data.sql` | Demo data |
| `docs/PROTOCOL.md` | Serial protocol specification |
| `docs/FULL_SYSTEM_FLOW.md` | Full system flow documentation |
| `WIRING_GUIDE.md` | Hardware wiring diagrams and BOM |
| `currentsystemarchitecture.md` | System architecture documentation |

---

## Demo Configuration

- **Flask:** `http://localhost:5001`
- **MySQL:** `127.0.0.1:3306`, root / `ebalik123`, database `ebalik_db`
- **Arduino:** COM port (auto-detected), 115200 baud
- **Admin login:** `admin` / `admin123`
- **Serial:** `SERIAL_ENABLED=true`, `DEBUG_MODE=true`

---

## Error Paths

### Invalid Scan Scenarios

| Scenario | Backend Response | Arduino LCD | Red LED |
|----------|-----------------|-------------|---------|
| Malformed UID (not 8 or 14 hex chars) | `INVALID,<uid>,MALFORMED_UID` | "Bad tag / read" | Blink |
| Unknown tag (not in books table) | `INVALID,<uid>,UNKNOWN_TAG` | "Tag not / recognized" | Blink |
| Book exists but not borrowed | `INVALID,<uid>,NOT_BORROWED` | "Book not / checked out" | Blink |

All invalid scans: error beep (400 Hz, 300ms) → display 1.5s → return to IDLE.

### Timeout Scenarios

| State | Timeout | Failure | LCD |
|-------|---------|---------|-----|
| AWAITING_VALIDATION | 5s | `RETURN_FAILED,PC_TIMEOUT` | "No response / Try again" |
| AWAITING_ENTRANCE | 15s | `RETURN_FAILED,INSERT_TIMEOUT` | "Timeout / No book inserted" |
| AWAIT_FULL_ENTRY | 8s | `RETURN_FAILED,INCOMPLETE_ENTRY` | "Incomplete / Book not fully in" |

All timeouts: red LED blink → servo closes (if open) → return to IDLE.

### Reconnect Behavior

- On `SerialException`: SerialBridge emits `hw_status_update(connected: false)`, closes port, retries `_connect()` every 5 seconds
- Each retry re-calls `_resolve_port()` to find Arduino if it moved to a different COM port
- Dashboard badge flips to red "Arduino offline" on disconnect, back to green on reconnect
- `socket_client.js` `connect` handler fetches `/api/hw-status` and calls `refreshStats()` to resync stale data
