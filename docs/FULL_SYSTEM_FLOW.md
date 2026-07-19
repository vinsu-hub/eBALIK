# eBALIK — Full System Flow: Book Return

## Overview

eBALIK (Book Automated Library Inventory Keeper) is an RFID-based library book return system. When a patron returns a borrowed book, they scan the RFID tag at the return station. The system validates the tag against the database, opens a servo-controlled door flap, uses IR sensors to confirm the book is fully inserted, then closes the flap and updates the database — all reflected live on the web dashboard via Socket.IO.

---

## System Architecture

```
┌─────────────┐   USB Serial   ┌─────────────────┐   Socket.IO   ┌──────────────┐
│  Arduino Uno │◄─────────────►│  Flask Backend   │◄─────────────►│   Dashboard   │
│  + MFRC522   │  115200 baud  │  (SerialBridge)  │   WebSocket  │   (Browser)   │
│  + IR Sensors│               │  + MySQL 8.4     │              │               │
│  + Servo     │               │                  │              │               │
└─────────────┘               └─────────────────┘              └──────────────┘
```

**Key components:**
- **Arduino Uno R3** — RFID reader, IR sensors, servo motor, LCD, buzzer, LEDs
- **Flask Backend** — SerialBridge thread, REST API, SQLAlchemy ORM, Socket.IO
- **MySQL Database** — books, borrow_records, return_records, system_logs, users
- **Web Dashboard** — Bootstrap UI, live stat cards, real-time event log

---

## Full System Flow: Book Return

### Phase 1 — RFID Scan (Arduino)

```
STATE_IDLE → "eBALIK Return / Scan your book" on LCD
```

1. `pollForCard()` continuously checks the MFRC522 RFID reader for a tag
2. Tag detected → debounce check: the same UID scanned within 3 seconds is ignored
3. UID extracted from the tag's byte array and converted to uppercase hex string
4. Sent as `RFID,<uid>` over USB serial to the PC
5. LCD updates to "Checking book..."
6. Arduino state transitions to `STATE_AWAITING_VALIDATION` (5-second timeout starts)

### Phase 2 — Backend Validation (SerialBridge)

```
serial_reader.py → _handle_rfid_scan()
```

7. `SerialBridge._handle_line()` receives the `RFID,<uid>` message
8. UID validated against regex `^[0-9A-F]{8}$|^[0-9A-F]{14}$` (4-byte or 7-byte MIFARE)
   - **Malformed UID** → sends `INVALID,<uid>,MALFORMED_UID` → logs WARNING to system_logs
9. Queries `Book` table for a matching `rfid_uid`
   - **Unknown tag** → sends `INVALID,<uid>,UNKNOWN_TAG` → logs WARNING
10. Queries `BorrowRecord` for an open (not yet returned) borrow on that book
    - **Not borrowed** → sends `INVALID,<uid>,NOT_BORROWED` → logs WARNING
11. **Book found + has active borrow** → sends `VALID,<uid>` back to Arduino, emits `scan_result` Socket.IO event

### Phase 3 — VALID Response (Arduino)

```
STATE_AWAITING_VALIDATION → STATE_AWAITING_ENTRANCE
```

12. Arduino receives `VALID,<uid>` via serial
13. Green LED blinks, buzzer chirps (1800 Hz, 100 ms)
14. LCD displays: "Book approved / Insert when ready"
15. Servo stays **closed** (10 degrees) — the door flap does NOT open yet
16. State transitions to `STATE_AWAITING_ENTRANCE` (15-second timeout starts)

### Phase 4 — Book Inserted (Entrance IR Sensor)

```
STATE_AWAITING_ENTRANCE → STATE_AWAIT_FULL_ENTRY
```

17. Patron slides the book into the return slot
18. Entrance IR sensor (pin D3, upper slot) detects the book — must stay LOW for 1s continuously
19. Arduino sends `STATUS,ENTRANCE_DETECTED` to PC
20. Servo **opens** the door flap: 10 degrees → 80 degrees
21. LCD displays: "Book detected / Keep pushing..."
22. State transitions to `STATE_AWAIT_FULL_ENTRY` (8-second timeout starts)

### Phase 5 — Book Fully Inside (Full Entry IR Sensor)

```
STATE_AWAIT_FULL_ENTRY → STATE_CLOSING_WARNING
```

23. Full entry IR sensor (pin D2, bottom compartment) detects the book — single trigger
24. Arduino sends `STATUS,FULL_ENTRY` to PC
25. LCD displays: "Book received! Closing shortly"
26. First closing warning beep plays (double pulse at 1200 Hz)
27. State transitions to `STATE_CLOSING_WARNING` (2-second warning window)

### Phase 6 — Closing Warning

```
STATE_CLOSING_WARNING (2 seconds) → STATE_CLOSING
```

28. At 1 second: second closing warning beep fires
29. At 2 seconds: warning window ends, state transitions to `STATE_CLOSING`

### Phase 7 — Slot Closes + Success

```
STATE_CLOSING → STATE_IDLE
```

30. Servo closes the door flap: 80 degrees → 10 degrees
31. Arduino sends `STATUS,SLOT_CLOSED` then `RETURN_SUCCESS,<uid>` over serial
32. Green LED blinks, success tone plays (two-tone sweep: 1500 Hz → 2000 Hz)
33. LCD displays: "Return success! / Thank you."
34. After 2-second display delay → back to `STATE_IDLE` ("eBALIK Return / Scan your book")

### Phase 8 — Backend Processes Return

```
serial_reader.py → _handle_return_success()
```

35. `SerialBridge` receives `RETURN_SUCCESS,<uid>`
36. Finds the book by `rfid_uid` in the database
37. Finds the open `BorrowRecord` (is_returned=False) for that book
38. **Database update** in a single commit:
    - `borrow_record.is_returned = True`
    - `borrow_record.returned_at = now()`
    - `book.status = "available"`
    - New `ReturnRecord` created (verified_by_sensors=True)
39. Logs event to `system_logs`: "Book 'X' returned successfully"
40. Emits `book_returned` Socket.IO event with title, borrower name, and timestamp

### Phase 9 — Dashboard Live Update

```
socket_client.js → dashboard.js
```

41. `socket_client.js` receives Socket.IO events and dispatches custom DOM events
42. `dashboard.js` listeners handle the events:
    - `ebalik:hardware_status` — live indicator updates through each status message
    - `ebalik:book_returned` — green success indicator, new row prepended to returns table, `refreshStats()` called
43. `refreshStats()` fetches `/api/stats` endpoint → updates the 4 stat cards (total books, available, borrowed, returns today)

---

## Timeout and Failure Paths

| Arduino State | Timeout | Failure Message | Result |
|---------------|---------|-----------------|--------|
| `AWAITING_VALIDATION` | 5 seconds | `RETURN_FAILED,PC_TIMEOUT` | Red LED, error beep, return to IDLE |
| `AWAITING_ENTRANCE` | 15 seconds | `RETURN_FAILED,INSERT_TIMEOUT` | Servo closes, return to IDLE |
| `AWAIT_FULL_ENTRY` | 8 seconds | `RETURN_FAILED,INCOMPLETE_ENTRY` | Servo closes, return to IDLE |

All `RETURN_FAILED` messages are:
- Logged as `ERROR` in the `system_logs` database table
- Emitted via Socket.IO `return_failed` event to the dashboard
- Displayed in the dashboard live indicator and event log

---

## Invalid Scan Paths

| Scenario | Backend Response | Arduino LCD | Dashboard |
|----------|-----------------|-------------|-----------|
| Malformed UID (not 8 or 14 hex chars) | `INVALID,<uid>,MALFORMED_UID` | "Bad tag / read" | WARNING log entry |
| Unknown tag (not in books table) | `INVALID,<uid>,UNKNOWN_TAG` | "Tag not / recognized" | WARNING log entry |
| Book exists but not borrowed | `INVALID,<uid>,NOT_BORROWED` | "Book not / checked out" | WARNING log entry |

All invalid scans:
- Blink the red LED
- Sound an error beep (400 Hz, 300 ms)
- Display error on LCD for 1.5 seconds
- Return to `STATE_IDLE`

---

## State Machine Diagram

```
                              ┌──────────────────────────────────────────┐
                              │                                          │
                              ▼                                          │
                        ┌──────────┐                                     │
            ┌──────────►│   IDLE   │◄────────────────────────────────────┤
            │           └────┬─────┘                                     │
            │                │                                           │
            │         RFID scan detected                                │
            │                │                                           │
            │                ▼                                           │
            │    ┌───────────────────────┐                              │
            │    │ AWAITING_VALIDATION   │                              │
            │    └───────┬───────────────┘                              │
            │            │                                              │
            │     ┌──────┼──────┐                                       │
            │     ▼      ▼      ▼                                       │
            │  VALID  INVALID  TIMEOUT (5s)                             │
            │     │      │      │                                       │
            │     │      │      └──► RETURN_FAILED ─────────────────────┤
            │     │      └──► IDLE  ────────────────────────────────────┤
            │     ▼                                                     │
            │ ┌───────────────────────┐                                 │
            │ │ AWAITING_ENTRANCE     │                                 │
            │ └───────┬───────────────┘                                 │
            │         │                                                 │
            │  ┌──────┼──────┐                                          │
            │  ▼      ▼      ▼                                          │
            │ IR    TIMEOUT (15s)                                       │
            │  │      │                                                 │
            │  │      └──► RETURN_FAILED ───────────────────────────────┤
            │  ▼                                                        │
            │ ┌───────────────────────┐                                 │
            │ │ AWAIT_FULL_ENTRY      │                                 │
            │ └───────┬───────────────┘                                 │
            │         │                                                 │
            │  ┌──────┼──────┐                                          │
            │  ▼      ▼      ▼                                          │
            │ IR    TIMEOUT (8s)                                        │
            │  │      │                                                 │
            │  │      └──► RETURN_FAILED ───────────────────────────────┤
            │  ▼                                                        │
            │ ┌───────────────────────┐                                 │
            │ │ CLOSING_WARNING       │  (2s: double beep warning)      │
            │ └───────┬───────────────┘                                 │
            │         │                                                 │
            │         ▼                                                 │
            │ ┌───────────────────────┐                                 │
            │ │ CLOSING               │  Servo closes, RETURN_SUCCESS   │
            │ └───────┬───────────────┘                                 │
            │         │                                                 │
            │         └──► IDLE  ───────────────────────────────────────┘
            │
            └── (on any error: servo closes, delay, then IDLE)
```

---

## Serial Protocol Reference

### Arduino → PC

| Message | Format | When Sent |
|---------|--------|-----------|
| `RFID,<uid>` | `RFID,04A1B2C3` | Tag scanned by MFRC522 |
| `STATUS,ENTRANCE_DETECTED` | Fixed | Entrance IR sensor triggers |
| `STATUS,FULL_ENTRY` | Fixed | Full entry IR sensor triggers |
| `STATUS,SLOT_CLOSED` | Fixed | Servo closes after return |
| `RETURN_SUCCESS,<uid>` | `RETURN_SUCCESS,04A1B2C3` | Full return cycle completed |
| `RETURN_FAILED,<uid>,<reason>` | `RETURN_FAILED,04A1B2C3,INSERT_TIMEOUT` | Timeout or error |
| `HELLO,EBALIK,<version>` | `HELLO,EBALIK,1.0` | Boot or PING response |

**RETURN_FAILED reasons:** `PC_TIMEOUT`, `INSERT_TIMEOUT`, `INCOMPLETE_ENTRY`

### PC → Arduino

| Message | Format | Effect |
|---------|--------|--------|
| `VALID,<uid>` | `VALID,04A1B2C3` | Book approved, green LED, await insertion |
| `INVALID,<uid>,<reason>` | `INVALID,04A1B2C3,UNKNOWN_TAG` | Book rejected, red LED, error LCD |
| `PING` | Fixed | Arduino replies with `HELLO,EBALIK,1.0` |
| `RESET` | Fixed | Force state machine back to IDLE |

**INVALID reasons:** `UNKNOWN_TAG`, `NOT_BORROWED`, `MALFORMED_UID`

---

## Database Schema

### books
| Column | Type | Notes |
|--------|------|-------|
| book_id | INT PK | Auto-increment |
| rfid_uid | VARCHAR(32) UNIQUE | Nullable (for reassignment) |
| title | VARCHAR(255) | |
| author | VARCHAR(255) | |
| accession_number | VARCHAR(50) UNIQUE | Library accession number |
| category | VARCHAR(100) | |
| status | ENUM | available, borrowed, lost, maintenance |
| created_at | DATETIME | |
| updated_at | DATETIME | Auto-updated |

### borrow_records
| Column | Type | Notes |
|--------|------|-------|
| borrow_id | INT PK | Auto-increment |
| book_id | INT FK → books | |
| borrower_name | VARCHAR(150) | |
| borrower_id | VARCHAR(50) | Student/employee ID |
| borrow_date | DATETIME | |
| due_date | DATETIME | |
| is_returned | BOOLEAN | Default: False |
| returned_at | DATETIME | Set on successful return |

### return_records
| Column | Type | Notes |
|--------|------|-------|
| return_id | INT PK | Auto-increment |
| book_id | INT FK → books | |
| borrow_id | INT FK → borrow_records | Nullable |
| rfid_uid | VARCHAR(32) | |
| returned_at | DATETIME | |
| verified_by_sensors | BOOLEAN | True if IR sensors confirmed |

### system_logs
| Column | Type | Notes |
|--------|------|-------|
| log_id | INT PK | Auto-increment |
| event_type | ENUM | INFO, WARNING, ERROR |
| source | VARCHAR(50) | RFID, RETURN, DASHBOARD, etc. |
| message | VARCHAR(500) | |
| rfid_uid | VARCHAR(32) | Nullable |
| created_at | DATETIME | |

---

## Hardware Pin Map

| Component | Pin | Notes |
|-----------|-----|-------|
| MFRC522 RFID Reader | SS=10, RST=9, SCK=13, MOSI=11, MISO=12 | SPI bus |
| SG90 Servo Motor | D6 | 10 deg closed, 80 deg open |
| IR Sensor — Entrance (upper slot) | D3 | Active LOW, 1s debounce |
| IR Sensor — Full Entry (bottom) | D2 | Active LOW, single trigger |
| Active Buzzer | D5 | Multiple frequencies for different cues |
| Green LED | D7 | Return approved / success |
| Red LED | D8 | Return rejected / error |
| LCD (I2C 16x2) | SDA=A4, SCL=A5, Addr 0x27 | Status messages |

**Pin D4 is unused** — previously assigned to a safety obstruction sensor that has been removed.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `arduino/eBALIK_arduino/eBALIK_arduino.ino` | Arduino firmware (~436 lines) |
| `backend/app/serial_reader.py` | SerialBridge — DB validation, return processing, Socket.IO events |
| `backend/app/routes/api.py` | REST API — stats, device status, RFID listen, reassign tag |
| `backend/app/models.py` | SQLAlchemy models — Book, BorrowRecord, ReturnRecord, SystemLog |
| `backend/app/static/js/socket_client.js` | Socket.IO connection, custom event dispatch |
| `backend/app/static/js/dashboard.js` | Live dashboard updates, stat card refresh |
| `backend/app/static/js/book_rfid_scan.js` | RFID registration + duplicate detection + reassign UI |
| `backend/app/templates/base.html` | Sidebar + topbar layout, 3 FAB buttons |
| `backend/app/static/css/style.css` | Full design system (~1340 lines) |
| `docs/PROTOCOL.md` | Serial protocol specification |
| `currentsystemarchitecture.md` | System architecture documentation |
| `WIRING_GUIDE.md` | Hardware wiring diagrams and BOM |

---

## Servo Calibration Values

| State | Angle | Description |
|-------|-------|-------------|
| Closed | 10 degrees | Door flap shut, default on boot |
| Open | 80 degrees | Door flap open, book can enter |

Calibrated: 2026-07-18. Mechanism: **door flap** (not tilt-drop shelf).

---

## Serial Protocol Constants

| Constant | Value | Description |
|----------|-------|-------------|
| RFID_VALIDATION_TIMEOUT | 5000 ms | Waiting for VALID/INVALID from PC |
| INSERT_TIMEOUT | 15000 ms | Waiting for book insertion after VALID |
| FULL_ENTRY_TIMEOUT | 8000 ms | Waiting for full entry after entrance detected |
| CLOSE_WARNING_MS | 2000 ms | "Closing shortly" warning before servo closes |
| RFID_DEBOUNCE_MS | 3000 ms | Ignore same tag for 3s after scan |

---

## Demo Configuration

- **Flask:** `http://localhost:5001`
- **MySQL:** `127.0.0.1:3306`, root / `ebalik123`, database `ebalik_db`
- **Arduino:** COM port, 115200 baud
- **Admin login:** `admin` / `admin123`
