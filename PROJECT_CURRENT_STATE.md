# eBALIK — Project Current State (2026-07-18)

## What eBALIK Is

RFID-based book return station. A physical return box with a door flap mechanism, 2 IR sensors, LCD, and buzzer, controlled by an Arduino Uno R3 communicating over USB Serial to a Flask + MySQL web dashboard running on localhost.

**Admin login:** `admin` / `admin123`  
**DB:** MySQL 8.4.9, `ebalik_db`, root password `ebalik123`  
**Arduino:** COM4, firmware v1.0, compiled and uploaded  
**Flask:** running on `http://localhost:5001`, SerialBridge connected to COM4  

---

## Today's Work

### 1. Environment Setup (from scratch)

- Installed Python 3.13.14 via winget
- Created venv at `backend/venv` + installed all 10 direct + 20 transitive pip dependencies
- Created `backend/.env` from `.env.example` (SECRET_KEY, DB_PASSWORD=ebalik123, SERIAL_ENABLED=true, DEBUG_MODE=true)
- Initialized MySQL 8.4.9 data directory, started server (PID 3608), set root password, loaded `schema.sql` + `seed_data.sql`, created admin user
- CH340 driver installed via `SETUP.EXE /S`
- Installed arduino-cli v1.5.1, AVR core 1.8.8, libraries: MFRC522 v1.4.12, LiquidCrystal I2C v1.1.2, Servo v1.3.0
- Fixed admin password hash in MySQL (seed had truncated scrypt hash)

### 2. Obstruction Sensor Removal Propagation

The original design had 3 IR sensors (Entrance, Full Entry, Safety Obstruction). Safety Obstruction (pin D4) was removed from the firmware. A closing warning module (2s delay, double beep, LCD message) replaced the sensor-verified clearance check.

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

### 3. Servo Calibration Propagation

Calibrated servo angles against the physical build. Mechanism is a **door flap** (servo opens/closes the flap directly). Angles calibrated 2026-07-18 using `arduino/servo_calibration/servo_calibration.ino`.

| Angle | State | What happens |
|-------|-------|-------------|
| 10° | CLOSED | Door flap shut (default on boot) |
| 80° | OPEN | Door flap open, book can enter |

**Files updated:**
- `WIRING_GUIDE.md` — servo BOM description, pin table, 2 ASCII diagrams, angle table (0/90 → 80/20), firmware #define table, checklist
- `backend/simulate_return.py` — log messages: 90→20 (open), 0→80 (closed)
- `wokwi/eBALIK_wokwi.ino` — angle defines 0/90 → 80/20 + calibrated comment block
- `currentsystemarchitecture.md` — BOM ("door flap"), state machine diagram, mechanism descriptions
- `TOOLS/eBALIK_project_context.md` — component table, module descriptions, workflow steps, BOM
- `README.md` — "servo-controlled slot" → "door flap mechanism", return flow description
- `arduino/eBALIK_arduino/eBALIK_arduino.ino` — full replacement with calibrated firmware (10/80 angles, door flap comment block)

---

## Current Hardware State

| Component | Status |
|-----------|--------|
| Arduino Uno R3 (CH340) | Connected, firmware uploaded (COM4) |
| MFRC522 RFID Reader | Wired (SPI: D10-D13, D9 RST) |
| SG90 Servo | Wired (D6), angles 10/80 calibrated |
| IR Sensor 1 (Entrance) | Wired (D2) |
| IR Sensor 2 (Full Entry) | Wired (D3) |
| Pin D4 | Free (previously Safety Obstruction) |
| Buzzer | Wired (D5) |
| Green LED | Wired (D7) |
| Red LED | Wired (D8) |
| LCD 16x2 I2C | Wired (A4/A5, addr 0x27) |

---

## Current Software State

| Component | Status |
|-----------|--------|
| Flask server | Running on http://localhost:5001 |
| SerialBridge | Connected to COM4, listening for serial |
| MySQL 8.4.9 | Running, eBALIK DB loaded with schema + seed data |
| Admin user | admin / admin123 (hash fixed) |
| HW monitor | NOT running (conflicts with SerialBridge for COM4) |

---

## Firmware v1.1 — Key Details

- **2 IR sensors** (Entrance D2, Full Entry D3), pin D4 free
- **Servo angles:** SERVO_CLOSED_ANGLE = 10 (door flap closed), SERVO_OPEN_ANGLE = 80 (door flap open)
- **Return flow:** VALID → servo stays closed, shows "Book approved" → entrance IR detects book → servo opens → full entry IR → closing warning (2s, double beep) → servo closes
- **Closing warning:** 2s delay, double beep (1200Hz × 2), LCD "Book received! / Closing shortly"
- **Debounce:** 3s cooldown for same RFID tag
- **Timeouts:** RFID validation 5s, insertion 15s, full entry 8s
- **Serial protocol:** RFID/STATUS/RETURN_SUCCESS/RETURN_FAILED → PC; VALID/INVALID/PING/RESET → Arduino
- **Buzzer tones:** approved (1800Hz), success (1500→2000Hz sweep), error (400Hz), closing warning (1200Hz × 2)

---

## What Does NOT Exist (for reference)

- Hardware tested: servo calibrated to 10/80 via physical testing, door flap confirmed working
- No HTTPS (local only, not needed)
- No cloud database (MySQL local)
- No multi-user auth (admin-only dashboard)
- No mobile app
- No deployment scripts beyond local laptop setup
- No reference to "50" as a servo angle anywhere in the repo
- No long-term servo holding reliability claims in code or docs
- No `gate mechanism`, `flap`, or `direct-drive` descriptions (all removed)
